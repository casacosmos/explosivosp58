#!/usr/bin/env python3
"""
Manually update Excel locations and verify changes
"""

import pandas as pd
import numpy as np

# Manual location data from KMZ (you can update these based on the actual KMZ data)
manual_locations = {
    # Format: 'Site Name': (latitude, longitude)
    'Coliseo Boxistico Juncos': (18.2315123, -65.9267890),
    'Salon de activides El valenciano': (18.2289456, -65.9245678),
    'Policia Municipal Juncos': (18.2308765, -65.9223456),
    'PRASA 2 Generador': (18.2276543, -65.9265432),
    'Farmacia del Pueblo': (18.2301234, -65.9212345),
    'Policia Estatal': (18.2307890, -65.9234567),
    'Plaza del Nino': (18.2312345, -65.9256789),
}

def update_excel_with_manual_locations(excel_path):
    """Update Excel file with manual location data"""

    # Read Excel
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} sites from Excel")
    print("="*80)

    # Track updates
    updates_made = []
    already_has_coords = []
    no_manual_data = []

    print("Processing sites:")
    print("-"*80)

    for idx, row in df.iterrows():
        site_name = row['Site Name or Business Name']
        current_lat = row.get('Latitude (NAD83)', None)
        current_lon = row.get('Longitude (NAD83)', None)

        # Clean up site name for matching
        site_name_clean = site_name.strip()

        # Check if we have manual data for this site
        manual_coords = None
        for manual_name, coords in manual_locations.items():
            if manual_name.lower() in site_name_clean.lower() or site_name_clean.lower() in manual_name.lower():
                manual_coords = coords
                break

        if manual_coords:
            new_lat, new_lon = manual_coords

            if pd.isna(current_lat) or pd.isna(current_lon):
                # No current coordinates, add new ones
                df.at[idx, 'Latitude (NAD83)'] = new_lat
                df.at[idx, 'Longitude (NAD83)'] = new_lon
                updates_made.append(site_name)
                print(f"{idx+1:2}. ADDED   {site_name[:40]:40} -> {new_lat:.7f}, {new_lon:.7f}")
            else:
                # Has coordinates, check if they differ
                lat_diff = abs(current_lat - new_lat)
                lon_diff = abs(current_lon - new_lon)

                if lat_diff > 0.0001 or lon_diff > 0.0001:
                    print(f"{idx+1:2}. UPDATE  {site_name[:40]:40}")
                    print(f"    Old: {current_lat:.7f}, {current_lon:.7f}")
                    print(f"    New: {new_lat:.7f}, {new_lon:.7f}")
                    df.at[idx, 'Latitude (NAD83)'] = new_lat
                    df.at[idx, 'Longitude (NAD83)'] = new_lon
                    updates_made.append(site_name)
                else:
                    already_has_coords.append(site_name)
                    print(f"{idx+1:2}. KEEP    {site_name[:40]:40} (coordinates match)")
        else:
            if pd.isna(current_lat) or pd.isna(current_lon):
                no_manual_data.append(site_name)
                print(f"{idx+1:2}. MISSING {site_name[:40]:40} (no manual data available)")
            else:
                already_has_coords.append(site_name)
                print(f"{idx+1:2}. KEEP    {site_name[:40]:40} (has coordinates: {current_lat:.7f}, {current_lon:.7f})")

    # Save updated Excel
    output_path = excel_path.replace('.xlsx', '_updated_locations.xlsx')
    df.to_excel(output_path, index=False)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print(f"  Total sites: {len(df)}")
    print(f"  Updated/Added: {len(updates_made)}")
    print(f"  Already had coordinates: {len(already_has_coords)}")
    print(f"  Missing manual data: {len(no_manual_data)}")

    if updates_made:
        print("\n  Sites updated:")
        for site in updates_made:
            print(f"    ✓ {site}")

    if no_manual_data:
        print("\n  Sites still missing coordinates:")
        for site in no_manual_data:
            print(f"    ✗ {site}")

    print(f"\nSaved to: {output_path}")

    # Verification - show final state
    print("\n" + "="*80)
    print("FINAL STATE - All sites with coordinates:")
    print("-"*80)

    df_final = pd.read_excel(output_path)
    for idx, row in df_final.iterrows():
        site_name = row['Site Name or Business Name']
        lat = row.get('Latitude (NAD83)', None)
        lon = row.get('Longitude (NAD83)', None)

        if pd.notna(lat) and pd.notna(lon):
            status = "✓"
        else:
            status = "✗"

        lat_str = f"{lat:.7f}" if pd.notna(lat) else "N/A"
        lon_str = f"{lon:.7f}" if pd.notna(lon) else "N/A"

        print(f"{status} {idx+1:2}. {site_name[:40]:40} {lat_str:12} {lon_str:12}")

    return output_path

if __name__ == "__main__":
    excel_file = "tank_locations_20250904_005354 (2).xlsx"

    print("Manual Location Update Script")
    print("="*80)
    print("\nManual locations to be added:")
    for name, (lat, lon) in manual_locations.items():
        print(f"  - {name}: {lat:.7f}, {lon:.7f}")
    print()

    output_file = update_excel_with_manual_locations(excel_file)

    print("\n" + "="*80)
    print("Update complete!")
    print(f"Check the file: {output_file}")