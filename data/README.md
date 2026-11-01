# Data files

## `yearly_exports/`

The 24 yearly CSV files are the archived Google Earth Engine exports for 2001–2024. Each file contains 576 state × month × fixed-land-cover records (16 German federal states × 12 months × 3 broad vegetation classes).

The exact extraction script is `../code/final_fixedLC_MOD13A3_ERA5_export.js`.

## `germany_fixedLC_2001_2024_combined.csv`

This is the modelling input used by the Python reproducibility pipeline. It is the concatenation of the 24 yearly exports, sorted by federal state, land-cover name, year, and month.

Columns:

- `year`, `month`: calendar year and month
- `adm1`: German federal state (FAO GAUL ADM1 name)
- `lc_class`, `lc_name`: fixed broad land-cover class (forest, cropland, grassland)
- `ndvi`: fraction-weighted MOD13A3 monthly NDVI mean
- `temp_c`: fraction-weighted ERA5-Land 2-m air temperature (°C)
- `soil_moisture`: fraction-weighted ERA5-Land volumetric soil water content, layer 1 (0–7 cm)
- `precip_mm`: fraction-weighted ERA5-Land monthly precipitation (mm)
- `ndvi_n`: valid MOD13A3 support diagnostic
- `lc_weight_sum`: summed fixed land-cover fraction over valid support
- `lc_fraction_mean`: mean fixed land-cover fraction over valid support
- `lc_area_km2`: effective fraction-weighted class area over valid support

All source products are public Earth-observation/reanalysis datasets; see the manuscript and main README for provenance and citations.
