#!/usr/bin/env python3
"""Combine the 24 archived yearly Google Earth Engine exports into the modelling input."""
from pathlib import Path
import argparse
import pandas as pd

REQUIRED = [
    "year", "month", "adm1", "lc_class", "lc_name", "ndvi", "temp_c",
    "soil_moisture", "precip_mm", "ndvi_n", "lc_weight_sum",
    "lc_fraction_mean", "lc_area_km2",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=Path("data/yearly_exports"))
    ap.add_argument("--output", type=Path, default=Path("data/germany_fixedLC_2001_2024_combined.csv"))
    args = ap.parse_args()

    files = sorted(args.input_dir.glob("germany_fixedLC_mod13a3_era5_*.csv"))
    if len(files) != 24:
        raise ValueError(f"Expected 24 yearly CSVs, found {len(files)}")

    parts = []
    for f in files:
        d = pd.read_csv(f)
        missing = [c for c in REQUIRED if c not in d.columns]
        if missing:
            raise ValueError(f"{f.name}: missing columns {missing}")
        parts.append(d[REQUIRED].copy())

    out = pd.concat(parts, ignore_index=True)
    out["year"] = pd.to_numeric(out["year"], errors="raise").astype(int)
    out["month"] = pd.to_numeric(out["month"], errors="raise")
    out["lc_class"] = pd.to_numeric(out["lc_class"], errors="raise").astype(int)

    if len(out) != 13824:
        raise ValueError(f"Expected 13,824 rows, found {len(out)}")
    if out.duplicated(["year", "month", "adm1", "lc_class", "lc_name"]).any():
        raise ValueError("Duplicate state × month × class keys found")

    # This ordering matches the archived manuscript input.
    out = out.sort_values(["adm1", "lc_name", "year", "month"]).reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out):,} rows to {args.output}")

if __name__ == "__main__":
    main()
