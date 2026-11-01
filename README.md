# From Random Splits to Spatiotemporal Transfer

Reproducibility materials for the manuscript:

**From Random Splits to Spatiotemporal Transfer: Evaluating Machine-Learning Prediction of Vegetation Anomalies**

**Author:** Funda Yakar

**Version:** v1.0.0  
**Zenodo DOI:** https://doi.org/10.5281/zenodo.23864094

## Overview

This repository evaluates whether machine-learning skill for predicting negative monthly vegetation anomalies persists when models are transferred across geography, time, or both. The study uses MODIS NDVI and ERA5-Land hydroclimatic information aggregated within fixed broad land-cover strata across the 16 German federal states.

The binary target is an anomalously low NDVI state relative to an independent reference period; it is not interpreted as a direct physiological vegetation-stress measurement.

## Analytical design

- **Reference period:** 2001–2016
- **Prediction/evaluation period:** 2017–2024
- **Target months:** April–October
- **Final model rows:** 2,688
- **Primary outcome:** NDVI z-score < −1 using 2001–2016 state × land-cover × calendar-month reference statistics
- **Robustness outcome:** raw NDVI below the corresponding 2001–2016 20th percentile
- **Primary-event prevalence:** 29.09%
- **q20-event prevalence:** 35.57%

### Fixed land-cover support

MCD12Q1 Version 6.1 IGBP classes were grouped as forest (1–5), cropland (12), and grassland (10). Class 14 and all other classes were excluded. Only annual MCD12Q1 observations with `QC = 0` were used. A single modal broad-class map was constructed from 2001–2016 and held fixed through 2024. Binary fixed-class masks were aggregated to the native MOD13A3 grid as fractional class coverage.

MOD13A3 Version 6.1 NDVI retained `SummaryQA` values 0–1. ERA5-Land supplied 2-m air temperature, 0–7 cm volumetric soil water content, and total monthly precipitation. State × class × month values were fraction-weighted on the MOD13A3 valid-data support.

The validated Earth Engine extraction is in `code/final_fixedLC_MOD13A3_ERA5_export.js`.

### Antecedent predictors

Standardized anomalies of NDVI, temperature, soil moisture, and precipitation are represented at one-, two-, and three-month lags. Calendar month is encoded with sine/cosine terms and land cover with one-hot encoding. Federal-state identity is deliberately excluded as a predictor.

## Validation framework

The same model specifications are evaluated under four settings:

1. **Random CV:** stratified 5-fold cross-validation.
2. **Geographic transfer:** leave-one-of-four contiguous geographic blocks out.
3. **Temporal transfer:** rolling-origin future-year evaluation for 2020–2024.
4. **Spatiotemporal transfer:** each future test year crossed with an unseen geographic block.

Geographic blocks:

- **North:** Schleswig-Holstein, Hamburg, Niedersachsen, Bremen
- **Northeast:** Mecklenburg-Vorpommern, Brandenburg, Berlin, Sachsen-Anhalt
- **West-Central:** Nordrhein-Westfalen, Hessen, Rheinland-Pfalz, Saarland
- **South-East:** Baden-Wuerttemberg, Bayern, Thueringen, Sachsen

## Models

- Logistic regression: `C=1`, `lbfgs`, `max_iter=2000`
- Random forest: 200 trees, `max_features="sqrt"`, `min_samples_leaf=2`, `random_state=42`
- XGBoost: 200 estimators, learning rate 0.05, depth 3, subsample 0.8, column subsample 0.8, L2=1, `tree_method="hist"`, `random_state=42`
- No class weighting
- F1 probability threshold: 0.5

ROC-AUC is the primary performance measure. PR-AUC, F1, and Brier score are supporting metrics because event prevalence differs among held-out years.

## Repository structure

```text
.
├── README.md
├── CITATION.cff
├── REPRODUCIBILITY_CHECKS.md
├── requirements.txt
├── code/
│   ├── final_fixedLC_MOD13A3_ERA5_export.js
│   ├── combine_yearly_exports.py
│   ├── validate_final_gee_exports.py
│   └── final_vegetation_anomaly_reproducibility.py
├── data/
│   └── README.md
└── results/
    ├── README.md
    ├── analysis_manifest_final.json
    ├── validation_ladder_model_comparison_final.csv
    ├── predictor_configuration_rf_summary_final.csv
    ├── predictor_configuration_xgboost_summary_final.csv
    ├── lead_time_rf_summary_final.csv
    ├── lead_time_xgboost_summary_final.csv
    └── robustness_q20_summary_final.csv
```

## Reproduce the Earth Engine extraction

Run `code/final_fixedLC_MOD13A3_ERA5_export.js` in the Google Earth Engine Code Editor. It creates one CSV task for each year from 2001 through 2024. Each yearly export contains 576 state × month × fixed-land-cover records.

The exact yearly exports used for the manuscript and the combined modelling input are retained in the versioned Zenodo reproducibility package: https://doi.org/10.5281/zenodo.23864094

The helper scripts `code/combine_yearly_exports.py` and `code/validate_final_gee_exports.py` combine and validate those yearly exports once the archival data package is downloaded.

## Reproduce the modelling analysis

After obtaining `germany_fixedLC_2001_2024_combined.csv` from the archival data package, create an environment and install the locked dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run:

```bash
python code/final_vegetation_anomaly_reproducibility.py \
  --input data/germany_fixedLC_2001_2024_combined.csv \
  --outdir reproduced_results
```

Individual analysis families can also be run with `--stage main`, `--stage predictors`, `--stage lead`, or `--stage robustness`.

The script rebuilds the 2001–2016 reference statistics, creates the final April–October 2017–2024 modelling dataset, and reruns the validation ladder, predictor-family comparison, lead-time experiments, and q20 robustness analysis.

## Software versions

- Python 3.13.5
- NumPy 2.3.5
- pandas 2.2.3
- scikit-learn 1.8.0
- XGBoost 3.1.3

See `results/analysis_manifest_final.json` for the locked analysis settings.

## Data provenance

The aggregated inputs derive from publicly available products:

- MODIS MOD13A3 Version 6.1 monthly vegetation indices
- MODIS MCD12Q1 Version 6.1 annual land cover
- ERA5-Land monthly aggregated reanalysis
- FAO GAUL 2015 first-level administrative boundaries

Product citations and methodological details are provided in the manuscript.

## Reproducibility verification

The recovered final Earth Engine workflow was rerun for 2001 and reproduced the archived 2001 export to floating-point precision. The 24 archived yearly exports also reproduce the combined manuscript modelling input. The final Python pipeline was rerun from that combined input, and the summary tables versioned in this repository correspond to the manuscript results. See `REPRODUCIBILITY_CHECKS.md`.

## Data and archival DOI

The complete reproducibility package contains the 24 original yearly Earth Engine exports, the combined modelling input, intermediate model-ready data, complete fold-level outputs, and manuscript figures.

**Version v1.0.0:** https://doi.org/10.5281/zenodo.23864094

## Citation

Citation metadata are provided in `CITATION.cff`. The versioned archival release is available at https://doi.org/10.5281/zenodo.23864094.
