#!/usr/bin/env python3
"""
Update Book 1 Excel with HUD results.
"""

import pandas as pd
import json
from pathlib import Path

def update_excel_with_hud(excel_path: str, hud_results_path: str, output_path: str):
    """Update Excel with HUD ASD/flood zone results."""

    print(f"📊 Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path)

    print(f"📊 Reading HUD results: {hud_results_path}")
    with open(hud_results_path, 'r') as f:
        hud_results = json.load(f)

    # Create a mapping of tank names to HUD results
    hud_map = {}
    for result in hud_results:
        # Try different ways to match tanks
        tank_name = result.get('name', '')
        tank_id = result.get('tank_id', '')

        # Store by name
        hud_map[tank_name] = result

        # Also try to extract tank ID from name for matching
        if 'TK-' in tank_name:
            tk_id = tank_name.split('TK-')[1].split(' ')[0]
            hud_map[f'TK-{tk_id}'] = result

    # Add new columns if they don't exist
    if 'ASDPPU' not in df.columns:
        df['ASDPPU'] = None
    if 'ASDBPU' not in df.columns:
        df['ASDBPU'] = None
    if 'ASDPNPD' not in df.columns:
        df['ASDPNPD'] = None
    if 'ASDBNPD' not in df.columns:
        df['ASDBNPD'] = None
    if 'Flood Zone' not in df.columns:
        df['Flood Zone'] = None
    if 'HUD Screenshot' not in df.columns:
        df['HUD Screenshot'] = None

    # Update each row with HUD results
    matched = 0
    for idx, row in df.iterrows():
        # Try to find matching HUD result
        tank_desc = str(row.get('Tank Use/Description', row.get('Tank Use', '')))
        tank_id = str(row.get('Tank ID', ''))

        # Try different matching strategies
        hud_data = None

        # Try exact match on description
        if tank_desc in hud_map:
            hud_data = hud_map[tank_desc]
        # Try tank ID match
        elif tank_id in hud_map:
            hud_data = hud_map[tank_id]
        # Try partial match
        else:
            for key, value in hud_map.items():
                if tank_id and tank_id in key:
                    hud_data = value
                    break
                elif tank_desc and any(part in key for part in tank_desc.split()[:3]):
                    hud_data = value
                    break

        # Update row with HUD data
        if hud_data:
            results = hud_data.get('results', {})
            df.at[idx, 'ASDPPU'] = results.get('asdppu', '')
            df.at[idx, 'ASDBPU'] = results.get('asdbpu', '')
            df.at[idx, 'ASDPNPD'] = results.get('asdpnpd', '')
            df.at[idx, 'ASDBNPD'] = results.get('asdbnpd', '')
            df.at[idx, 'HUD Screenshot'] = hud_data.get('screenshot', '')
            matched += 1
            print(f"  ✓ Matched: {tank_id or tank_desc[:30]} → ASDPPU={results.get('asdppu')}")

    # Save updated Excel
    df.to_excel(output_path, index=False)

    print(f"\n✅ Updated {matched}/{len(df)} tanks with HUD results")
    print(f"💾 Saved to: {output_path}")

    # Show sample of updated data
    print("\n📋 Sample of updated data:")
    print(df[['Tank ID', 'Tank Use/Description', 'Capacity (gallons)', 'ASDPPU', 'ASDBPU']].head())

    return df

if __name__ == "__main__":
    # Update Book 1 Excel with HUD results
    df = update_excel_with_hud(
        excel_path="book1_with_coordinates.xlsx",
        hud_results_path="fast_results.json",
        output_path="book1_with_hud_results.xlsx"
    )

    print("\n✨ Excel updated with HUD data!")