#!/usr/bin/env python3
"""
Create output KMZ file with tank locations labeled by capacities.
Reads compliance results and creates a Google Earth KMZ file.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def create_kml_placemark(
    tank_id: str,
    capacity: str,
    lat: float,
    lon: float,
    compliance: str,
    product: str = ""
) -> Element:
    """Create a KML Placemark element for a tank."""
    placemark = Element("Placemark")

    # Name (Tank ID + Capacity)
    name = SubElement(placemark, "name")
    name.text = f"{tank_id} ({capacity})"

    # Description
    description = SubElement(placemark, "description")
    desc_text = f"""
    <![CDATA[
    <h3>{tank_id}</h3>
    <table border="1" cellpadding="5">
        <tr><td><b>Capacity:</b></td><td>{capacity}</td></tr>
        <tr><td><b>Product:</b></td><td>{product}</td></tr>
        <tr><td><b>Compliance:</b></td><td style="color: {'green' if compliance == 'YES' else 'red' if compliance == 'NO' else 'orange'}"><b>{compliance}</b></td></tr>
    </table>
    ]]>
    """
    description.text = desc_text

    # Style based on compliance
    style_url = SubElement(placemark, "styleUrl")
    if compliance == "YES":
        style_url.text = "#greenIcon"
    elif compliance == "NO":
        style_url.text = "#redIcon"
    else:
        style_url.text = "#yellowIcon"

    # Point coordinates
    point = SubElement(placemark, "Point")
    coordinates = SubElement(point, "coordinates")
    coordinates.text = f"{lon},{lat},0"

    return placemark


def create_kml_styles() -> List[Element]:
    """Create KML style definitions for different compliance statuses."""
    styles = []

    # Green (Compliant)
    style_green = Element("Style", id="greenIcon")
    icon_style = SubElement(style_green, "IconStyle")
    icon = SubElement(icon_style, "Icon")
    href = SubElement(icon, "href")
    href.text = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
    styles.append(style_green)

    # Red (Non-compliant)
    style_red = Element("Style", id="redIcon")
    icon_style = SubElement(style_red, "IconStyle")
    icon = SubElement(icon_style, "Icon")
    href = SubElement(icon, "href")
    href.text = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
    styles.append(style_red)

    # Yellow (Review)
    style_yellow = Element("Style", id="yellowIcon")
    icon_style = SubElement(style_yellow, "IconStyle")
    icon = SubElement(icon_style, "Icon")
    href = SubElement(icon, "href")
    href.text = "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png"
    styles.append(style_yellow)

    return styles


def create_output_kmz(
    compliance_excel: str,
    output_kmz: str
) -> Dict[str, Any]:
    """
    Create KMZ file with tank locations labeled by capacities.

    Args:
        compliance_excel: Path to final compliance Excel file
        output_kmz: Path for output KMZ file

    Returns:
        Dictionary with success status and output path
    """
    try:
        import pandas as pd

        # Read compliance results
        df = pd.read_excel(compliance_excel)

        # Create KML structure
        kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        document = SubElement(kml, "Document")

        # Document name
        name = SubElement(document, "name")
        name.text = "Tank Compliance Results"

        # Add styles
        for style in create_kml_styles():
            document.append(style)

        # Add placemarks for each tank
        tanks_added = 0
        for _, row in df.iterrows():
            # Extract data
            tank_id = str(row.get("Tank ID", "Unknown"))
            capacity = str(row.get("Tank Capacity", "Unknown"))
            lat = row.get("Latitude", None)
            lon = row.get("Longitude", None)
            compliance = str(row.get("Compliance", "REVIEW"))
            product = str(row.get("Product Stored", ""))

            # Skip if no coordinates
            if pd.isna(lat) or pd.isna(lon):
                continue

            # Create placemark
            placemark = create_kml_placemark(
                tank_id=tank_id,
                capacity=capacity,
                lat=float(lat),
                lon=float(lon),
                compliance=compliance,
                product=product
            )
            document.append(placemark)
            tanks_added += 1

        # Convert to pretty XML string
        xml_str = minidom.parseString(tostring(kml, encoding='utf-8')).toprettyxml(indent="  ")

        # Create KMZ (zipped KML)
        output_path = Path(output_kmz)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            kmz.writestr('doc.kml', xml_str)

        return {
            "success": True,
            "output_kmz": str(output_path),
            "tanks_added": tanks_added,
            "message": f"Created KMZ with {tanks_added} tank locations"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create KMZ: {str(e)}"
        }


def main():
    parser = argparse.ArgumentParser(description="Create output KMZ with labeled tank locations")
    parser.add_argument("compliance_excel", help="Path to compliance Excel file")
    parser.add_argument("-o", "--output", default="tanks_output.kmz", help="Output KMZ path")

    args = parser.parse_args()

    result = create_output_kmz(args.compliance_excel, args.output)

    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"📍 Output: {result['output_kmz']}")
        return 0
    else:
        print(f"❌ {result['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())