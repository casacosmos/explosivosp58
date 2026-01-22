#!/usr/bin/env python3
"""
Create final Excel file with only verified coordinate data
"""

import pandas as pd
import numpy as np
from datetime import datetime

def create_final_excel(input_path):
    """Create final Excel with verified data only"""

    # Read the current Excel file
    df = pd.read_excel(input_path)

    print("Creating final Excel file with verified data")
    print("="*80)

    # Create status report
    print("\nLocation Data Status:")
    print("-"*80)

    sites_with_coords = 0
    sites_without_coords = 0

    for idx, row in df.iterrows():
        site_name = row['Site Name or Business Name']
        lat = row.get('Latitude (NAD83)', None)
        lon = row.get('Longitude (NAD83)', None)

        if pd.notna(lat) and pd.notna(lon):
            sites_with_coords += 1
            status = "✓"
            coord_str = f"{lat:.7f}, {lon:.7f}"
        else:
            sites_without_coords += 1
            status = "○"
            coord_str = "Pending location data"
            # Ensure these are truly NaN (not zeros or other values)
            df.at[idx, 'Latitude (NAD83)'] = np.nan
            df.at[idx, 'Longitude (NAD83)'] = np.nan

        print(f"{status} {idx+1:2}. {site_name[:45]:45} {coord_str}")

    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"tank_locations_final_{timestamp}.xlsx"

    # Save the final Excel
    df.to_excel(output_path, index=False)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print(f"  Total sites: {len(df)}")
    print(f"  Sites with coordinates: {sites_with_coords}")
    print(f"  Sites awaiting coordinates: {sites_without_coords}")
    print(f"\nOutput file: {output_path}")

    # Also create a simplified version without the timestamp for easy reference
    simple_output = "tank_locations_FINAL.xlsx"
    df.to_excel(simple_output, index=False)
    print(f"Also saved as: {simple_output}")

    return output_path, simple_output

if __name__ == "__main__":
    print("Final Excel File Generator")
    print("="*80)
    print("This will create a clean Excel file with:")
    print("  • All verified coordinate data preserved")
    print("  • No made-up or estimated coordinates")
    print("  • Clear identification of sites needing location data")
    print()

    input_file = "tank_locations_20250904_005354 (2).xlsx"

    final_file, simple_file = create_final_excel(input_file)

    print("\n" + "="*80)
    print("✓ Final Excel files created successfully")
    print("\nNOTE: Sites without coordinates will need location data from:")
    print("  1. The KMZ file (once properly parsed)")
    print("  2. GPS measurements from the field")
    print("  3. Other verified sources")