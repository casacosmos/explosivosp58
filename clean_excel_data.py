#!/usr/bin/env python3
"""
Clean Excel file by removing auto-assigned 500 gallon values for tanks without measurements
"""

import pandas as pd
import numpy as np

# Read the Excel file
df = pd.read_excel('tank_locations_20250904_005354.xlsx')

print(f"Cleaning Excel file with {len(df)} tanks...")
cleaned_count = 0

# Clear Tank Capacity and ASD for tanks without real measurements
for idx, row in df.iterrows():
    measurements = row['Tank Measurements']
    capacity = row['Tank Capacity']

    # Check if this is likely an auto-assigned value
    if capacity == 500 and (pd.isna(measurements) or str(measurements).strip() == ''):
        # Clear the auto-assigned values
        df.at[idx, 'Tank Capacity'] = np.nan
        df.at[idx, 'Acceptable Separation Distance Calculated '] = ''
        cleaned_count += 1
        print(f"  Cleared Row {idx+1}: {row['Site Name or Business Name ']} (no measurements)")

# Save cleaned Excel
df.to_excel('tank_locations_20250904_005354_cleaned.xlsx', index=False)
df.to_excel('tank_locations_20250904_005354.xlsx', index=False)

print(f"\nCleaned {cleaned_count} tanks with auto-assigned values")
print("Saved cleaned Excel file")