#!/usr/bin/env python3
"""
Match location data from KMZ file to Excel file by site names
"""

import pandas as pd
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import re
from difflib import SequenceMatcher

def parse_kmz_file(kmz_path):
    """Parse KMZ file and extract placemarks with coordinates"""
    locations = []

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
            return locations

        # Read and parse the KML
        with kmz.open(kml_file) as kml:
            tree = ET.parse(kml)
            root = tree.getroot()

            # Handle namespace
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}
            if root.tag == '{http://earth.google.com/kml/2.0}kml':
                ns = {'kml': 'http://earth.google.com/kml/2.0'}
            elif root.tag == '{http://earth.google.com/kml/2.1}kml':
                ns = {'kml': 'http://earth.google.com/kml/2.1'}
            elif root.tag == '{http://earth.google.com/kml/2.2}kml':
                ns = {'kml': 'http://earth.google.com/kml/2.2'}

            # Find all Placemarks
            for placemark in root.findall('.//kml:Placemark', ns):
                name_elem = placemark.find('kml:name', ns)
                if name_elem is None:
                    continue

                name = name_elem.text

                # Get coordinates
                coords_elem = placemark.find('.//kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coords = coords_elem.text.strip()
                    # Format: longitude,latitude,altitude
                    parts = coords.split(',')
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        locations.append({
                            'name': name,
                            'latitude': lat,
                            'longitude': lon
                        })

    return locations

def normalize_name(name):
    """Normalize site names for matching"""
    # Convert to lowercase
    name = str(name).lower().strip()
    # Remove common variations
    name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    return name

def find_best_match(excel_name, kmz_locations):
    """Find the best matching location from KMZ for an Excel site name"""
    excel_norm = normalize_name(excel_name)
    best_match = None
    best_score = 0

    for kmz_loc in kmz_locations:
        kmz_norm = normalize_name(kmz_loc['name'])

        # Try exact match first
        if excel_norm == kmz_norm:
            return kmz_loc, 1.0

        # Calculate similarity score
        score = SequenceMatcher(None, excel_norm, kmz_norm).ratio()

        # Also check if one contains the other
        if excel_norm in kmz_norm or kmz_norm in excel_norm:
            score = max(score, 0.8)

        # Check for partial word matches
        excel_words = set(excel_norm.split())
        kmz_words = set(kmz_norm.split())
        common_words = excel_words.intersection(kmz_words)
        if len(common_words) >= 2:  # At least 2 words in common
            score = max(score, 0.7)

        if score > best_score:
            best_score = score
            best_match = kmz_loc

    return best_match, best_score

def match_locations(excel_path, kmz_path):
    """Match locations from KMZ to Excel by site names"""

    # Read Excel
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} sites from Excel")

    # Parse KMZ
    kmz_locations = parse_kmz_file(kmz_path)
    print(f"Found {len(kmz_locations)} locations in KMZ file")
    print("\nKMZ Locations found:")
    for loc in kmz_locations:
        print(f"  - {loc['name']}")

    # Match each Excel site to KMZ location
    print("\n" + "="*80)
    print("Matching sites:")
    print("="*80)

    matches = []
    no_matches = []

    for idx, row in df.iterrows():
        excel_name = row['Site Name or Business Name']
        current_lat = row.get('Latitude (NAD83)', None)
        current_lon = row.get('Longitude (NAD83)', None)

        # Find best match in KMZ
        match, score = find_best_match(excel_name, kmz_locations)

        if match and score >= 0.5:  # Threshold for accepting a match
            matches.append({
                'row': idx,
                'excel_name': excel_name,
                'kmz_name': match['name'],
                'score': score,
                'new_lat': match['latitude'],
                'new_lon': match['longitude'],
                'old_lat': current_lat,
                'old_lon': current_lon
            })

            status = "UPDATE" if pd.notna(current_lat) else "ADD"
            print(f"{idx+1:2}. {status:6} {excel_name[:40]:40} -> {match['name'][:30]:30} (score: {score:.2f})")
            if pd.notna(current_lat):
                lat_diff = abs(match['latitude'] - current_lat) if pd.notna(current_lat) else 0
                lon_diff = abs(match['longitude'] - current_lon) if pd.notna(current_lon) else 0
                if lat_diff > 0.0001 or lon_diff > 0.0001:
                    print(f"    Old: {current_lat:.8f}, {current_lon:.8f}")
                    print(f"    New: {match['latitude']:.8f}, {match['longitude']:.8f}")
        else:
            no_matches.append(excel_name)
            if pd.notna(current_lat):
                print(f"{idx+1:2}. KEEP   {excel_name[:40]:40} (no match found, keeping existing)")
            else:
                print(f"{idx+1:2}. SKIP   {excel_name[:40]:40} (no match found)")

    # Apply matches to DataFrame
    print("\n" + "="*80)
    print(f"Applying {len(matches)} matches to Excel...")

    for match in matches:
        df.at[match['row'], 'Latitude (NAD83)'] = match['new_lat']
        df.at[match['row'], 'Longitude (NAD83)'] = match['new_lon']

    # Save updated Excel
    output_path = excel_path.replace('.xlsx', '_with_kmz_locations.xlsx')
    df.to_excel(output_path, index=False)
    print(f"\nSaved updated Excel to: {output_path}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print(f"  Total sites in Excel: {len(df)}")
    print(f"  Locations matched from KMZ: {len(matches)}")
    print(f"  Sites not matched: {len(no_matches)}")
    if no_matches:
        print("\n  Unmatched sites:")
        for name in no_matches:
            print(f"    - {name}")

if __name__ == "__main__":
    excel_file = "tank_locations_20250904_005354 (2).xlsx"
    kmz_file = "JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"

    match_locations(excel_file, kmz_file)