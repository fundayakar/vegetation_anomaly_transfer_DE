#!/usr/bin/env python3
"""Validate rerun GEE yearly exports against the archived final combined CSV.

Usage
-----
python validate_final_gee_exports.py \
  --candidate-dir /path/to/rerun_yearly_csvs \
  --reference germany_fixedLC_2001_2024_combined.csv

The script checks schema, 576 rows/year, unique state/class/month keys, missingness,
and numerical agreement for the eight exported numeric result/diagnostic columns.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

KEYS = ["year", "month", "adm1", "lc_class", "lc_name"]
NUMERIC = [
    "ndvi", "temp_c", "soil_moisture", "precip_mm",
    "ndvi_n", "lc_weight_sum", "lc_fraction_mean", "lc_area_km2",
]
REQUIRED = KEYS + NUMERIC


def load_candidate(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("germany_fixedLC_mod13a3_era5_*.csv"))
    if not files:
        raise FileNotFoundError(f"No yearly export CSVs found in {folder}")
    parts = []
    for f in files:
        d = pd.read_csv(f)
        missing = [c for c in REQUIRED if c not in d.columns]
        if missing:
            raise ValueError(f"{f.name}: missing columns {missing}")
        parts.append(d[REQUIRED].copy())
    return pd.concat(parts, ignore_index=True)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="raise").astype(int)
    out["month"] = pd.to_numeric(out["month"], errors="raise").astype(int)
    out["lc_class"] = pd.to_numeric(out["lc_class"], errors="raise").astype(int)
    for c in NUMERIC:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.sort_values(KEYS).reset_index(drop=True)


def qc_shape(df: pd.DataFrame, label: str) -> None:
    dup = int(df.duplicated(KEYS).sum())
    print(f"{label}: {len(df):,} rows; duplicate keys={dup}")
    if dup:
        raise AssertionError(f"{label} has duplicate keys")

    yearly = df.groupby("year").size()
    bad = yearly[yearly != 576]
    if len(bad):
        raise AssertionError(f"{label}: years not equal to 576 rows:\n{bad}")
    if set(yearly.index) != set(range(2001, 2025)):
        raise AssertionError(f"{label}: expected years 2001–2024")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-dir", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--atol", type=float, default=1e-6,
                    help="absolute tolerance for numeric comparison")
    ap.add_argument("--rtol", type=float, default=1e-8,
                    help="relative tolerance for numeric comparison")
    args = ap.parse_args()

    cand = normalize(load_candidate(args.candidate_dir))
    ref = normalize(pd.read_csv(args.reference)[REQUIRED])

    qc_shape(cand, "candidate")
    qc_shape(ref, "reference")

    cand_keys = pd.MultiIndex.from_frame(cand[KEYS])
    ref_keys = pd.MultiIndex.from_frame(ref[KEYS])
    missing = ref_keys.difference(cand_keys)
    extra = cand_keys.difference(ref_keys)
    if len(missing) or len(extra):
        print(f"Key mismatch: missing={len(missing)}, extra={len(extra)}")
        if len(missing):
            print("First missing keys:", list(missing[:10]))
        if len(extra):
            print("First extra keys:", list(extra[:10]))
        return 2

    merged = ref.merge(cand, on=KEYS, suffixes=("_ref", "_cand"), validate="one_to_one")

    all_ok = True
    print("\nNumeric comparison")
    print("------------------")
    for c in NUMERIC:
        a = merged[f"{c}_ref"].to_numpy(float)
        b = merged[f"{c}_cand"].to_numpy(float)
        same_nan = np.array_equal(np.isnan(a), np.isnan(b))
        finite = np.isfinite(a) & np.isfinite(b)
        if finite.any():
            absdiff = np.abs(a[finite] - b[finite])
            max_abs = float(absdiff.max())
            mean_abs = float(absdiff.mean())
            close = np.allclose(a[finite], b[finite], atol=args.atol, rtol=args.rtol)
        else:
            max_abs = mean_abs = 0.0
            close = True
        ok = same_nan and close
        all_ok &= ok
        print(f"{c:20s} ok={str(ok):5s}  max_abs={max_abs:.12g}  mean_abs={mean_abs:.12g}  nan_pattern={same_nan}")

    print("\nReference missing NDVI rows:", int(ref["ndvi"].isna().sum()))
    print("Candidate missing NDVI rows:", int(cand["ndvi"].isna().sum()))

    if all_ok:
        print("\nPASS: rerun exports reproduce the archived final dataset within tolerance.")
        return 0

    print("\nFAIL: at least one exported field differs from the archived final dataset.")
    print("Do not replace the public repository extraction workflow until the mismatch is resolved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
