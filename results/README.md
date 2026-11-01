# Result files

The versioned summary tables in this directory correspond to the final manuscript analysis.

- `analysis_manifest_final.json`: locked analysis settings, software versions, sample size, and event prevalence.
- `validation_ladder_model_comparison_final.csv`: model-level random, geographic, temporal, and spatiotemporal validation summary.
- `predictor_configuration_rf_summary_final.csv` and `predictor_configuration_xgboost_summary_final.csv`: season/land-cover baseline, NDVI-only, hydroclimate-only, and full-predictor comparisons.
- `lead_time_rf_summary_final.csv` and `lead_time_xgboost_summary_final.csv`: one-, two-, three-month and combined-history experiments.
- `robustness_q20_summary_final.csv`: validation ladder under the alternative reference-period 20th-percentile NDVI event definition.

The Python reproducibility pipeline regenerates the state × land-cover × month reference statistics, final 2,688-row model-ready table, full fold-level outputs, and these summary tables from the combined input dataset. Those larger/intermediate files are also retained in the archival Zenodo reproducibility package.

ROC-AUC is the primary discrimination metric. PR-AUC, F1, and Brier score are supporting metrics.
