# Reproducibility checks

The repository was assembled from the locked manuscript workflow and checked at three levels.

## 1. GEE script → yearly export

The exact final Google Earth Engine script was recovered from the analysis record. A fresh rerun for 2001 reproduced the archived 2001 export to floating-point precision, including state × month × class keys, missingness, NDVI, ERA5-Land variables, and support diagnostics.

## 2. Yearly exports → combined modelling input

All 24 archived yearly exports (2001–2024) contain 576 records each, for 13,824 total records. They have no duplicate state × month × class keys. Concatenation and manuscript ordering reproduce `data/germany_fixedLC_2001_2024_combined.csv` to floating-point precision.

To check the archived exports against the combined file:

```bash
python code/validate_final_gee_exports.py \
  --candidate-dir data/yearly_exports \
  --reference data/germany_fixedLC_2001_2024_combined.csv
```

## 3. Combined input → modelling results

The final Python pipeline rebuilds the independent 2001–2016 reference climatology, the 2017–2024 April–October modelling dataset, the four validation schemes, predictor-family comparisons, lead-time experiments, and the q20 robustness analysis.

The locked environment is recorded in `requirements.txt` and `results/analysis_manifest_final.json`.
