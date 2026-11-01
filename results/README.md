# Result files

These tables correspond to the final analysis used for the manuscript.

- `analysis_manifest_final.json`: locked analysis settings, software versions, sample size, and event prevalence.
- `reference_stats_2001_2016_final.csv`: state × land-cover × calendar-month reference statistics.
- `model_ready_2017_2024_AprOct_final.csv`: final 2,688-row modelling dataset.
- `validation_ladder_*`: random, geographic, temporal, and spatiotemporal validation results.
- `predictor_configuration_*`: season/land-cover baseline, NDVI-only, hydroclimate-only, and full-predictor comparisons.
- `lead_time_*`: one-, two-, three-month and combined-history experiments.
- `robustness_q20_*`: validation ladder under the alternative reference-period 20th-percentile NDVI event definition.

ROC-AUC is the primary discrimination metric. PR-AUC, F1, and Brier score are reported as supporting metrics.
