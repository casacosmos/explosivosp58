#!/usr/bin/env python3
"""
Add sample capacities and optional dike information to a KMZ-generated Excel.

Usage:
  python add_sample_data_to_excel.py input.xlsx [-o output.xlsx]

Behavior:
  - Fills empty 'Tank Capacity' with deterministic sample values (e.g., '500 gal').
  - Fills 'Tank Type' as 'diesel' where missing.
  - Optionally marks some rows as having a dike and adds simple dike dimensions.

Notes:
  - Only fills empty cells; existing values are preserved.
  - Output defaults to '<dirname>/tank_locations_with_measurements.xlsx' if -o not given.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


FIRST_COL = 'Site Name or Business Name '


def add_samples(df: pd.DataFrame, add_dikes: bool = True) -> pd.DataFrame:
    capacities_cycle = [500, 750, 1000, 1200, 1500, 2000, 2500, 3000]
    dims_cycle = [(8, 4, 5), (10, 6, 4), (12, 8, 5), (15, 5, 6)]
    # Ensure expected columns exist
    for col in [
        'Tank Capacity', 'Tank Measurements', 'Dike Measurements', 'Tank Type',
        'Has Dike', 'Additional information ', 'Latitude (NAD83)', 'Longitude (NAD83)'
    ]:
        if col not in df.columns:
            df[col] = None

    # Cast columns to object to avoid dtype warnings on string assignment
    for c in ['Tank Capacity', 'Tank Type', 'Has Dike', 'Dike Measurements', 'Tank Measurements']:
        if c in df.columns:
            try:
                df[c] = df[c].astype('object')
            except Exception:
                pass

    # Fill a mix of capacities and measurements
    for i in range(len(df)):
        # Decide whether this row should be measurement-only (no gallons string)
        measurement_only = (i % 4 == 2)  # every 4th row starting at index 2
        if measurement_only:
            # leave Tank Capacity empty, fill Tank Measurements if empty
            if pd.isna(df.at[i, 'Tank Measurements']) or str(df.at[i, 'Tank Measurements']).strip() == '':
                L, W, H = dims_cycle[(i // 4) % len(dims_cycle)]
                df.at[i, 'Tank Measurements'] = f"{L} ft x {W} ft x {H} ft"
            # ensure capacity stays blank
            if not (pd.isna(df.at[i, 'Tank Capacity']) or str(df.at[i, 'Tank Capacity']).strip() == ''):
                df.at[i, 'Tank Capacity'] = ''
        else:
            # capacity-only rows: fill Tank Capacity if empty
            if pd.isna(df.at[i, 'Tank Capacity']) or str(df.at[i, 'Tank Capacity']).strip() == '':
                gal = capacities_cycle[i % len(capacities_cycle)]
                df.at[i, 'Tank Capacity'] = f"{gal} gal"

    # Default tank type
    mask_type = df['Tank Type'].isna() | (df['Tank Type'].astype(str).str.strip() == '')
    df.loc[mask_type, 'Tank Type'] = 'diesel'

    if add_dikes:
        # Mark every 3rd row as having a simple dike if empty
        for i in range(len(df)):
            has_dike_val = str(df.at[i, 'Has Dike']).strip().lower() if not pd.isna(df.at[i, 'Has Dike']) else ''
            if (i % 3 == 2) and has_dike_val in ('', 'nan', 'none'):
                df.at[i, 'Has Dike'] = 'Yes'
                if pd.isna(df.at[i, 'Dike Measurements']) or str(df.at[i, 'Dike Measurements']).strip() == '':
                    df.at[i, 'Dike Measurements'] = 'Length 4 ft ; Width 4 ft'

    return df


def main():
    ap = argparse.ArgumentParser(description='Add sample data to tank Excel')
    ap.add_argument('input', help='Input Excel path')
    ap.add_argument('-o', '--output', help='Output Excel path')
    ap.add_argument('--no-dikes', action='store_true', help='Do not add dike info')
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"Input not found: {src}")
    dst = Path(args.output) if args.output else (src.parent / 'tank_locations_with_measurements.xlsx')

    df = pd.read_excel(src)
    df = add_samples(df, add_dikes=not args.no_dikes)
    df.to_excel(dst, index=False)
    print(f"Wrote: {dst}")


if __name__ == '__main__':
    main()
