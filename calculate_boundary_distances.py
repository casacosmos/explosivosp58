#!/usr/bin/env python3
"""
Calculate distances from tank locations to polygon boundary and check ASD compliance
Uses proper coordinate system transformations for accurate distance measurements
"""

import pandas as pd
import numpy as np
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import re
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import pyproj
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import transform

def parse_polygon_from_kmz(kmz_path):
    """Parse KMZ file and extract polygon boundaries"""
    polygons = []

    try:
        # KMZ is a zipped KML file
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            # Find the KML file inside
            kml_file = None
            for file_name in kmz.namelist():
                if file_name.endswith('.kml'):
                    kml_file = file_name
                    break

            if not kml_file:
                print("No KML file found in KMZ")
                return polygons

            # Read and parse the KML
            with kmz.open(kml_file) as kml:
                content = kml.read().decode('utf-8')

                # Try to parse with different namespace approaches
                # Remove namespace declarations for simpler parsing
                content = re.sub(r'xmlns[^=]*="[^"]*"', '', content)
                content = re.sub(r'<kml[^>]*>', '<kml>', content)

                root = ET.fromstring(content)

                # Find all Polygon elements
                for polygon_elem in root.iter('Polygon'):
                    # Get outer boundary coordinates
                    for outer in polygon_elem.iter('outerBoundaryIs'):
                        for coords_elem in outer.iter('coordinates'):
                            if coords_elem.text:
                                coords_text = coords_elem.text.strip()
                                coordinates = []

                                # Parse coordinates (format: lon,lat,alt lon,lat,alt ...)
                                for coord_set in coords_text.split():
                                    parts = coord_set.split(',')
                                    if len(parts) >= 2:
                                        lon = float(parts[0])
                                        lat = float(parts[1])
                                        coordinates.append((lon, lat))

                                if len(coordinates) >= 3:  # Valid polygon needs at least 3 points
                                    polygons.append(coordinates)
                                    print(f"Found polygon with {len(coordinates)} vertices")

    except Exception as e:
        print(f"Error parsing KMZ: {e}")
        # Try alternative: look for a simple text file with polygon coordinates
        try:
            # Check if there's a polygon file in the output directory
            polygon_files = list(Path('.').glob('**/polygon_*.txt'))
            if polygon_files:
                print(f"Found polygon file: {polygon_files[0]}")
                with open(polygon_files[0], 'r') as f:
                    coords = []
                    for line in f:
                        if ',' in line:
                            parts = line.strip().split(',')
                            if len(parts) >= 2:
                                lon = float(parts[0])
                                lat = float(parts[1])
                                coords.append((lon, lat))
                    if coords:
                        polygons.append(coords)
                        print(f"Loaded polygon with {len(coords)} vertices from text file")
        except Exception as e2:
            print(f"Could not load alternative polygon file: {e2}")

    return polygons

def calculate_distance_to_polygon(point_lat, point_lon, polygon_coords, use_projection=True):
    """
    Calculate minimum distance from a point to polygon boundary

    Args:
        point_lat: Latitude of the point
        point_lon: Longitude of the point
        polygon_coords: List of (lon, lat) tuples defining the polygon
        use_projection: If True, use projected coordinates for accuracy

    Returns:
        Dictionary with distance info
    """

    if use_projection:
        # Use UTM Zone 19N which covers Puerto Rico (EPSG:32619)
        # This gives more accurate distance measurements for Puerto Rico
        transformer = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32619', always_xy=True)

        # Transform point to projected coordinates
        point_x, point_y = transformer.transform(point_lon, point_lat)
        tank_point = Point(point_x, point_y)

        # Transform polygon to projected coordinates
        poly_x = []
        poly_y = []
        for lon, lat in polygon_coords:
            x, y = transformer.transform(lon, lat)
            poly_x.append(x)
            poly_y.append(y)

        # Create polygon in projected coordinates
        polygon = Polygon(zip(poly_x, poly_y))

        # Calculate distance to boundary (exterior ring)
        boundary = polygon.exterior
        distance_meters = tank_point.distance(boundary)

        # Find the closest point on the boundary
        closest_point = boundary.interpolate(boundary.project(tank_point))
        closest_x, closest_y = closest_point.x, closest_point.y

        # Transform back to lat/lon for reporting
        transformer_back = pyproj.Transformer.from_crs('EPSG:32619', 'EPSG:4326', always_xy=True)
        closest_lon, closest_lat = transformer_back.transform(closest_x, closest_y)

        # Convert to feet
        distance_feet = distance_meters * 3.28084

        # Check if point is inside or outside polygon
        is_inside = polygon.contains(tank_point)

    else:
        # Fallback: Simple haversine distance (less accurate but doesn't need pyproj)
        tank_point = Point(point_lon, point_lat)
        polygon = Polygon(polygon_coords)

        # Find closest point on boundary
        boundary = polygon.exterior
        min_distance = float('inf')
        closest_point = None

        # Check each segment of the polygon
        coords_list = list(polygon_coords)
        for i in range(len(coords_list)):
            p1 = coords_list[i]
            p2 = coords_list[(i + 1) % len(coords_list)]

            # Create line segment
            segment = LineString([p1, p2])

            # Project point onto segment
            projected = segment.interpolate(segment.project(tank_point))

            # Calculate distance
            dist = haversine_distance(point_lat, point_lon, projected.y, projected.x)

            if dist < min_distance:
                min_distance = dist
                closest_point = (projected.x, projected.y)

        distance_feet = min_distance
        closest_lon, closest_lat = closest_point if closest_point else (None, None)
        is_inside = polygon.contains(tank_point)

    return {
        'distance_feet': distance_feet,
        'distance_meters': distance_feet / 3.28084,
        'closest_point_lat': closest_lat,
        'closest_point_lon': closest_lon,
        'is_inside': is_inside
    }

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points in feet
    """
    # Radius of earth in feet
    R = 20925721.784

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c

def extract_asd_values(asd_string):
    """Extract ASDPPU and ASDBPU values from the ASD string"""
    if pd.isna(asd_string) or asd_string == '':
        return None, None

    asd_string = str(asd_string)
    asdppu = None
    asdbpu = None

    # Look for ASDPPU value
    asdppu_match = re.search(r'ASDPPU:\s*([\d.]+)', asd_string)
    if asdppu_match:
        asdppu = float(asdppu_match.group(1))

    # Look for ASDBPU value
    asdbpu_match = re.search(r'ASDBPU:\s*([\d.]+)', asd_string)
    if asdbpu_match:
        asdbpu = float(asdbpu_match.group(1))

    return asdppu, asdbpu

def check_compliance(distance_feet, asdppu, asdbpu, has_dike):
    """
    Check if tank is in compliance based on distance and ASD values
    """
    if asdppu is None:
        return "No ASD Data", None

    # Use ASDBPU if tank has dike, otherwise use ASDPPU
    required_distance = asdbpu if (has_dike and asdbpu is not None) else asdppu

    if required_distance is None:
        return "No ASD Data", None

    margin = distance_feet - required_distance

    if distance_feet >= required_distance:
        return "COMPLIANT", margin
    else:
        return "NON-COMPLIANT", margin

def process_compliance_check(excel_path, kmz_path):
    """Main function to process compliance checking"""

    print("="*80)
    print("TANK COMPLIANCE ASSESSMENT")
    print("Distance from Polygon Boundary to Tank Locations")
    print("="*80)

    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"\nLoaded {len(df)} tanks from Excel")

    # Parse polygon from KMZ
    polygons = parse_polygon_from_kmz(kmz_path)

    if not polygons:
        print("\n⚠️  WARNING: No polygon boundary found in KMZ file")
        print("Cannot calculate distances without boundary data")
        return None

    # Use the first polygon (assuming single boundary)
    polygon_coords = polygons[0]
    print(f"\nUsing polygon boundary with {len(polygon_coords)} vertices")

    # Try to use pyproj for accurate measurements
    use_projection = True
    try:
        import pyproj
        print("Using projected coordinate system for accurate distance measurements")
    except ImportError:
        print("pyproj not available, using haversine formula (less accurate)")
        use_projection = False

    # Process each tank
    print("\n" + "="*80)
    print("COMPLIANCE ASSESSMENT RESULTS")
    print("="*80)

    results = []

    for idx, row in df.iterrows():
        site_name = row['Site Name or Business Name']
        lat = row.get('Latitude (NAD83)', None)
        lon = row.get('Longitude (NAD83)', None)
        asd_string = row.get('Acceptable Separation Distance Calculated', '')
        has_dike = row.get('Has Dike', False)

        # Skip if no coordinates
        if pd.isna(lat) or pd.isna(lon):
            print(f"\n{idx+1}. {site_name}")
            print("   ⚠️  No coordinates - cannot calculate distance")
            continue

        # Calculate distance to boundary
        dist_info = calculate_distance_to_polygon(lat, lon, polygon_coords, use_projection)

        # Extract ASD values
        asdppu, asdbpu = extract_asd_values(asd_string)

        # Check compliance
        compliance, margin = check_compliance(
            dist_info['distance_feet'],
            asdppu,
            asdbpu,
            has_dike
        )

        # Store results
        result = {
            'Site': site_name,
            'Distance_to_Boundary_ft': dist_info['distance_feet'],
            'ASDPPU_ft': asdppu,
            'ASDBPU_ft': asdbpu,
            'Required_Distance_ft': asdbpu if (has_dike and asdbpu) else asdppu,
            'Has_Dike': has_dike,
            'Margin_ft': margin,
            'Compliance': compliance,
            'Tank_Lat': lat,
            'Tank_Lon': lon,
            'Closest_Boundary_Lat': dist_info['closest_point_lat'],
            'Closest_Boundary_Lon': dist_info['closest_point_lon'],
            'Inside_Polygon': dist_info['is_inside']
        }
        results.append(result)

        # Print result
        print(f"\n{idx+1}. {site_name}")
        print(f"   Location: {lat:.7f}, {lon:.7f}")
        print(f"   Distance to boundary: {dist_info['distance_feet']:.2f} ft")

        if asdppu:
            print(f"   Required distance: {result['Required_Distance_ft']:.2f} ft")
            print(f"   {'Has dike: Yes (using ASDBPU)' if (has_dike and asdbpu) else 'No dike (using ASDPPU)'}")

            if compliance == "COMPLIANT":
                print(f"   ✅ COMPLIANT (margin: +{margin:.2f} ft)")
            elif compliance == "NON-COMPLIANT":
                print(f"   ❌ NON-COMPLIANT (deficit: {margin:.2f} ft)")
        else:
            print(f"   ⚠️  No ASD data available")

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Save results
    output_path = excel_path.replace('.xlsx', '_compliance_assessment.xlsx')
    results_df.to_excel(output_path, index=False)

    # Summary
    print("\n" + "="*80)
    print("COMPLIANCE SUMMARY")
    print("="*80)

    if results_df.empty:
        print("No tanks could be assessed")
    else:
        compliant = len(results_df[results_df['Compliance'] == 'COMPLIANT'])
        non_compliant = len(results_df[results_df['Compliance'] == 'NON-COMPLIANT'])
        no_data = len(results_df[results_df['Compliance'] == 'No ASD Data'])

        print(f"Total tanks assessed: {len(results_df)}")
        print(f"  ✅ Compliant: {compliant}")
        print(f"  ❌ Non-compliant: {non_compliant}")
        print(f"  ⚠️  No ASD data: {no_data}")

        print(f"\nResults saved to: {output_path}")

    return results_df

if __name__ == "__main__":
    # Check for required libraries
    try:
        import pyproj
        print("✓ pyproj available for accurate distance calculations")
    except ImportError:
        print("⚠️  Installing pyproj for accurate distance calculations...")
        import subprocess
        subprocess.run(["pip", "install", "pyproj", "shapely"], check=False)

    excel_file = "tank_locations_FINAL.xlsx"
    kmz_file = "JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"

    process_compliance_check(excel_file, kmz_file)