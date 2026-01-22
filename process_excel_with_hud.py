#!/usr/bin/env python3
"""
Process Excel file directly through HUD calculator to get ASD distances
"""

import pandas as pd
import json
import subprocess
from pathlib import Path
import tempfile
import re

def parse_tank_measurements(measurement_str):
    """Parse tank measurements to extract volume or dimensions"""
    if pd.isna(measurement_str):
        return None

    # Try to extract dimensions (diameter x height or similar patterns)
    # Example: '39"x46"x229"' or '182"55"x26"'
    measurement_str = str(measurement_str)

    # Remove spaces and normalize
    measurement_str = measurement_str.replace(' ', '').replace('"', '')

    # Try to find dimensions pattern
    if 'x' in measurement_str.lower():
        parts = measurement_str.lower().split('x')
        if len(parts) >= 2:
            try:
                # Extract numeric values
                dims = []
                for part in parts:
                    # Extract first number from each part
                    match = re.search(r'(\d+\.?\d*)', part)
                    if match:
                        dims.append(float(match.group(1)))

                if len(dims) >= 2:
                    # Assume cylindrical tank (diameter x height)
                    # Volume = π * r^2 * h (in cubic inches)
                    # Convert to gallons (1 gallon = 231 cubic inches)
                    if len(dims) == 2:
                        diameter = dims[0]
                        height = dims[1]
                        volume_cubic_inches = 3.14159 * (diameter/2)**2 * height
                        volume_gallons = volume_cubic_inches / 231
                        return int(volume_gallons)
                    elif len(dims) == 3:
                        # Rectangular tank
                        volume_cubic_inches = dims[0] * dims[1] * dims[2]
                        volume_gallons = volume_cubic_inches / 231
                        return int(volume_gallons)
            except:
                pass

    return None

def extract_tank_capacity(row):
    """Extract tank capacity from various columns"""
    # First check Tank Capacity column
    if pd.notna(row['Tank Capacity']):
        try:
            capacity = float(row['Tank Capacity'])
            if capacity > 0:
                return capacity
        except:
            pass

    # Try to parse from Tank Measurements
    volume = parse_tank_measurements(row['Tank Measurements'])
    if volume and volume > 0:
        return volume

    # Return None if no valid data found
    return None

def process_excel_through_hud(excel_path):
    """Process Excel file through HUD calculator"""

    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"Processing {len(df)} tanks from Excel file")

    # Prepare tank data for HUD processing
    tanks = []
    skipped_tanks = []
    tank_id = 1

    for idx, row in df.iterrows():
        capacity = extract_tank_capacity(row)
        tank_name = str(row['Site Name or Business Name ']) if pd.notna(row['Site Name or Business Name ']) else f"Tank_{idx+1}"

        if capacity is None:
            skipped_tanks.append(f"{idx+1}: {tank_name} (no measurements)")
            continue

        tank_data = {
            "id": tank_id,  # Sequential ID for valid tanks only
            "name": tank_name,
            "latitude": row['Latitude (NAD83)'],
            "longitude": row['Longitude (NAD83)'],
            "volume": capacity,
            "is_underground": False,  # Assume aboveground unless specified
            "has_dike": pd.notna(row['Dike Measurements']) and str(row['Dike Measurements']).strip() != '',
            "original_index": idx  # Keep track of original Excel row
        }
        tanks.append(tank_data)
        print(f"  Tank {tank_id}: {tank_data['name']} - {tank_data['volume']} gallons")
        tank_id += 1

    if skipped_tanks:
        print(f"\nSkipped {len(skipped_tanks)} tanks without measurements:")
        for skip in skipped_tanks:
            print(f"  - Row {skip}")

    # Save tanks to temporary JSON file with correct format
    temp_json = Path("temp_tanks.json")
    config = {"tanks": tanks}
    with open(temp_json, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\nProcessing through HUD calculator...")

    # Run fast_hud_processor with correct arguments
    try:
        result = subprocess.run(
            ["python", "fast_hud_processor.py", "--config", str(temp_json)],
            capture_output=True,
            text=True,
            check=True
        )
        print("HUD processing completed successfully")

        # Read HUD results (fast_hud_processor saves to fast_results.json)
        with open("fast_results.json", 'r') as f:
            hud_results = json.load(f)

        # Update Excel with HUD results
        print("\nUpdating Excel with HUD results...")

        # First, clear any previously auto-assigned values
        df['Acceptable Separation Distance Calculated '] = df['Acceptable Separation Distance Calculated '].apply(
            lambda x: '' if pd.isna(x) or 'ASDPPU: 207.20 ft, ASDBPU: 36.50 ft' in str(x) else x
        )

        # Map results back to original tank indices
        for tank, result in zip(tanks, hud_results):
            original_idx = tank['original_index']

            # Update ASD values
            if 'results' in result:
                asdppu = result['results'].get('asdppu', '')
                asdbpu = result['results'].get('asdbpu', '')

                # Update the Acceptable Separation Distance column
                if asdppu:
                    df.at[original_idx, 'Acceptable Separation Distance Calculated '] = f"ASDPPU: {asdppu} ft"
                    if asdbpu:
                        df.at[original_idx, 'Acceptable Separation Distance Calculated '] += f", ASDBPU: {asdbpu} ft"

                    # Also store the actual volume used
                    df.at[original_idx, 'Tank Capacity'] = result.get('volume', '')

                    print(f"  Updated {result['name']}: ASDPPU={asdppu}, ASDBPU={asdbpu}")

        # Save updated Excel file
        output_path = excel_path.replace('.xlsx', '_with_hud.xlsx')
        df.to_excel(output_path, index=False)
        print(f"\nSaved updated Excel to: {output_path}")

        # Also update the original file
        df.to_excel(excel_path, index=False)
        print(f"Updated original file: {excel_path}")

        # Clean up temp files
        temp_json.unlink()
        if Path("fast_results.json").exists():
            Path("fast_results.json").unlink()

        return output_path

    except subprocess.CalledProcessError as e:
        print(f"Error running HUD processor: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    excel_file = "tank_locations_20250904_005354.xlsx"
    process_excel_through_hud(excel_file)