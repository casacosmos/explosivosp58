#!/usr/bin/env python3
"""
Calculate distances from points to Cataño polygon boundary.
This script reads coordinates from an Excel file and calculates the distance
from each point to the nearest point on a polygon boundary extracted from a KMZ file.
"""

import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import pyproj
import argparse
import sys
from pathlib import Path


def load_polygon_from_file(polygon_file):
    """Load polygon coordinates from a text file."""
    polygon_coords = []
    with open(polygon_file, 'r') as f:
        for line in f:
            if line.strip():
                lon, lat = map(float, line.strip().split(','))
                polygon_coords.append((lon, lat))
    
    if len(polygon_coords) < 3:
        raise ValueError(f"Insufficient coordinates for a polygon: {len(polygon_coords)} points found")
    
    return polygon_coords


def calculate_distances_to_polygon(excel_path, polygon_coords, output_path=None):
    """
    Calculate distances from points in Excel to polygon boundary.
    
    Args:
        excel_path: Path to input Excel file with point coordinates
        polygon_coords: List of (lon, lat) tuples defining the polygon
        output_path: Optional output path for the updated Excel file
    
    Returns:
        DataFrame with calculated distances and statistics dictionary
    """
    # Create polygon
    polygon = Polygon(polygon_coords)
    if not polygon.is_valid:
        print("Warning: Polygon is invalid, attempting to fix...")
        polygon = polygon.buffer(0)  # Common fix for self-intersecting polygons
    
    print(f"Polygon loaded with {len(polygon_coords)} vertices")
    print(f"Polygon area: {polygon.area:.8f} square degrees")
    
    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"\nLoaded Excel file with {len(df)} rows")
    
    # Set up coordinate transformation for accurate distance calculation
    # Use UTM zone 19N for Puerto Rico
    utm_pr = pyproj.CRS('EPSG:32619')  # WGS84 / UTM zone 19N
    wgs84 = pyproj.CRS('EPSG:4326')  # WGS84 (lat/lon)
    
    # Create transformers
    transformer_to_utm = pyproj.Transformer.from_crs(wgs84, utm_pr, always_xy=True)
    transformer_from_utm = pyproj.Transformer.from_crs(utm_pr, wgs84, always_xy=True)
    
    # Transform polygon to UTM for accurate distance calculation
    polygon_utm = transform(transformer_to_utm.transform, polygon)
    print(f"Polygon in UTM - Area: {polygon_utm.area:.2f} square meters ({polygon_utm.area * 10.764:.2f} square feet)")
    
    # Calculate distances for each point
    results = []
    
    print("\n" + "="*80)
    print("DISTANCE CALCULATIONS")
    print("="*80)
    
    for idx, row in df.iterrows():
        try:
            # Look for latitude and longitude columns
            lat_col = None
            lon_col = None
            # Prefer canonical NAD83 columns when present
            preferred_lat = ['Latitude (NAD83)', 'Latitude']
            preferred_lon = ['Longitude (NAD83)', 'Longitude']
            lat_col = next((c for c in preferred_lat if c in df.columns), None)
            lon_col = next((c for c in preferred_lon if c in df.columns), None)
            # Fallback: pick the first column containing 'lat'/'lon' that is not a derived field like 'Closest Point Lat/Lon'
            if not lat_col:
                for col in df.columns:
                    lc = col.lower()
                    if 'lat' in lc and 'closest' not in lc:
                        lat_col = col
                        break
            if not lon_col:
                for col in df.columns:
                    lc = col.lower()
                    if 'lon' in lc and 'closest' not in lc:
                        lon_col = col
                        break
            
            if not lat_col or not lon_col:
                raise ValueError("Could not find latitude and longitude columns")
            
            lat = row[lat_col]
            lon = row[lon_col]
            
            # Get site name (first column or column with 'name' in it)
            site_name = row[df.columns[0]]
            for col in df.columns:
                if 'name' in col.lower():
                    site_name = row[col]
                    break
            
            # Skip if coordinates are invalid
            if pd.isna(lat) or pd.isna(lon):
                print(f"{idx+1:3}. {str(site_name)[:45]:45} - No coordinates available")
                results.append({
                    'Calculated Distance to Polygon (ft)': np.nan,
                    'Closest Point Lat': np.nan,
                    'Closest Point Lon': np.nan,
                    'Point Location': np.nan
                })
                continue
            
            # Create point and transform to UTM
            point = Point(lon, lat)
            point_utm = transform(transformer_to_utm.transform, point)
            
            # Check if point is inside or outside polygon
            is_inside = polygon_utm.contains(point_utm)
            
            # Calculate distance to boundary
            distance_meters = point_utm.distance(polygon_utm.exterior)
            distance_feet = distance_meters * 3.28084  # Convert meters to feet
            
            # Find closest point on boundary
            closest_point_utm = polygon_utm.exterior.interpolate(polygon_utm.exterior.project(point_utm))
            
            # Transform closest point back to lat/lon
            closest_lon, closest_lat = transformer_from_utm.transform(closest_point_utm.x, closest_point_utm.y)
            
            results.append({
                'Calculated Distance to Polygon (ft)': distance_feet,
                'Closest Point Lat': closest_lat,
                'Closest Point Lon': closest_lon,
                'Point Location': 'Inside Polygon' if is_inside else 'Outside Polygon'
            })
            
            location_str = "INSIDE" if is_inside else "OUTSIDE"
            print(f"{idx+1:3}. {str(site_name)[:45]:45} - {distance_feet:8.2f} ft ({location_str})")
            
        except Exception as e:
            print(f"{idx+1:3}. Error processing row: {e}")
            results.append({
                'Calculated Distance to Polygon (ft)': np.nan,
                'Closest Point Lat': np.nan,
                'Closest Point Lon': np.nan,
                'Point Location': np.nan
            })
    
    # Add results to dataframe
    for col, values in zip(results[0].keys(), zip(*[r.values() for r in results])):
        df[col] = values
    
    # Also backfill Approximate Distance to Site if present in sheet or expected by downstream
    df['Approximate Distance to Site (appoximately) '] = df['Calculated Distance to Polygon (ft)']
    
    # Save updated Excel file
    if output_path:
        df.to_excel(output_path, index=False)
        print(f"\n✓ Results saved to: {output_path}")
    
    # Calculate statistics
    valid_distances = pd.Series([r.get('Calculated Distance to Polygon (ft)') for r in results]).dropna()
    inside_count = sum(1 for r in results if str(r.get('Point Location', '')).lower().startswith('inside'))
    outside_count = sum(1 for r in results if str(r.get('Point Location', '')).lower().startswith('outside'))
    
    stats = {
        'total_points': len(df),
        'valid_points': len(valid_distances),
        'invalid_points': len(df) - len(valid_distances),
        'inside_polygon': inside_count,
        'outside_polygon': outside_count,
        'min_distance': valid_distances.min() if len(valid_distances) > 0 else np.nan,
        'max_distance': valid_distances.max() if len(valid_distances) > 0 else np.nan,
        'mean_distance': valid_distances.mean() if len(valid_distances) > 0 else np.nan,
        'median_distance': valid_distances.median() if len(valid_distances) > 0 else np.nan
    }
    
    return df, stats


def print_statistics(stats):
    """Print summary statistics."""
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total points in Excel file: {stats['total_points']}")
    print(f"Points with valid coordinates: {stats['valid_points']}")
    print(f"Points without coordinates: {stats['invalid_points']}")
    print(f"\nLocation relative to polygon:")
    print(f"  - Inside polygon: {stats['inside_polygon']}")
    print(f"  - Outside polygon: {stats['outside_polygon']}")
    
    if not np.isnan(stats['min_distance']):
        print(f"\nDistance to boundary statistics:")
        print(f"  - Minimum distance: {stats['min_distance']:.2f} ft")
        print(f"  - Maximum distance: {stats['max_distance']:.2f} ft")
        print(f"  - Average distance: {stats['mean_distance']:.2f} ft")
        print(f"  - Median distance: {stats['median_distance']:.2f} ft")


def main():
    parser = argparse.ArgumentParser(
        description='Calculate distances from points to polygon boundary'
    )
    parser.add_argument(
        'excel_file',
        help='Input Excel file with point coordinates'
    )
    parser.add_argument(
        'polygon_file',
        help='Text file with polygon coordinates (lon,lat format)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output Excel file path (default: adds _with_distances to input filename)',
        default=None
    )
    
    args = parser.parse_args()
    
    # Validate input files
    excel_path = Path(args.excel_file)
    polygon_path = Path(args.polygon_file)
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        sys.exit(1)
    
    if not polygon_path.exists():
        print(f"Error: Polygon file not found: {polygon_path}")
        sys.exit(1)
    
    # Set output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = excel_path.parent / f"{excel_path.stem}_with_distances.xlsx"
    
    try:
        # Load polygon coordinates
        polygon_coords = load_polygon_from_file(polygon_path)
        
        # Calculate distances
        df, stats = calculate_distances_to_polygon(
            excel_path,
            polygon_coords,
            output_path
        )
        
        # Print statistics
        print_statistics(stats)
        
        print("\n✓ Distance calculation completed successfully!")
        
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
