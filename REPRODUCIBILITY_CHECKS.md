# Reproducibility checks

The locked manuscript workflow was checked at three levels.

## 1. Earth Engine script → yearly export

The final Google Earth Engine extraction workflow was recovered from the analysis record. A fresh 2001 rerun reproduced the archived 2001 export to floating-point precision, including all state × month × class keys, missingness, NDVI, ERA5-Land variables, and support diagnostics.

The validated workflow is `code/final_fixedLC_MOD13A3_ERA5_export.js`.

## 2. Yearly exports → combined modelling input

All 24 archived yearly exports (2001–2024) contain 576 records each, for 13,824 total records. They contain no duplicate state × month × class keys. Concatenation and manuscript ordering reproduce `germany_fixedLC_2001_2024_combined.csv` to floating-point precision.

The exact 24 yearly exports and combined file are retained in the archival reproducibility data package. After downloading that package, place the yearly files in `data/yearly_exports/` and the combined file in `data/`, then run:

```bash
python code/validate_final_gee_exports.py \
  --candidate-dir data/yearly_exports \
  --reference data/germany_fixedLC_2001_2024_combined.csv
```

The yearly files can also be recombined independently with:

```bash
python code/combine_yearly_exports.py
```

## 3. Combined input → modelling results

The final Python pipeline rebuilds the independent 2001–2016 reference climatology, the 2017–2024 April–October modelling dataset, the four validation schemes, predictor-family comparisons, lead-time experiments, and the q20 robustness analysis.

A fresh rerun of this final pipeline was used to align the repository summary tables with the manuscript. The locked environment is recorded in `requirements.txt` and `results/analysis_manifest_final.json`.

The complete archival package additionally retains the generated reference statistics, 2,688-row model-ready table, fold-level outputs, and manuscript figures. A persistent Zenodo DOI will be added when that package is released.
