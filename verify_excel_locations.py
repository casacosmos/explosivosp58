#!/usr/bin/env python3
"""
Verify which sites have real location data and which are missing
"""

import pandas as pd
import numpy as np

def verify_location_data(excel_path):
    """Verify and report on location data status"""

    # Read Excel
    df = pd.read_excel(excel_path)
    print(f"Verifying location data for {len(df)} sites")
    print("="*80)

    # Categorize sites
    has_coordinates = []
    missing_coordinates = []

    print("Site Location Status:")
    print("-"*80)
    print(f"{'#':3} {'Site Name':45} {'Latitude':12} {'Longitude':12} {'Status':10}")
    print("-"*80)

    for idx, row in df.iterrows():
        site_name = row['Site Name or Business Name']
        lat = row.get('Latitude (NAD83)', None)
        lon = row.get('Longitude (NAD83)', None)

        if pd.notna(lat) and pd.notna(lon):
            has_coordinates.append({
                'name': site_name,
                'lat': lat,
                'lon': lon
            })
            status = "✓ HAS DATA"
            lat_str = f"{lat:.7f}"
            lon_str = f"{lon:.7f}"
        else:
            missing_coordinates.append(site_name)
            status = "✗ MISSING"
            lat_str = "N/A"
            lon_str = "N/A"

        print(f"{idx+1:3} {site_name[:45]:45} {lat_str:12} {lon_str:12} {status:10}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print(f"  Total sites: {len(df)}")
    print(f"  Sites WITH coordinates: {len(has_coordinates)}")
    print(f"  Sites WITHOUT coordinates: {len(missing_coordinates)}")

    if missing_coordinates:
        print("\n  Sites missing coordinates:")
        for i, site in enumerate(missing_coordinates, 1):
            print(f"    {i}. {site}")

        print("\n  ⚠️  WARNING: These sites need real location data from the KMZ file")
        print("     Do NOT use made-up coordinates!")

    # Check for suspicious coordinates (all zeros or defaults)
    print("\n" + "="*80)
    print("Checking for suspicious coordinates...")
    suspicious = []
    for item in has_coordinates:
        # Check for coordinates that might be defaults or errors
        if abs(item['lat']) < 1 or abs(item['lon']) < 1:
            suspicious.append(item)
        # Check if outside Puerto Rico area (rough bounds)
        elif not (17.5 < item['lat'] < 18.6 and -67.5 < item['lon'] < -65.0):
            suspicious.append(item)

    if suspicious:
        print(f"  Found {len(suspicious)} sites with potentially incorrect coordinates:")
        for item in suspicious:
            print(f"    - {item['name']}: {item['lat']}, {item['lon']}")
    else:
        print("  All coordinates appear to be in valid range for Puerto Rico")

    return has_coordinates, missing_coordinates

if __name__ == "__main__":
    print("Location Data Verification Tool")
    print("="*80)
    print("\nChecking original file with updates...")
    excel_file = "tank_locations_20250904_005354 (2).xlsx"

    has_coords, missing = verify_location_data(excel_file)

    print("\n" + "="*80)
    print("IMPORTANT NOTES:")
    print("  1. Only use real coordinates from the KMZ file")
    print("  2. Do not make up or estimate coordinates")
    print("  3. Sites without coordinates should remain empty until real data is available")
    print("  4. To get real coordinates, the KMZ file must be properly parsed")