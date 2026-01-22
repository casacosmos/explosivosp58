#!/usr/bin/env python3
"""
Test script for the enhanced agent
"""
import asyncio
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import TankComplianceTools

async def test_workflow():
    tools = TankComplianceTools()

    print("1. Testing KMZ parsing...")
    kmz_path = "/home/avapc/Appspc/explosivos/pipeline_isolated/JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"
    kmz_data = await tools.parse_kmz_file(kmz_path)
    print(f"   ✅ Parsed {kmz_data['count']} sites")
    print(f"   ✅ Found {len(kmz_data.get('polygons', []))} polygons")

    print("\n2. Testing distance calculation...")
    sites = kmz_data['sites'][:3]  # Test with first 3 sites
    polygons = kmz_data['polygons']

    # Find main polygon
    main_polygon = None
    for p in polygons:
        if 'Buffer' not in p['name']:
            main_polygon = p
            break

    if main_polygon:
        print(f"   Using polygon: {main_polygon['name']}")
        results = await tools.batch_calculate_distances(sites, main_polygon['coordinates'])

        for r in results:
            if 'distance_feet' in r:
                print(f"   • {r['name']}: {r['distance_feet']:.1f} ft")

    print("\n3. Creating Excel file...")
    import pandas as pd

    # Create DataFrame
    data = []
    for site in kmz_data['sites']:
        data.append({
            'Site Name': site['name'],
            'Latitude': site['latitude'],
            'Longitude': site['longitude'],
            'Tank Capacity': '',
            'Distance to Boundary (ft)': ''
        })

    df = pd.DataFrame(data)
    output_path = "test_compliance.xlsx"
    df.to_excel(output_path, index=False)
    print(f"   ✅ Excel created: {output_path}")

    print("\n4. Reading Excel file...")
    df_read = pd.read_excel(output_path)
    print(f"   ✅ Read {len(df_read)} rows")

    print("\n5. Modifying Excel...")
    df_read.loc[0, 'Tank Capacity'] = '5000'
    df_read.to_excel(output_path, index=False)
    print(f"   ✅ Modified and saved")

    print("\n✨ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_workflow())