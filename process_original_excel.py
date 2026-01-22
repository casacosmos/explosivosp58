#!/usr/bin/env python3
"""
Process original Excel file through HUD calculator
Handles multiple tanks per row (separated by ;) and existing capacity values
"""

import pandas as pd
import json
import subprocess
from pathlib import Path
import tempfile
import re
import numpy as np

def parse_tank_measurements(measurement_str):
    """Parse tank measurements to extract volume for a single tank"""
    if pd.isna(measurement_str) or measurement_str == '':
        return None

    # Remove spaces but keep quotes for parsing
    measurement_str = str(measurement_str).replace(' ', '')

    # Handle malformed measurements like "36"x34"75"" -> likely meant "36"x34"x75""
    # Pattern: number" followed directly by another number (missing x)
    measurement_str = re.sub(r'(\d+)"(\d+)"', r'\1"x\2"', measurement_str)

    # Try to find dimensions pattern
    if 'x' in measurement_str.lower():
        parts = measurement_str.lower().split('x')
        if len(parts) >= 2:
            try:
                # Extract numeric values in inches
                dims = []
                for part in parts:
                    # Look for inches notation (number followed by ")
                    inches_match = re.search(r'(\d+)"', part)
                    if inches_match:
                        inches = float(inches_match.group(1))
                        dims.append(inches)
                    else:
                        # If no quotes, try to extract plain number (assume inches)
                        plain_match = re.search(r'(\d+\.?\d*)', part)
                        if plain_match:
                            dims.append(float(plain_match.group(1)))

                if len(dims) == 2:
                    # Cylindrical tank (diameter x height)
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
            except Exception as e:
                print(f"    Error parsing dimensions: {e}")
                pass

    return None

def extract_tank_capacity(capacity_str):
    """Extract numeric capacity from string like '964 gal' """
    if pd.isna(capacity_str) or capacity_str == '':
        return None

    # Extract numeric value from string
    capacity_str = str(capacity_str)
    match = re.search(r'(\d+\.?\d*)', capacity_str)
    if match:
        return float(match.group(1))
    return None

def process_tank_row(row, row_idx):
    """Process a single row, potentially containing multiple tanks"""
    tanks = []

    # Check if there's existing capacity
    existing_capacity = extract_tank_capacity(row['Tank Capacity'])

    # Check if there are measurements
    measurements = row['Tank Measurements']

    # If no capacity and no measurements, skip
    if existing_capacity is None and (pd.isna(measurements) or str(measurements).strip() == ''):
        return tanks

    # If there's existing capacity and no measurements, use it
    if existing_capacity is not None and (pd.isna(measurements) or str(measurements).strip() == ''):
        tanks.append({
            'capacity': existing_capacity,
            'source': 'existing',
            'measurement': None
        })
        return tanks

    # If there are measurements, parse them
    if pd.notna(measurements) and str(measurements).strip() != '':
        # Check for multiple tanks separated by semicolon
        if ';' in str(measurements):
            tank_measurements = str(measurements).split(';')
            for i, measurement in enumerate(tank_measurements):
                volume = parse_tank_measurements(measurement.strip())
                if volume:
                    tanks.append({
                        'capacity': volume,
                        'source': 'calculated',
                        'measurement': measurement.strip(),
                        'tank_number': i + 1
                    })
        else:
            # Single tank
            volume = parse_tank_measurements(measurements)
            if volume:
                tanks.append({
                    'capacity': volume,
                    'source': 'calculated',
                    'measurement': measurements
                })
            elif existing_capacity:
                # If we couldn't calculate but have existing capacity, use it
                tanks.append({
                    'capacity': existing_capacity,
                    'source': 'existing',
                    'measurement': measurements
                })

    return tanks

def process_excel_through_hud(excel_path):
    """Process original Excel file through HUD calculator"""

    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"Processing {len(df)} rows from original Excel file")
    print("="*80)

    # Prepare tank data for HUD processing
    all_tanks = []
    skipped_rows = []
    tank_id = 1

    for idx, row in df.iterrows():
        tank_name = str(row['Site Name or Business Name ']) if pd.notna(row['Site Name or Business Name ']) else f"Tank_{idx+1}"

        # Process this row (may contain multiple tanks)
        row_tanks = process_tank_row(row, idx)

        if not row_tanks:
            skipped_rows.append(f"{idx+1}: {tank_name} (no data)")
            continue

        # Add each tank from this row
        for tank_info in row_tanks:
            tank_data = {
                "id": tank_id,
                "name": tank_name if len(row_tanks) == 1 else f"{tank_name} - Tank {tank_info.get('tank_number', '')}",
                "latitude": row['Latitude (NAD83)'],
                "longitude": row['Longitude (NAD83)'],
                "volume": tank_info['capacity'],
                "is_underground": False,
                "has_dike": pd.notna(row['Dike Measurements']) and str(row['Dike Measurements']).strip() != '',
                "original_index": idx,
                "source": tank_info['source']
            }
            all_tanks.append(tank_data)

            source_text = f"[{tank_info['source']}]"
            measurement_text = f"({tank_info['measurement']})" if tank_info.get('measurement') else ""
            print(f"  Tank {tank_id}: {tank_data['name']} - {tank_data['volume']:.0f} gallons {source_text} {measurement_text}")
            tank_id += 1

    if skipped_rows:
        print(f"\nSkipped {len(skipped_rows)} rows without data:")
        for skip in skipped_rows:
            print(f"  - Row {skip}")

    if not all_tanks:
        print("No tanks to process!")
        return None

    # Save tanks to temporary JSON file with correct format
    temp_json = Path("temp_tanks.json")
    config = {"tanks": all_tanks}
    with open(temp_json, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\nProcessing {len(all_tanks)} tanks through HUD calculator...")

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

        # Clear any existing ASD values
        df['Acceptable Separation Distance Calculated '] = ''

        # Clear Tank Capacity column to refill with correct values
        df['Tank Capacity'] = np.nan

        # Map results back to original rows
        for tank, result in zip(all_tanks, hud_results):
            original_idx = tank['original_index']

            # Update ASD values
            if 'results' in result:
                asdppu = result['results'].get('asdppu', '')
                asdbpu = result['results'].get('asdbpu', '')

                # Update the Acceptable Separation Distance column
                if asdppu:
                    current_asd = df.at[original_idx, 'Acceptable Separation Distance Calculated ']
                    if current_asd and current_asd != '':
                        # Multiple tanks in this row, append
                        df.at[original_idx, 'Acceptable Separation Distance Calculated '] += f"; ASDPPU: {asdppu} ft, ASDBPU: {asdbpu} ft"
                    else:
                        df.at[original_idx, 'Acceptable Separation Distance Calculated '] = f"ASDPPU: {asdppu} ft"
                        if asdbpu:
                            df.at[original_idx, 'Acceptable Separation Distance Calculated '] += f", ASDBPU: {asdbpu} ft"

                    # Store volume (handling multiple tanks per row)
                    current_capacity = df.at[original_idx, 'Tank Capacity']
                    if pd.isna(current_capacity):
                        df.at[original_idx, 'Tank Capacity'] = f"{result.get('volume', '')} gal"
                    else:
                        df.at[original_idx, 'Tank Capacity'] += f"; {result.get('volume', '')} gal"

                    print(f"  Updated {result['name']}: ASDPPU={asdppu}, ASDBPU={asdbpu}")

        # Save updated Excel file
        output_path = excel_path.replace('.xlsx', '_processed.xlsx')
        df.to_excel(output_path, index=False)
        print(f"\nSaved processed Excel to: {output_path}")

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
    excel_file = "tank_locations_20250904_005354 (1).xlsx"
    process_excel_through_hud(excel_file)