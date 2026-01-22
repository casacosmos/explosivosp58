#!/usr/bin/env python3
"""
Script to narrow a polygon in a KMZ file to approximately 100 meters width.
Scales the polygon proportionally from both sides along its width axis.
"""

import xml.etree.ElementTree as ET
import numpy as np
from math import radians, cos, sin, sqrt, atan2
import zipfile
import os
import sys

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

def parse_coordinates(coord_string):
    """Parse KML coordinate string into list of (lon, lat, alt) tuples."""
    coords = []
    lines = coord_string.strip().split()
    for line in lines:
        if line:
            parts = line.split(',')
            if len(parts) >= 2:
                lon = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else 0
                coords.append((lon, lat, alt))
    return coords

def find_polygon_axis(coords):
    """Find the principal axis (length and width) of the polygon."""
    # Convert to numpy array (excluding altitude)
    points = np.array([(lon, lat) for lon, lat, _ in coords])

    # Calculate centroid
    centroid = np.mean(points, axis=0)

    # Center the points
    centered = points - centroid

    # Calculate covariance matrix
    cov = np.cov(centered.T)

    # Find eigenvectors (principal axes)
    eigenvalues, eigenvectors = np.linalg.eig(cov)

    # Sort by eigenvalue (largest first - this is the length axis)
    idx = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # The first eigenvector is the length axis, second is width axis
    length_axis = eigenvectors[:, 0]
    width_axis = eigenvectors[:, 1]

    # Calculate current width in meters
    # Project points onto width axis
    projections = np.dot(centered, width_axis)
    min_proj = np.min(projections)
    max_proj = np.max(projections)

    # Convert width from degrees to meters (approximate)
    width_degrees = max_proj - min_proj
    # Use centroid latitude for conversion
    meters_per_degree_lon = haversine_distance(centroid[1], centroid[0], centroid[1], centroid[0] + 1)
    meters_per_degree_lat = haversine_distance(centroid[1], centroid[0], centroid[1] + 1, centroid[0])
    avg_meters_per_degree = (meters_per_degree_lon + meters_per_degree_lat) / 2

    current_width = width_degrees * avg_meters_per_degree

    return centroid, width_axis, current_width, avg_meters_per_degree

def narrow_polygon(coords, target_width_meters=100):
    """Narrow the polygon to the target width."""
    centroid, width_axis, current_width, meters_per_degree = find_polygon_axis(coords)

    print(f"Current polygon width: {current_width:.1f} meters")
    print(f"Target width: {target_width_meters} meters")

    if current_width <= target_width_meters:
        print("Polygon is already narrower than target width. No changes made.")
        return coords

    # Calculate scaling factor
    scale_factor = target_width_meters / current_width
    print(f"Scaling factor: {scale_factor:.3f}")

    # Apply scaling along the width axis
    new_coords = []
    for lon, lat, alt in coords:
        point = np.array([lon, lat])
        centered = point - centroid

        # Project onto width axis
        projection = np.dot(centered, width_axis)

        # Scale the projection
        new_projection = projection * scale_factor

        # Reconstruct the point
        width_component = width_axis * new_projection
        length_component = centered - (width_axis * projection)
        new_point = centroid + width_component + length_component

        new_coords.append((new_point[0], new_point[1], alt))

    return new_coords

def process_kmz(input_file, output_file):
    """Process KMZ file to narrow the polygon."""
    # Extract KML from KMZ
    temp_dir = "/tmp/kmz_work"
    os.makedirs(temp_dir, exist_ok=True)

    with zipfile.ZipFile(input_file, 'r') as kmz:
        kmz.extractall(temp_dir)

    kml_file = os.path.join(temp_dir, "doc.kml")

    # Parse KML
    tree = ET.parse(kml_file)
    root = tree.getroot()

    # Define namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    # Find coordinates element
    coords_elem = root.find('.//kml:coordinates', ns)
    if coords_elem is None:
        # Try without namespace
        coords_elem = root.find('.//coordinates')

    if coords_elem is None:
        print("Error: No coordinates found in KML file")
        return False

    # Parse coordinates
    coords = parse_coordinates(coords_elem.text)
    print(f"Found polygon with {len(coords)} vertices")

    # Narrow the polygon
    new_coords = narrow_polygon(coords, target_width_meters=100)

    # Format new coordinates
    coord_strings = []
    for lon, lat, alt in new_coords:
        coord_strings.append(f"{lon},{lat},{alt}")

    # Update coordinates in KML
    coords_elem.text = "\n\t\t\t\t\t\t" + " ".join(coord_strings) + "\n\t\t\t\t\t"

    # Save modified KML
    tree.write(kml_file, encoding='UTF-8', xml_declaration=True)

    # Create new KMZ
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as kmz:
        kmz.write(kml_file, "doc.kml")

    print(f"Created narrowed KMZ file: {output_file}")
    return True

if __name__ == "__main__":
    input_file = "/home/avapc/Downloads/bayamonguaynabo.kmz"
    output_file = "/home/avapc/Downloads/bayamonguaynabo_narrow.kmz"

    if process_kmz(input_file, output_file):
        print("Successfully narrowed polygon to ~100m width")
    else:
        print("Failed to process KMZ file")