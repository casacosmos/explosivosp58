#!/usr/bin/env python3
"""
Create Excel file from KMZ data with proper compliance format
"""

import asyncio
import pandas as pd
from pathlib import Path
from server import TankComplianceTools

async def create_compliance_excel(
    kmz_path: str,
    output_path: str = "tank_compliance_formatted.xlsx",
    include_distances: bool = True
):
    """
    Create Excel file with proper compliance format from KMZ file

    Args:
        kmz_path: Path to KMZ file
        output_path: Output Excel file path
        include_distances: Whether to calculate distances to polygon
    """

    # Initialize tools
    tools = TankComplianceTools()

    print(f"Parsing KMZ file: {kmz_path}")

    # Parse KMZ file
    kmz_data = await tools.parse_kmz_file(kmz_path)

    sites = kmz_data['sites']
    polygons = kmz_data['polygons']

    print(f"Found {len(sites)} sites and {len(polygons)} polygons")

    # Create DataFrame with the required format
    excel_data = []
    for site in sites:
        row = {
            'Site Name or Business Name ': site['name'],
            'Person Contacted': '',
            'Tank Capacity': '',
            'Tank Measurements': '',
            'Dike Measurements': '',
            'Acceptable Separation Distance Calculated': '',
            'Approximate Distance to Site (approximately)': '',
            'Compliance': '',
            'Additional information ': '',
            'Latitude (NAD83)': site['latitude'],
            'Longitude (NAD83)': site['longitude'],
            'Calculated Distance to Polygon (ft)': '',
            'Tank Type': '',
            'Has Dike': ''
        }
        excel_data.append(row)

    # Calculate distances if requested
    if include_distances and polygons:
        print("Calculating distances to polygon boundary...")

        # Find main polygon (not buffer)
        main_polygon = None
        for polygon in polygons:
            if 'Buffer' not in polygon['name']:
                main_polygon = polygon
                break

        if not main_polygon and polygons:
            main_polygon = polygons[0]

        if main_polygon:
            print(f"Using polygon: {main_polygon['name']}")

            # Calculate distances
            polygon_coords = main_polygon['coordinates']
            distance_results = await tools.batch_calculate_distances(sites, polygon_coords)

            # Create distance map
            distance_map = {}
            if isinstance(distance_results, list):
                for result in distance_results:
                    if 'name' in result and 'distance_feet' in result:
                        distance_map[result['name']] = result['distance_feet']

            # Add distances to Excel data
            for row in excel_data:
                site_name = row['Site Name or Business Name ']
                if site_name in distance_map:
                    row['Calculated Distance to Polygon (ft)'] = f"{distance_map[site_name]:.1f}"

    # Create DataFrame
    df = pd.DataFrame(excel_data)

    # Sort by site name
    df = df.sort_values('Site Name or Business Name ')

    # Create Excel file with formatting
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

        number_format = workbook.add_format({
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
            0: 35,   # Site Name or Business Name
            1: 20,   # Person Contacted
            2: 15,   # Tank Capacity
            3: 20,   # Tank Measurements
            4: 20,   # Dike Measurements
            5: 25,   # Acceptable Separation Distance Calculated
            6: 25,   # Approximate Distance to Site
            7: 15,   # Compliance
            8: 30,   # Additional information
            9: 18,   # Latitude (NAD83)
            10: 18,  # Longitude (NAD83)
            11: 25,  # Calculated Distance to Polygon (ft)
            12: 15,  # Tank Type
            13: 12   # Has Dike
        }

        for col, width in column_widths.items():
            worksheet.set_column(col, col, width)

        # Write headers with formatting
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_format)

        # Apply formatting to data rows
        for row in range(1, len(df) + 1):
            for col, col_name in enumerate(df.columns):
                value = df.iloc[row-1, col]

                if col_name in ['Latitude (NAD83)', 'Longitude (NAD83)']:
                    worksheet.write(row, col, value, coord_format)
                elif col_name == 'Calculated Distance to Polygon (ft)' and value != '':
                    try:
                        worksheet.write(row, col, float(value), number_format)
                    except:
                        worksheet.write(row, col, value, general_format)
                else:
                    worksheet.write(row, col, value, general_format)

        # Add conditional formatting for compliance column
        compliance_col = df.columns.get_loc('Compliance')
        worksheet.conditional_format(1, compliance_col, len(df), compliance_col, {
            'type': 'text',
            'criteria': 'containing',
            'value': 'Pass',
            'format': workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1})
        })

        worksheet.conditional_format(1, compliance_col, len(df), compliance_col, {
            'type': 'text',
            'criteria': 'containing',
            'value': 'Fail',
            'format': workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1})
        })

        # Freeze top row
        worksheet.freeze_panes(1, 0)

    print(f"\n✅ Excel file created: {output_path}")
    print(f"   Total sites: {len(df)}")

    if include_distances and distance_map:
        distances = [float(v) for v in distance_map.values()]
        print(f"\n📏 Distance Statistics:")
        print(f"   Minimum: {min(distances):.1f} ft")
        print(f"   Maximum: {max(distances):.1f} ft")
        print(f"   Average: {sum(distances)/len(distances):.1f} ft")

    print("\n📝 Columns in Excel file:")
    for col in df.columns:
        print(f"   • {col}")

    return output_path

async def main():
    kmz_path = "/home/avapc/Appspc/explosivos/pipeline_isolated/JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"
    output_path = "tank_compliance_formatted.xlsx"

    await create_compliance_excel(kmz_path, output_path, include_distances=True)

if __name__ == "__main__":
    asyncio.run(main())