#!/usr/bin/env python3
"""
Parse KMZ file and create Excel with distance calculations
"""

import asyncio
import json
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any
from server import TankComplianceTools

async def main():
    # Initialize tools
    tools = TankComplianceTools()

    # KMZ file path
    kmz_path = "/home/avapc/Appspc/explosivos/pipeline_isolated/JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"

    print(f"Parsing KMZ file: {kmz_path}")

    # Parse KMZ file
    kmz_data = await tools.parse_kmz_file(kmz_path)

    print(f"Found {kmz_data['count']} sites")
    print(f"Found {len(kmz_data['polygons'])} polygons")

    # Extract sites and polygons
    sites = kmz_data['sites']
    polygons = kmz_data['polygons']

    # Find the main polygon (not the buffer)
    main_polygon = None
    for polygon in polygons:
        if 'CRC' in polygon['name'] or 'USAR' in polygon['name']:
            main_polygon = polygon
            break

    if not main_polygon:
        # Use the first non-buffer polygon
        for polygon in polygons:
            if 'Buffer' not in polygon['name']:
                main_polygon = polygon
                break

    if not main_polygon and polygons:
        main_polygon = polygons[0]

    print(f"Using polygon: {main_polygon['name'] if main_polygon else 'None found'}")

    # Calculate distances if we have a polygon
    if main_polygon:
        print("Calculating distances to polygon boundary...")

        # Convert polygon coordinates for the calculation
        # The polygon coordinates are already in (lon, lat) format from KMZ
        polygon_coords = main_polygon['coordinates']

        # Calculate distances for all sites
        distance_results = await tools.batch_calculate_distances(sites, polygon_coords)

        # Parse the distance results
        distances = {}
        print(f"Distance results: {distance_results}")

        if isinstance(distance_results, dict) and 'results' in distance_results:
            for site_result in distance_results['results']:
                distances[site_result['name']] = site_result.get('distance_feet', site_result.get('distance'))
        elif isinstance(distance_results, list):
            for site_result in distance_results:
                if isinstance(site_result, dict):
                    distances[site_result['name']] = site_result.get('distance_feet', site_result.get('distance'))
    else:
        distances = {}

    # Create DataFrame for Excel
    excel_data = []
    for site in sites:
        row = {
            'Site Name': site['name'],
            'Latitude': site['latitude'],
            'Longitude': site['longitude'],
            'Distance to Boundary (ft)': distances.get(site['name'], 'N/A'),
            'Tank Capacity': '',  # To be filled manually
            'Tank Measurements': '',  # To be filled manually
            'Underground (Y/N)': '',  # To be filled manually
            'Has Dike (Y/N)': '',  # To be filled manually
            'ASDPPU (ft)': '',  # To be calculated
            'ASDBPU (ft)': '',  # To be calculated
            'Compliance Status': '',  # To be determined
            'Notes': ''
        }
        excel_data.append(row)

    # Create DataFrame
    df = pd.DataFrame(excel_data)

    # Sort by site name
    df = df.sort_values('Site Name')

    # Create Excel file with formatting
    output_path = "/home/avapc/Appspc/explosivos/pipeline_isolated/mcp_tank_compliance/tank_compliance_data.xlsx"

    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tank Compliance', index=False)

        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Tank Compliance']

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BD',
            'border': 1
        })

        distance_format = workbook.add_format({
            'num_format': '#,##0.0',
            'border': 1
        })

        coord_format = workbook.add_format({
            'num_format': '0.00000000',
            'border': 1
        })

        general_format = workbook.add_format({
            'border': 1
        })

        # Set column widths
        column_widths = {
            'A': 30,  # Site Name
            'B': 15,  # Latitude
            'C': 15,  # Longitude
            'D': 20,  # Distance
            'E': 15,  # Tank Capacity
            'F': 20,  # Tank Measurements
            'G': 15,  # Underground
            'H': 12,  # Has Dike
            'I': 12,  # ASDPPU
            'J': 12,  # ASDBPU
            'K': 18,  # Compliance Status
            'L': 30   # Notes
        }

        for col, width in column_widths.items():
            worksheet.set_column(f'{col}:{col}', width)

        # Write headers with formatting
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_format)

        # Apply number formatting to specific columns
        for row in range(1, len(df) + 1):
            for col, col_name in enumerate(df.columns):
                value = df.iloc[row-1, col]

                if col_name in ['Latitude', 'Longitude']:
                    worksheet.write(row, col, value, coord_format)
                elif col_name == 'Distance to Boundary (ft)' and isinstance(value, (int, float)):
                    worksheet.write(row, col, value, distance_format)
                else:
                    worksheet.write(row, col, value, general_format)

        # Add conditional formatting for compliance status
        worksheet.conditional_format(f'K2:K{len(df)+1}', {
            'type': 'text',
            'criteria': 'containing',
            'value': 'Pass',
            'format': workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        })

        worksheet.conditional_format(f'K2:K{len(df)+1}', {
            'type': 'text',
            'criteria': 'containing',
            'value': 'Fail',
            'format': workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        })

        # Freeze top row
        worksheet.freeze_panes(1, 0)

    print(f"\nExcel file created: {output_path}")
    print(f"Total sites: {len(df)}")

    # Display summary statistics
    if distances:
        valid_distances = [d for d in distances.values() if isinstance(d, (int, float))]
        if valid_distances:
            print(f"\nDistance Statistics:")
            print(f"  Minimum: {min(valid_distances):.1f} ft")
            print(f"  Maximum: {max(valid_distances):.1f} ft")
            print(f"  Average: {sum(valid_distances)/len(valid_distances):.1f} ft")

    # Create a summary JSON file
    summary = {
        'kmz_file': kmz_path,
        'total_sites': len(sites),
        'polygon_used': main_polygon['name'] if main_polygon else 'None',
        'sites_with_distances': len(distances),
        'output_excel': output_path,
        'sites': [
            {
                'name': site['name'],
                'latitude': site['latitude'],
                'longitude': site['longitude'],
                'distance_feet': distances.get(site['name'], None)
            }
            for site in sites
        ]
    }

    summary_path = "/home/avapc/Appspc/explosivos/pipeline_isolated/mcp_tank_compliance/kmz_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Summary JSON created: {summary_path}")

    return output_path, summary

if __name__ == "__main__":
    asyncio.run(main())