#!/usr/bin/env python3
"""
MCP Server for Tank Compliance Assessment Pipeline
Provides tools for processing tank data, calculating distances, and assessing compliance
"""

import json
import asyncio
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
import pyproj
from shapely.geometry import Point, Polygon
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import re
from pathlib import Path
from math import pi
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TankComplianceTools:
    """MCP Tools for Tank Compliance Assessment"""

    def __init__(self):
        self.transformer = None
        self.current_data = {}

    # ============ Data Parsing & Validation Tools ============

    async def parse_tank_measurements(self, measurement_str: str) -> Dict[str, Any]:
        """
        Parse tank measurements and calculate volumes

        Args:
            measurement_str: String like "39"x46"x229"" or "182"x55"x26""

        Returns:
            Dictionary with parsed measurements and calculated volume
        """
        if not measurement_str or pd.isna(measurement_str):
            return {"error": "No measurement provided", "volume_gallons": None}

        measurement_str = str(measurement_str)

        # Fix common formatting issues
        measurement_str = re.sub(r'(\d+)"(\d+)"', r'\1"x\2"', measurement_str)
        measurement_str = re.sub(r'(\d+)"(\d+)"', r'\1"x\2"', measurement_str)

        # Extract dimensions
        matches = re.findall(r'(\d+(?:\.\d+)?)"', measurement_str)

        if not matches:
            return {"error": "No dimensions found", "volume_gallons": None}

        dimensions = [float(m) for m in matches]

        # Calculate volume based on number of dimensions
        if len(dimensions) == 2:
            # Cylindrical tank: diameter x height
            diameter, height = dimensions
            radius = diameter / 2
            volume_cubic_inches = pi * (radius ** 2) * height
        elif len(dimensions) == 3:
            # Rectangular tank
            volume_cubic_inches = dimensions[0] * dimensions[1] * dimensions[2]
        else:
            return {"error": f"Unexpected number of dimensions: {len(dimensions)}", "volume_gallons": None}

        # Convert to gallons (1 gallon = 231 cubic inches)
        volume_gallons = volume_cubic_inches / 231

        return {
            "dimensions": dimensions,
            "shape": "cylindrical" if len(dimensions) == 2 else "rectangular",
            "volume_cubic_inches": volume_cubic_inches,
            "volume_gallons": round(volume_gallons, 2)
        }

    async def parse_multi_tank_capacities(self, capacity_str: str) -> Dict[str, Any]:
        """
        Parse capacity string with possibly multiple tanks

        Args:
            capacity_str: String like "1778 gal; 1126 gal" or "397 gal"

        Returns:
            Dictionary with individual capacities and largest tank
        """
        if not capacity_str or pd.isna(capacity_str):
            return {"tanks": [], "largest_capacity": None, "total_capacity": None}

        capacity_str = str(capacity_str)
        capacities = []

        # Find all numbers followed by 'gal'
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*gal', capacity_str, re.IGNORECASE)
        for match in matches:
            capacities.append(float(match))

        if not capacities:
            return {"tanks": [], "largest_capacity": None, "total_capacity": None}

        return {
            "tanks": capacities,
            "number_of_tanks": len(capacities),
            "largest_capacity": max(capacities),
            "total_capacity": sum(capacities),
            "use_for_compliance": max(capacities)  # Use largest for compliance
        }

    async def extract_asd_values(self, asd_string: str) -> Dict[str, Optional[float]]:
        """
        Extract ASDPPU and ASDBPU values from ASD string

        Args:
            asd_string: String containing ASD values

        Returns:
            Dictionary with ASDPPU and ASDBPU values
        """
        if not asd_string or pd.isna(asd_string):
            return {"ASDPPU": None, "ASDBPU": None}

        asd_string = str(asd_string)
        result = {"ASDPPU": None, "ASDBPU": None}

        # Look for ASDPPU value
        asdppu_match = re.search(r'ASDPPU:\s*([\d.]+)', asd_string)
        if asdppu_match:
            result["ASDPPU"] = float(asdppu_match.group(1))

        # Look for ASDBPU value
        asdbpu_match = re.search(r'ASDBPU:\s*([\d.]+)', asd_string)
        if asdbpu_match:
            result["ASDBPU"] = float(asdbpu_match.group(1))

        return result

    # ============ Coordinate System Management Tools ============

    async def parse_kmz_file(self, kmz_path: str) -> Dict[str, Any]:
        """
        Parse KMZ file and extract site locations and polygons

        Args:
            kmz_path: Path to KMZ file

        Returns:
            Dictionary with sites and polygons
        """
        sites = []
        polygons = []

        try:
            with zipfile.ZipFile(kmz_path, 'r') as kmz:
                # Find KML file inside
                kml_file = None
                for file_name in kmz.namelist():
                    if file_name.endswith('.kml'):
                        kml_file = file_name
                        break

                if not kml_file:
                    return {"error": "No KML file found in KMZ", "sites": [], "polygons": []}

                # Read and parse KML
                with kmz.open(kml_file) as kml:
                    content = kml.read().decode('utf-8')

                    # Remove namespace declarations
                    content = re.sub(r'xmlns[^=]*="[^"]*"', '', content)
                    content = re.sub(r'<kml[^>]*>', '<kml>', content)

                    # Parse placemarks
                    placemarks = re.findall(r'<Placemark[^>]*>(.*?)</Placemark>', content, re.DOTALL)

                    for placemark in placemarks:
                        name_match = re.search(r'<name>([^<]+)</name>', placemark)
                        if name_match:
                            name = name_match.group(1).strip()
                            name = name.replace('&quot;', '"')

                            # Look for point coordinates
                            point_match = re.search(r'<Point>.*?<coordinates>([^<]+)</coordinates>', placemark, re.DOTALL)
                            if point_match:
                                coords = point_match.group(1).strip().split(',')
                                if len(coords) >= 2:
                                    sites.append({
                                        "name": name,
                                        "latitude": float(coords[1]),
                                        "longitude": float(coords[0])
                                    })

                            # Look for polygon coordinates
                            polygon_match = re.search(r'<Polygon>.*?<coordinates>([^<]+)</coordinates>', placemark, re.DOTALL)
                            if polygon_match:
                                coords_str = polygon_match.group(1).strip()
                                coords = []
                                for coord_set in coords_str.split():
                                    parts = coord_set.split(',')
                                    if len(parts) >= 2:
                                        coords.append((float(parts[0]), float(parts[1])))
                                if len(coords) >= 3:
                                    polygons.append({
                                        "name": name,
                                        "coordinates": coords
                                    })

        except Exception as e:
            return {"error": str(e), "sites": [], "polygons": []}

        return {"sites": sites, "polygons": polygons, "count": len(sites)}

    async def convert_dms_to_decimal(self, degrees: float, minutes: float, seconds: float, direction: str = 'N') -> float:
        """
        Convert degrees, minutes, seconds to decimal degrees

        Args:
            degrees: Degrees value
            minutes: Minutes value
            seconds: Seconds value
            direction: N/S/E/W direction

        Returns:
            Decimal degrees value
        """
        decimal = degrees + minutes/60 + seconds/3600

        # Make negative for South or West
        if direction in ['S', 'W']:
            decimal = -decimal

        return round(decimal, 7)

    async def match_sites_fuzzy(self, excel_sites: List[str], kmz_sites: List[Dict]) -> Dict[str, Any]:
        """
        Match site names between Excel and KMZ using fuzzy matching

        Args:
            excel_sites: List of site names from Excel
            kmz_sites: List of site dictionaries from KMZ

        Returns:
            Dictionary mapping Excel names to KMZ coordinates
        """
        matches = {}
        unmatched_excel = []
        unmatched_kmz = list(kmz_sites)

        for excel_name in excel_sites:
            excel_clean = excel_name.lower().strip()
            best_match = None
            best_score = 0

            for kmz_site in kmz_sites:
                kmz_name = kmz_site['name'].lower().strip()

                # Check various matching strategies
                score = 0
                if excel_clean == kmz_name:
                    score = 1.0
                elif excel_clean in kmz_name or kmz_name in excel_clean:
                    score = 0.8
                elif any(word in kmz_name for word in excel_clean.split()[:3]):
                    score = 0.6

                if score > best_score:
                    best_score = score
                    best_match = kmz_site

            if best_match and best_score > 0.5:
                matches[excel_name] = {
                    "latitude": best_match['latitude'],
                    "longitude": best_match['longitude'],
                    "kmz_name": best_match['name'],
                    "match_score": best_score
                }
                if best_match in unmatched_kmz:
                    unmatched_kmz.remove(best_match)
            else:
                unmatched_excel.append(excel_name)

        return {
            "matches": matches,
            "unmatched_excel": unmatched_excel,
            "unmatched_kmz": [site['name'] for site in unmatched_kmz],
            "match_rate": len(matches) / len(excel_sites) if excel_sites else 0
        }

    # ============ Geospatial Calculation Tools ============

    async def calculate_distance_to_polygon(self, point_lat: float, point_lon: float,
                                           polygon_coords: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Calculate minimum distance from point to polygon boundary

        Args:
            point_lat: Latitude of the point
            point_lon: Longitude of the point
            polygon_coords: List of (lon, lat) tuples defining polygon

        Returns:
            Dictionary with distance and closest point information
        """
        # Use UTM Zone 19N for Puerto Rico
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

        # Create polygon
        polygon = Polygon(zip(poly_x, poly_y))

        # Calculate distance to boundary
        boundary = polygon.exterior
        distance_meters = tank_point.distance(boundary)

        # Find closest point on boundary
        closest_point = boundary.interpolate(boundary.project(tank_point))

        # Transform back to lat/lon
        transformer_back = pyproj.Transformer.from_crs('EPSG:32619', 'EPSG:4326', always_xy=True)
        closest_lon, closest_lat = transformer_back.transform(closest_point.x, closest_point.y)

        # Convert to feet
        distance_feet = distance_meters * 3.28084

        # Check if inside polygon
        is_inside = polygon.contains(tank_point)

        return {
            "distance_feet": round(distance_feet, 2),
            "distance_meters": round(distance_meters, 2),
            "closest_point_lat": closest_lat,
            "closest_point_lon": closest_lon,
            "is_inside": is_inside,
            "point_location": "Inside" if is_inside else "Outside"
        }

    async def batch_calculate_distances(self, sites: List[Dict], polygon_coords: List[Tuple]) -> List[Dict]:
        """
        Calculate distances for multiple sites

        Args:
            sites: List of site dictionaries with lat/lon
            polygon_coords: Polygon boundary coordinates

        Returns:
            List of sites with distance information added
        """
        results = []

        for site in sites:
            if 'latitude' in site and 'longitude' in site:
                distance_info = await self.calculate_distance_to_polygon(
                    site['latitude'],
                    site['longitude'],
                    polygon_coords
                )
                site.update(distance_info)
            else:
                site['distance_feet'] = None
                site['error'] = "No coordinates"

            results.append(site)

        return results

    # ============ Compliance Assessment Tools ============

    async def assess_compliance(self, distance_feet: float, asd_values: Dict,
                               has_dike: bool = False) -> Dict[str, Any]:
        """
        Assess compliance based on distance and ASD requirements

        Args:
            distance_feet: Actual distance to boundary
            asd_values: Dictionary with ASDPPU and ASDBPU values
            has_dike: Whether tank has a dike

        Returns:
            Compliance assessment results
        """
        if not asd_values or not asd_values.get('ASDPPU'):
            return {
                "status": "No ASD Data",
                "compliant": None,
                "margin": None,
                "required_distance": None
            }

        # Use ASDBPU if has dike, otherwise ASDPPU
        if has_dike and asd_values.get('ASDBPU'):
            required_distance = asd_values['ASDBPU']
            distance_type = "ASDBPU"
        else:
            required_distance = asd_values['ASDPPU']
            distance_type = "ASDPPU"

        margin = distance_feet - required_distance
        compliant = distance_feet >= required_distance

        # Determine risk level for non-compliant
        risk_level = None
        if not compliant:
            deficit = abs(margin)
            if deficit > 100:
                risk_level = "High Risk"
            elif deficit > 50:
                risk_level = "Medium Risk"
            else:
                risk_level = "Low Risk"

        return {
            "status": "COMPLIANT" if compliant else "NON-COMPLIANT",
            "compliant": compliant,
            "margin": round(margin, 2),
            "required_distance": required_distance,
            "distance_type": distance_type,
            "risk_level": risk_level
        }

    async def process_excel_compliance(self, excel_path: str, polygon_coords: List[Tuple]) -> Dict[str, Any]:
        """
        Process entire Excel file for compliance assessment

        Args:
            excel_path: Path to Excel file
            polygon_coords: Polygon boundary coordinates

        Returns:
            Comprehensive compliance results
        """
        df = pd.read_excel(excel_path)
        results = []

        summary = {
            "total": len(df),
            "compliant": 0,
            "non_compliant": 0,
            "no_asd_data": 0,
            "no_coordinates": 0
        }

        for idx, row in df.iterrows():
            site_result = {
                "site_name": row.get('Site Name or Business Name'),
                "tank_capacity": row.get('Tank Capacity'),
                "latitude": row.get('Latitude (NAD83)'),
                "longitude": row.get('Longitude (NAD83)')
            }

            # Check coordinates
            if pd.notna(site_result['latitude']) and pd.notna(site_result['longitude']):
                # Calculate distance
                distance_info = await self.calculate_distance_to_polygon(
                    site_result['latitude'],
                    site_result['longitude'],
                    polygon_coords
                )
                site_result.update(distance_info)

                # Extract ASD values
                asd_string = row.get('Acceptable Separation Distance Calculated', '')
                asd_values = await self.extract_asd_values(asd_string)

                # Assess compliance
                has_dike = row.get('Has Dike', False)
                compliance = await self.assess_compliance(
                    distance_info['distance_feet'],
                    asd_values,
                    has_dike
                )
                site_result.update(compliance)

                # Update summary
                if compliance['compliant'] == True:
                    summary['compliant'] += 1
                elif compliance['compliant'] == False:
                    summary['non_compliant'] += 1
                else:
                    summary['no_asd_data'] += 1
            else:
                site_result['status'] = "No Coordinates"
                summary['no_coordinates'] += 1

            results.append(site_result)

        return {
            "sites": results,
            "summary": summary
        }

    # ============ Visualization Generation Tools ============

    async def create_kmz_file(self, sites: List[Dict], polygons: List[Dict],
                             output_path: str = "output.kmz") -> Dict[str, Any]:
        """
        Create KMZ file with sites and polygons

        Args:
            sites: List of site dictionaries
            polygons: List of polygon dictionaries
            output_path: Output file path

        Returns:
            Success status and file path
        """
        # Create KML structure
        kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
        document = ET.SubElement(kml, 'Document')

        # Add name
        name_elem = ET.SubElement(document, 'name')
        name_elem.text = 'Tank Compliance Assessment'

        # Define styles
        styles = {
            'compliant': 'ff00ff00',  # Green
            'noncompliant': 'ff0000ff',  # Red
            'nodata': 'ff00ffff'  # Yellow
        }

        for style_id, color in styles.items():
            style = ET.SubElement(document, 'Style', id=style_id)
            icon_style = ET.SubElement(style, 'IconStyle')
            color_elem = ET.SubElement(icon_style, 'color')
            color_elem.text = color

        # Add sites
        sites_folder = ET.SubElement(document, 'Folder')
        folder_name = ET.SubElement(sites_folder, 'name')
        folder_name.text = 'Sites'

        for site in sites:
            if 'latitude' in site and 'longitude' in site:
                placemark = ET.SubElement(sites_folder, 'Placemark')

                name = ET.SubElement(placemark, 'name')
                name.text = site.get('display_name', site.get('site_name', 'Unknown'))

                # Set style based on compliance
                style_url = ET.SubElement(placemark, 'styleUrl')
                status = site.get('status', 'No ASD Data')
                if status == 'COMPLIANT':
                    style_url.text = '#compliant'
                elif status == 'NON-COMPLIANT':
                    style_url.text = '#noncompliant'
                else:
                    style_url.text = '#nodata'

                point = ET.SubElement(placemark, 'Point')
                coordinates = ET.SubElement(point, 'coordinates')
                coordinates.text = f"{site['longitude']},{site['latitude']},0"

        # Add polygons
        if polygons:
            boundary_folder = ET.SubElement(document, 'Folder')
            folder_name = ET.SubElement(boundary_folder, 'name')
            folder_name.text = 'Boundaries'

            for poly_data in polygons:
                placemark = ET.SubElement(boundary_folder, 'Placemark')
                name = ET.SubElement(placemark, 'name')
                name.text = poly_data.get('name', 'Boundary')

                polygon = ET.SubElement(placemark, 'Polygon')
                outer = ET.SubElement(polygon, 'outerBoundaryIs')
                linear_ring = ET.SubElement(outer, 'LinearRing')
                coordinates = ET.SubElement(linear_ring, 'coordinates')

                coords_str = ' '.join([f"{lon},{lat},0" for lon, lat in poly_data['coordinates']])
                coordinates.text = coords_str

        # Convert to XML string
        xml_str = ET.tostring(kml, encoding='unicode')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')

        # Save KML temporarily
        kml_path = Path(output_path).with_suffix('.kml')
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

        # Create KMZ
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            kmz.write(kml_path, 'doc.kml')

        # Clean up KML
        kml_path.unlink()

        return {
            "success": True,
            "path": output_path,
            "sites_count": len([s for s in sites if 'latitude' in s]),
            "polygons_count": len(polygons)
        }

    # ============ Data Integration Tools ============

    async def update_excel_with_results(self, excel_path: str, results: List[Dict],
                                       output_path: str = None) -> Dict[str, Any]:
        """
        Update Excel file with calculated results

        Args:
            excel_path: Original Excel file path
            results: List of results dictionaries
            output_path: Output file path (defaults to same as input)

        Returns:
            Success status and summary
        """
        if not output_path:
            output_path = excel_path

        df = pd.read_excel(excel_path)

        # Create mapping of results by site name
        results_map = {r['site_name']: r for r in results}

        # Add/update columns
        for idx, row in df.iterrows():
            site_name = row['Site Name or Business Name']

            if site_name in results_map:
                result = results_map[site_name]

                # Update distance and compliance columns
                df.at[idx, 'Calculated Distance to Polygon (ft)'] = result.get('distance_feet')
                df.at[idx, 'Closest Point Lat'] = result.get('closest_point_lat')
                df.at[idx, 'Closest Point Lon'] = result.get('closest_point_lon')
                df.at[idx, 'Point Location'] = result.get('point_location')

                # Update compliance
                if result.get('status') == 'COMPLIANT':
                    df.at[idx, 'Compliance'] = 'Yes'
                elif result.get('status') == 'NON-COMPLIANT':
                    df.at[idx, 'Compliance'] = 'No'
                else:
                    df.at[idx, 'Compliance'] = None

        # Save updated file
        df.to_excel(output_path, index=False)

        return {
            "success": True,
            "path": output_path,
            "rows_updated": len(results_map),
            "total_rows": len(df)
        }


# ============ HUD Browser Automation Tool ============

    async def process_hud_calculations(self, tanks: List[Dict], generate_pdf: bool = True,
                                      capture_screenshots: bool = True) -> Dict[str, Any]:
        """
        Process tanks through HUD ASD calculator with browser automation

        Args:
            tanks: List of tank dictionaries with site_name and tank_capacity
            generate_pdf: Whether to generate PDF report
            capture_screenshots: Whether to capture screenshots

        Returns:
            Dictionary with ASD results and generated files
        """
        from hud_automation_tool import process_hud_calculations

        return await process_hud_calculations({
            'tanks': tanks,
            'generate_pdf': generate_pdf,
            'capture_screenshots': capture_screenshots,
            'headless': True
        })

# ============ MCP Server Interface ============

async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle MCP tool requests
    """
    tools = TankComplianceTools()

    method = request.get('method')
    params = request.get('params', {})

    try:
        # Route to appropriate tool
        if method == 'parse_tank_measurements':
            return await tools.parse_tank_measurements(params['measurement_str'])

        elif method == 'parse_multi_tank_capacities':
            return await tools.parse_multi_tank_capacities(params['capacity_str'])

        elif method == 'extract_asd_values':
            return await tools.extract_asd_values(params['asd_string'])

        elif method == 'parse_kmz_file':
            return await tools.parse_kmz_file(params['kmz_path'])

        elif method == 'convert_dms_to_decimal':
            return await tools.convert_dms_to_decimal(
                params['degrees'], params['minutes'], params['seconds'],
                params.get('direction', 'N')
            )

        elif method == 'match_sites_fuzzy':
            return await tools.match_sites_fuzzy(params['excel_sites'], params['kmz_sites'])

        elif method == 'calculate_distance_to_polygon':
            return await tools.calculate_distance_to_polygon(
                params['point_lat'], params['point_lon'], params['polygon_coords']
            )

        elif method == 'batch_calculate_distances':
            return await tools.batch_calculate_distances(params['sites'], params['polygon_coords'])

        elif method == 'assess_compliance':
            return await tools.assess_compliance(
                params['distance_feet'], params['asd_values'], params.get('has_dike', False)
            )

        elif method == 'process_excel_compliance':
            return await tools.process_excel_compliance(params['excel_path'], params['polygon_coords'])

        elif method == 'create_kmz_file':
            return await tools.create_kmz_file(
                params['sites'], params['polygons'], params.get('output_path', 'output.kmz')
            )

        elif method == 'update_excel_with_results':
            return await tools.update_excel_with_results(
                params['excel_path'], params['results'], params.get('output_path')
            )

        elif method == 'process_hud_calculations':
            return await tools.process_hud_calculations(
                params['tanks'], params.get('generate_pdf', True),
                params.get('capture_screenshots', True)
            )

        else:
            return {"error": f"Unknown method: {method}"}

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"error": str(e)}


async def main():
    """
    Main entry point for MCP server
    """
    logger.info("Tank Compliance MCP Server started")

    # Read requests from stdin
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, input)
            request = json.loads(line)

            response = await handle_request(request)

            print(json.dumps(response))

        except EOFError:
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    asyncio.run(main())