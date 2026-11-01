#!/usr/bin/env python3
"""
Final reproducibility pipeline for the vegetation-anomaly transferability study.

Input
-----
Fixed-land-cover monthly panel exported from Google Earth Engine:
    germany_fixedLC_2001_2024_combined.csv

Pipeline
--------
1. Build 2001–2016 reference climatologies and fixed 20th-percentile thresholds.
2. Standardize 2001–2024 monthly NDVI and hydroclimatic variables.
3. Construct 1–3 month antecedent lags on the full monthly series.
4. Restrict prediction targets to April–October 2017–2024.
5. Evaluate Logistic Regression, Random Forest, and XGBoost under:
   - random 5-fold CV
   - four contiguous geographic blocks
   - rolling-origin temporal transfer
   - combined spatiotemporal transfer
6. Run predictor-family and lead-time experiments for RF and XGBoost.
7. Repeat the validation ladder with the reference-period 20th-percentile target.

No class weighting or scale_pos_weight is used in the final analysis.
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


SEED = 42
REFERENCE_START = 2001
REFERENCE_END = 2016
PREDICTION_START = 2017
PREDICTION_END = 2024
TARGET_MONTHS = list(range(4, 11))

GROUP_COLS = ["adm1", "lc_name", "month"]
RAW_VARS = {
    "ndvi": "ndvi_z",
    "temp_c": "temp_z",
    "soil_moisture": "sm_z",
    "precip_mm": "precip_z",
}

SPATIAL_BLOCKS = {
    "North": [
        "Schleswig-Holstein", "Hamburg", "Niedersachsen", "Bremen"
    ],
    "Northeast": [
        "Mecklenburg-Vorpommern", "Brandenburg", "Berlin", "Sachsen-Anhalt"
    ],
    "West-Central": [
        "Nordrhein-Westfalen", "Hessen", "Rheinland-Pfalz", "Saarland"
    ],
    "South-East": [
        "Baden-Wuerttemberg", "Bayern", "Thueringen", "Sachsen"
    ],
}

MONTH_FEATURES = ["month_sin", "month_cos"]
NDVI_LAGS = [f"ndvi_z_lag{k}" for k in (1, 2, 3)]
TEMP_LAGS = [f"temp_z_lag{k}" for k in (1, 2, 3)]
SM_LAGS = [f"sm_z_lag{k}" for k in (1, 2, 3)]
PRECIP_LAGS = [f"precip_z_lag{k}" for k in (1, 2, 3)]
HYDRO_LAGS = TEMP_LAGS + SM_LAGS + PRECIP_LAGS
FULL_DYNAMIC = NDVI_LAGS + HYDRO_LAGS


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/germany_fixedLC_2001_2024_combined.csv"),
    )
    p.add_argument(
        "--outdir",
        type=Path,
        default=Path("results_final"),
    )
    p.add_argument(
        "--stage",
        choices=["all", "main", "predictors", "lead", "robustness"],
        default="all",
        help="Run all analyses or one analysis family. Preprocessing is always rebuilt.",
    )
    return p.parse_args()


def build_analysis_dataset(raw: pd.DataFrame, outdir: Path):
    df = raw.copy()
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df = df.sort_values(["adm1", "lc_name", "year", "month"]).reset_index(drop=True)

    ref = df.loc[df["year"].between(REFERENCE_START, REFERENCE_END)].copy()

    # Mean, SD, and n for fixed reference climatology.
    pieces = []
    for raw_col, z_col in RAW_VARS.items():
        prefix = z_col.replace("_z", "")
        s = (
            ref.groupby(GROUP_COLS, as_index=False)
            .agg(
                **{
                    f"{prefix}_mean": (raw_col, "mean"),
                    f"{prefix}_std": (raw_col, "std"),
                    f"{prefix}_nref": (raw_col, "count"),
                }
            )
        )
        pieces.append(s)

    ref_stats = pieces[0]
    for p in pieces[1:]:
        ref_stats = ref_stats.merge(p, on=GROUP_COLS, how="outer")

    # Fixed reference-period 20th percentile of raw NDVI.
    q20 = (
        ref.groupby(GROUP_COLS)["ndvi"]
        .quantile(0.20)
        .rename("ndvi_q20")
        .reset_index()
    )
    ref_stats = ref_stats.merge(q20, on=GROUP_COLS, how="left")

    df = df.merge(ref_stats, on=GROUP_COLS, how="left")

    # Standardized anomalies using the 2001–2016 reference period only.
    df["ndvi_z"] = (df["ndvi"] - df["ndvi_mean"]) / df["ndvi_std"]
    df["temp_z"] = (df["temp_c"] - df["temp_mean"]) / df["temp_std"]
    df["sm_z"] = (df["soil_moisture"] - df["sm_mean"]) / df["sm_std"]
    df["precip_z"] = (df["precip_mm"] - df["precip_mean"]) / df["precip_std"]

    # Primary and robustness targets.
    df["negative_veg_anomaly"] = (df["ndvi_z"] < -1.0).astype("Int64")
    df["negative_veg_anomaly_q20"] = (df["ndvi"] < df["ndvi_q20"]).astype("Int64")

    # Cyclic seasonality.
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)

    # Antecedent lags are created on the complete monthly series.
    lag_sources = ["ndvi_z", "temp_z", "sm_z", "precip_z"]
    for col in lag_sources:
        for lag in (1, 2, 3):
            df[f"{col}_lag{lag}"] = (
                df.groupby(["adm1", "lc_name"], sort=False)[col].shift(lag)
            )

    model = df.loc[
        df["year"].between(PREDICTION_START, PREDICTION_END)
        & df["month"].isin(TARGET_MONTHS)
    ].copy()

    required = (
        ["negative_veg_anomaly", "negative_veg_anomaly_q20", "lc_name"]
        + MONTH_FEATURES
        + FULL_DYNAMIC
    )
    model = model.dropna(subset=required).reset_index(drop=True)
    model["negative_veg_anomaly"] = model["negative_veg_anomaly"].astype(int)
    model["negative_veg_anomaly_q20"] = model["negative_veg_anomaly_q20"].astype(int)

    # Exact final-data integrity checks.
    if len(model) != 2688:
        raise ValueError(f"Expected 2688 model rows; obtained {len(model)}.")
    if model[required].isna().any().any():
        raise ValueError("Missing values remain in final model predictors/targets.")

    ref_stats.to_csv(outdir / "reference_stats_2001_2016_final.csv", index=False)
    model.to_csv(outdir / "model_ready_2017_2024_AprOct_final.csv", index=False)

    return df, ref_stats, model


def make_model(name: str):
    if name == "Logistic":
        return LogisticRegression(
            C=1.0,
            solver="lbfgs",
            max_iter=2000,
            random_state=SEED,
        )
    if name == "RF":
        return RandomForestClassifier(
            n_estimators=200,
            max_features="sqrt",
            min_samples_leaf=2,
            random_state=SEED,
            n_jobs=-1,
        )
    if name == "XGBoost":
        return XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            min_child_weight=1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            reg_alpha=0.0,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=SEED,
            n_jobs=-1,
            verbosity=0,
        )
    raise KeyError(name)


def make_pipeline(model_name: str, numeric_features: list[str]):
    pre = ColumnTransformer(
        transformers=[
            (
                "land_cover",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["lc_name"],
            )
        ],
        remainder="passthrough",
        verbose_feature_names_out=False,
    )
    return Pipeline(
        [
            ("preprocess", pre),
            ("model", make_model(model_name)),
        ]
    )


def make_splits(df: pd.DataFrame, y: np.ndarray, scheme: str):
    if scheme == "random":
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
        for i, (train, test) in enumerate(skf.split(df, y), start=1):
            yield train, test, f"R{i}"
        return

    if scheme == "spatial":
        for block, states in SPATIAL_BLOCKS.items():
            test_mask = df["adm1"].isin(states).to_numpy()
            yield np.where(~test_mask)[0], np.where(test_mask)[0], block
        return

    if scheme == "temporal":
        # Three full years (2017–2019) are used as the initial calibration window.
        for test_year in range(2020, 2025):
            train_mask = (df["year"] < test_year).to_numpy()
            test_mask = (df["year"] == test_year).to_numpy()
            yield np.where(train_mask)[0], np.where(test_mask)[0], str(test_year)
        return

    if scheme == "spatiotemporal":
        for test_year in range(2020, 2025):
            for block, states in SPATIAL_BLOCKS.items():
                held_out_space = df["adm1"].isin(states)
                train_mask = ((df["year"] < test_year) & (~held_out_space)).to_numpy()
                test_mask = ((df["year"] == test_year) & held_out_space).to_numpy()
                yield (
                    np.where(train_mask)[0],
                    np.where(test_mask)[0],
                    f"{test_year}_{block}",
                )
        return

    raise KeyError(scheme)


def score_predictions(y_true, prob):
    pred = (prob >= 0.5).astype(int)
    return {
        "roc_auc": roc_auc_score(y_true, prob),
        "pr_auc": average_precision_score(y_true, prob),
        "f1": f1_score(y_true, pred, zero_division=0),
        "brier": brier_score_loss(y_true, prob),
        "n": len(y_true),
        "events": int(np.sum(y_true)),
        "prevalence": float(np.mean(y_true)),
    }


def run_scheme(
    df: pd.DataFrame,
    model_name: str,
    scheme: str,
    numeric_features: list[str],
    target: str,
):
    X = df[["lc_name"] + numeric_features]
    y = df[target].to_numpy(dtype=int)
    rows = []

    for train, test, fold in make_splits(df, y, scheme):
        pipe = make_pipeline(model_name, numeric_features)
        pipe.fit(X.iloc[train], y[train])
        prob = pipe.predict_proba(X.iloc[test])[:, 1]
        metrics = score_predictions(y[test], prob)
        metrics.update({"model": model_name, "scheme": scheme, "fold": fold})
        rows.append(metrics)

    return pd.DataFrame(rows)


def summarize_folds(folds: pd.DataFrame):
    metrics = ["roc_auc", "pr_auc", "f1", "brier"]
    out = (
        folds.groupby(["model", "scheme"], sort=False)[metrics]
        .agg(["mean", "std"])
        .reset_index()
    )
    out.columns = [
        "model",
        "scheme",
        "roc_auc_mean",
        "roc_auc_sd",
        "pr_auc_mean",
        "pr_auc_sd",
        "f1_mean",
        "f1_sd",
        "brier_mean",
        "brier_sd",
    ]
    nfolds = (
        folds.groupby(["model", "scheme"], sort=False)
        .size()
        .rename("n_folds")
        .reset_index()
    )
    return out.merge(nfolds, on=["model", "scheme"])


def run_validation_ladder(df, target):
    frames = []
    for model in ["Logistic", "RF", "XGBoost"]:
        for scheme in ["random", "spatial", "temporal", "spatiotemporal"]:
            frames.append(
                run_scheme(
                    df,
                    model,
                    scheme,
                    MONTH_FEATURES + FULL_DYNAMIC,
                    target,
                )
            )
    folds = pd.concat(frames, ignore_index=True)
    return folds, summarize_folds(folds)


def summarize_experiment(folds: pd.DataFrame, key: str):
    metrics = ["roc_auc", "pr_auc", "f1", "brier"]
    out = (
        folds.groupby([key, "scheme"], sort=False)[metrics]
        .agg(["mean", "std"])
        .reset_index()
    )
    out.columns = [
        key,
        "scheme",
        "roc_auc",
        "roc_sd",
        "pr_auc",
        "pr_sd",
        "f1",
        "f1_sd",
        "brier",
        "brier_sd",
    ]
    nfolds = (
        folds.groupby([key, "scheme"], sort=False)
        .size()
        .rename("n_folds")
        .reset_index()
    )
    return out.merge(nfolds, on=[key, "scheme"])


def run_predictor_configurations(df, model_name, target="negative_veg_anomaly"):
    configs = {
        "Season+LC": MONTH_FEATURES,
        "NDVI-only": MONTH_FEATURES + NDVI_LAGS,
        "Hydroclimate-only": MONTH_FEATURES + HYDRO_LAGS,
        "Full": MONTH_FEATURES + FULL_DYNAMIC,
    }
    rows = []
    for config, features in configs.items():
        for scheme in ["spatial", "temporal"]:
            tmp = run_scheme(df, model_name, scheme, features, target)
            tmp["config"] = config
            rows.append(tmp)
    folds = pd.concat(rows, ignore_index=True)
    return folds, summarize_experiment(folds, "config")


def run_lead_time(df, model_name, target="negative_veg_anomaly"):
    configs = {
        "Lead-1": MONTH_FEATURES
        + ["ndvi_z_lag1", "temp_z_lag1", "sm_z_lag1", "precip_z_lag1"],
        "Lead-2": MONTH_FEATURES
        + ["ndvi_z_lag2", "temp_z_lag2", "sm_z_lag2", "precip_z_lag2"],
        "Lead-3": MONTH_FEATURES
        + ["ndvi_z_lag3", "temp_z_lag3", "sm_z_lag3", "precip_z_lag3"],
        "History-1to3": MONTH_FEATURES + FULL_DYNAMIC,
    }
    rows = []
    for config, features in configs.items():
        for scheme in ["spatial", "temporal"]:
            tmp = run_scheme(df, model_name, scheme, features, target)
            tmp["config"] = config
            rows.append(tmp)
    folds = pd.concat(rows, ignore_index=True)
    return folds, summarize_experiment(folds, "config")


def main():
    args = parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.input)
    _, ref_stats, model_df = build_analysis_dataset(raw, args.outdir)

    if args.stage in {"all", "main"}:
        folds, summary = run_validation_ladder(model_df, "negative_veg_anomaly")
        folds.to_csv(args.outdir / "validation_ladder_fold_results_final.csv", index=False)
        summary.to_csv(args.outdir / "validation_ladder_model_comparison_final.csv", index=False)
        print("\nMain validation summary:")
        print(summary.to_string(index=False))

    if args.stage in {"all", "predictors"}:
        for model in ["RF", "XGBoost"]:
            pfolds, psum = run_predictor_configurations(model_df, model)
            stem = model.lower()
            pfolds.to_csv(args.outdir / f"predictor_configuration_{stem}_folds_final.csv", index=False)
            psum.to_csv(args.outdir / f"predictor_configuration_{stem}_summary_final.csv", index=False)

    if args.stage in {"all", "lead"}:
        for model in ["RF", "XGBoost"]:
            lfolds, lsum = run_lead_time(model_df, model)
            stem = model.lower()
            lfolds.to_csv(args.outdir / f"lead_time_{stem}_folds_final.csv", index=False)
            lsum.to_csv(args.outdir / f"lead_time_{stem}_summary_final.csv", index=False)

    if args.stage in {"all", "robustness"}:
        rfolds, rsummary = run_validation_ladder(model_df, "negative_veg_anomaly_q20")
        rfolds.to_csv(args.outdir / "robustness_q20_folds_final.csv", index=False)
        rsummary.to_csv(args.outdir / "robustness_q20_summary_final.csv", index=False)

    manifest = {
        "seed": SEED,
        "reference_period": [REFERENCE_START, REFERENCE_END],
        "prediction_period": [PREDICTION_START, PREDICTION_END],
        "prediction_months": TARGET_MONTHS,
        "primary_target": "ndvi_z < -1",
        "robustness_target": "raw NDVI < state × land-cover × calendar-month 2001–2016 20th percentile",
        "class_weighting": "none",
        "f1_probability_threshold": 0.5,
        "models": {
            "Logistic": {"C": 1.0, "solver": "lbfgs", "max_iter": 2000},
            "RF": {"n_estimators": 200, "max_features": "sqrt", "min_samples_leaf": 2},
            "XGBoost": {
                "n_estimators": 200, "learning_rate": 0.05, "max_depth": 3,
                "min_child_weight": 1, "subsample": 0.8, "colsample_bytree": 0.8,
                "reg_lambda": 1.0, "reg_alpha": 0.0, "tree_method": "hist"
            },
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "n_model_rows": int(len(model_df)),
        "primary_event_rate": float(model_df["negative_veg_anomaly"].mean()),
        "q20_event_rate": float(model_df["negative_veg_anomaly_q20"].mean()),
    }
    with open(args.outdir / "analysis_manifest_final.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\nFinal analysis stage complete.")
    print(f"Stage: {args.stage}")
    print(f"Model rows: {len(model_df)}")
    print(f"Primary event rate: {model_df['negative_veg_anomaly'].mean():.3f}")
    print(f"Q20 event rate: {model_df['negative_veg_anomaly_q20'].mean():.3f}")
    print(f"Outputs written to: {args.outdir.resolve()}")


if __name__ == "__main__":
    main()
