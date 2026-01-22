#!/usr/bin/env python3
"""
Smart Tank Analysis & Organization Tool
1. Parses KMZ/KML.
2. Intelligently separates Tanks from Site Boundaries/Points/Buffers.
3. Calculates accurate distances from Tanks to Site Boundary.
4. Generates a clean Excel report.
5. Produces a structured, organized Master KMZ.
"""

import os
import zipfile
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import xml.etree.ElementTree as ET

import pandas as pd
from shapely.geometry import Point, Polygon, LineString, shape
from shapely.ops import transform
from pyproj import Transformer

# ============================================================================ 
# UTILITIES
# ============================================================================ 

def safe_title_case(text: str) -> str:
    """Intelligently title case text (keeping acronyms like 'USA' if needed)."""
    if not text:
        return ""
    # Simple title case for now, can be enhanced
    return text.strip().title()

def is_tank_name(name: str) -> bool:
    """Heuristic to determine if a point is likely a tank/site."""
    name_lower = name.lower()
    exclusions = [
        'site point', 'project point', 'center', 'centroid',
        'buffer', 'boundary', 'polygon', 'area', 'zone',
        'site boundary', 'reference'
    ]
    return not any(ex in name_lower for ex in exclusions)

def get_distance_ft(point: Point, polygon: Polygon) -> float:
    """Calculate minimum distance from point to polygon in feet using PR State Plane."""
    # Transformers
    # EPSG:32161 is NAD83 / Puerto Rico & Virgin Islands (meters) - High accuracy for PR
    to_local = Transformer.from_crs("EPSG:4326", "EPSG:32161", always_xy=True)
    
    # Project to local CRS (meters)
    p_local = transform(to_local.transform, point)
    poly_local = transform(to_local.transform, polygon)
    
    # Calculate distance (meters)
    dist_m = poly_local.distance(p_local)
    
    # Convert to feet
    return dist_m * 3.28084

# ============================================================================ 
# PARSING
# ============================================================================ 

def parse_kmz(file_path: str) -> Dict[str, Any]:
    """Extract features from KMZ."""
    features = {
        'points': [],
        'polygons': [],
        'lines': []
    }
    
    try:
        with zipfile.ZipFile(file_path, 'r') as kmz:
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
            if not kml_files:
                return features
            
            with kmz.open(kml_files[0], 'r') as kml:
                tree = ET.parse(kml)
                root = tree.getroot()
                
                # Namespaces
                ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                # Try to handle common KML namespaces
                if root.tag.endswith('}kml'):
                    ns_url = root.tag.split('}')[0].strip('{')
                    ns = {'kml': ns_url}
                
                for placemark in root.findall('.//kml:Placemark', ns):
                    name = placemark.find('kml:name', ns)
                    name = name.text if name is not None else "Unnamed"
                    
                    # Extract Geometry
                    # Check for Polygon
                    poly = placemark.find('.//kml:Polygon', ns)
                    if poly is not None:
                        coords_text = placemark.find('.//kml:coordinates', ns).text
                        coords = parse_coordinates(coords_text)
                        if coords:
                            features['polygons'].append({
                                'name': name,
                                'geometry': Polygon(coords)
                            })
                        continue
                        
                    # Check for Point
                    point = placemark.find('.//kml:Point', ns)
                    if point is not None:
                        coords_text = placemark.find('.//kml:coordinates', ns).text
                        coords = parse_coordinates(coords_text)
                        if coords:
                            features['points'].append({
                                'name': name,
                                'geometry': Point(coords[0])
                            })
                        continue
                        
    except Exception as e:
        print(f"Error parsing KMZ: {e}")
        
    return features

def parse_coordinates(text: str) -> List[Tuple[float, float]]:
    """Parse KML coordinate string."""
    coords = []
    if not text:
        return coords
    
    for pair in text.strip().split():
        parts = pair.split(',')
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return coords

# ============================================================================ 
# PROCESSING
# ============================================================================ 

def process_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Classify and process features."""
    processed = {
        'site_boundary': None,
        'buffers': [],
        'site_point': None,
        'tanks': [],
        'other': []
    }
    
    # 1. Identify Polygons
    for poly in features['polygons']:
        name_lower = poly['name'].lower()
        if 'boundary' in name_lower or 'site' in name_lower and 'buffer' not in name_lower:
            # Assume this is the main site boundary
            # If multiple, take the first one or the one explicitly named "Site Boundary"
            if processed['site_boundary'] is None or 'boundary' in name_lower:
                processed['site_boundary'] = poly
            else:
                processed['other'].append(poly)
        elif 'buffer' in name_lower:
            processed['buffers'].append(poly)
        else:
            processed['other'].append(poly)
            
    # 2. Identify Points
    for pt in features['points']:
        name = safe_title_case(pt['name'])
        pt['name'] = name # Update name
        
        if is_tank_name(name):
            processed['tanks'].append(pt)
        elif 'point' in name.lower() and ('site' in name.lower() or 'project' in name.lower()):
            processed['site_point'] = pt
        else:
            processed['other'].append(pt)
            
    # 3. Calculate Distances
    if processed['site_boundary']:
        main_poly = processed['site_boundary']['geometry']
        for tank in processed['tanks']:
            dist_ft = get_distance_ft(tank['geometry'], main_poly)
            tank['distance_ft'] = dist_ft
            
    return processed

# ============================================================================ 
# OUTPUT
# ============================================================================ 

def generate_excel(processed: Dict[str, Any], output_path: str):
    """Generate clean Excel report."""
    rows = []
    
    for tank in processed['tanks']:
        row = {
            'Site Name': tank['name'],
            'Latitude': tank['geometry'].y,
            'Longitude': tank['geometry'].x,
            'Distance to Boundary (ft)': round(tank.get('distance_ft', 0), 2),
            'Notes': ''
        }
        rows.append(row)
        
    df = pd.DataFrame(rows)
    df = df.sort_values('Site Name')
    
    df.to_excel(output_path, index=False)
    print(f"Generated Excel: {output_path}")

def generate_master_kmz(processed: Dict[str, Any], output_path: str):
    """Generate structured Master KMZ."""
    
    kml_content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        '  <name>Master Site Analysis</name>',
        '  <Style id="site_style"><PolyStyle><color>4d0000ff</color></PolyStyle><LineStyle><color>ff0000ff</color><width>2</width></LineStyle></Style>',
        '  <Style id="buffer_style"><PolyStyle><color>4d00ffff</color></PolyStyle><LineStyle><color>ffffff00</color><width>1</width></LineStyle></Style>',
        '  <Style id="tank_style"><IconStyle><scale>1.1</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon></IconStyle><LabelStyle><scale>0.8</scale></LabelStyle></Style>',
        '  <Style id="site_point_style"><IconStyle><scale>1.3</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/star.png</href></Icon></IconStyle></Style>',
    ]
    
    # 1. Site Info Folder
    kml_content.append('  <Folder><name>Site Info</name>')
    
    if processed['site_boundary']:
        poly = processed['site_boundary']
        coords = list(poly['geometry'].exterior.coords)
        coord_str = " ".join([f"{x},{y},0" for x, y in coords])
        kml_content.append(f"""
        <Placemark>
          <name>{poly['name']}</name>
          <styleUrl>#site_style</styleUrl>
          <Polygon>
            <outerBoundaryIs>
              <LinearRing>
                <coordinates>{coord_str}</coordinates>
              </LinearRing>
            </outerBoundaryIs>
          </Polygon>
        </Placemark>
        """)
        
    if processed['site_point']:
        pt = processed['site_point']
        kml_content.append(f"""
        <Placemark>
          <name>{pt['name']}</name>
          <styleUrl>#site_point_style</styleUrl>
          <Point>
            <coordinates>{pt['geometry'].x},{pt['geometry'].y},0</coordinates>
          </Point>
        </Placemark>
        """)
    kml_content.append('  </Folder>')
    
    # 2. Buffers Folder
    if processed['buffers']:
        kml_content.append('  <Folder><name>Safety Buffers</name>')
        for buff in processed['buffers']:
            coords = list(buff['geometry'].exterior.coords)
            coord_str = " ".join([f"{x},{y},0" for x, y in coords])
            kml_content.append(f"""
            <Placemark>
              <name>{buff['name']}</name>
              <styleUrl>#buffer_style</styleUrl>
              <Polygon>
                <outerBoundaryIs>
                  <LinearRing>
                    <coordinates>{coord_str}</coordinates>
                  </LinearRing>
                </outerBoundaryIs>
              </Polygon>
            </Placemark>
            """)
        kml_content.append('  </Folder>')
    
    # 3. Tanks Folder
    kml_content.append('  <Folder><name>Tanks / Facilities</name>')
    for tank in processed['tanks']:
        dist_info = f"Distance to Boundary: {tank.get('distance_ft', 0):.1f} ft"
        kml_content.append(f"""
        <Placemark>
          <name>{tank['name']}</name>
          <description>{dist_info}</description>
          <styleUrl>#tank_style</styleUrl>
          <Point>
            <coordinates>{tank['geometry'].x},{tank['geometry'].y},0</coordinates>
          </Point>
        </Placemark>
        """)
    kml_content.append('  </Folder>')
    
    kml_content.append('</Document></kml>')
    
    # Write KMZ
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
        kmz.writestr('doc.kml', "\n".join(kml_content))
    print(f"Generated Master KMZ: {output_path}")

# ============================================================================ 
# MAIN
# ============================================================================ 

def main():
    parser = argparse.ArgumentParser(description="Smart Tank Analysis")
    parser.add_argument("input_kmz", help="Input KMZ file")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory")
    args = parser.parse_args()
    
    input_path = Path(args.input_kmz)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing: {input_path}")
    
    # 1. Parse
    features = parse_kmz(str(input_path))
    print(f"Found {len(features['points'])} points, {len(features['polygons'])} polygons")
    
    # 2. Process
    processed = process_features(features)
    print(f"Identified:")
    print(f"  - Site Boundary: {'Yes' if processed['site_boundary'] else 'No'}")
    print(f"  - Site Point: {'Yes' if processed['site_point'] else 'No'}")
    print(f"  - Buffers: {len(processed['buffers'])}")
    print(f"  - Tanks: {len(processed['tanks'])}")
    
    # 3. Generate Excel
    excel_path = output_dir / f"{input_path.stem}_Analysis.xlsx"
    generate_excel(processed, str(excel_path))
    
    # 4. Generate KMZ
    kmz_path = output_dir / f"{input_path.stem}_Master.kmz"
    generate_master_kmz(processed, str(kmz_path))
    
    print("\nDone!")

if __name__ == "__main__":
    main()
