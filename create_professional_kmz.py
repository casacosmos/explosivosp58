#!/usr/bin/env python3
"""
Professional KMZ Generator with Advanced Styling and Features
Creates richly styled KMZ files with HTML descriptions, legends, and boundary polygons.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import pandas as pd


# ============================================================================
# STYLE DEFINITIONS
# ============================================================================

def create_kml_styles() -> List[Element]:
    """Create professional KML style definitions"""
    styles = []

    # Compliant (Green)
    style_green = Element("Style", id="greenIcon")
    icon_style = SubElement(style_green, "IconStyle")
    SubElement(icon_style, "scale").text = "1.2"
    icon = SubElement(icon_style, "Icon")
    SubElement(icon, "href").text = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
    label_style = SubElement(style_green, "LabelStyle")
    SubElement(label_style, "scale").text = "1.0"
    styles.append(style_green)

    # Non-compliant (Red)
    style_red = Element("Style", id="redIcon")
    icon_style = SubElement(style_red, "IconStyle")
    SubElement(icon_style, "scale").text = "1.3"
    icon = SubElement(icon_style, "Icon")
    SubElement(icon, "href").text = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
    label_style = SubElement(style_red, "LabelStyle")
    SubElement(label_style, "scale").text = "1.1"
    SubElement(label_style, "color").text = "ffff0000"  # Red text
    styles.append(style_red)

    # Review/Unknown (Yellow)
    style_yellow = Element("Style", id="yellowIcon")
    icon_style = SubElement(style_yellow, "IconStyle")
    SubElement(icon_style, "scale").text = "1.2"
    icon = SubElement(icon_style, "Icon")
    SubElement(icon, "href").text = "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png"
    styles.append(style_yellow)

    # Boundary polygon style
    style_boundary = Element("Style", id="boundaryStyle")
    line_style = SubElement(style_boundary, "LineStyle")
    SubElement(line_style, "color").text = "ff0000ff"  # Red line
    SubElement(line_style, "width").text = "3"
    poly_style = SubElement(style_boundary, "PolyStyle")
    SubElement(poly_style, "color").text = "330000ff"  # Semi-transparent red fill
    styles.append(style_boundary)

    return styles


# ============================================================================
# HTML DESCRIPTION GENERATOR
# ============================================================================

def create_html_description(
    tank_id: str,
    capacity: str,
    lat: float,
    lon: float,
    compliance: str,
    product: str = "",
    distance_to_boundary: Optional[float] = None,
    asd_required: Optional[float] = None,
    measurements: Optional[str] = None
) -> str:
    """Create rich HTML description for tank placemark"""

    # Determine compliance color
    compliance_color = {
        "YES": "green",
        "COMPLIANT": "green",
        "NO": "red",
        "NON-COMPLIANT": "red",
        "REVIEW": "orange",
        "UNKNOWN": "gray"
    }.get(str(compliance).upper(), "gray")

    # Format capacity with commas
    try:
        if capacity:
            cap_num = float(str(capacity).replace(",", "").replace("gal", "").strip())
            capacity_formatted = f"{cap_num:,.0f} gal"
        else:
            capacity_formatted = "Unknown"
    except:
        capacity_formatted = str(capacity)

    # Build HTML description
    html = f"""
    <![CDATA[
    <div style="font-family: Arial, sans-serif; font-size: 12px; max-width: 400px;">
        <h3 style="color: #333; border-bottom: 2px solid {compliance_color}; padding-bottom: 5px;">
            {tank_id}
        </h3>

        <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; font-weight: bold; width: 40%;">Capacity:</td>
                <td style="padding: 8px;">{capacity_formatted}</td>
            </tr>
    """

    if product:
        html += f"""
            <tr>
                <td style="padding: 8px; font-weight: bold;">Product:</td>
                <td style="padding: 8px;">{product}</td>
            </tr>
        """

    if measurements:
        html += f"""
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; font-weight: bold;">Dimensions:</td>
                <td style="padding: 8px;">{measurements}</td>
            </tr>
        """

    # Compliance status with badge
    compliance_badge = f"""
        <span style="
            background-color: {compliance_color};
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: bold;
            display: inline-block;
        ">{compliance}</span>
    """

    html += f"""
            <tr>
                <td style="padding: 8px; font-weight: bold;">Compliance:</td>
                <td style="padding: 8px;">{compliance_badge}</td>
            </tr>
    """

    # Distance information
    if distance_to_boundary is not None:
        html += f"""
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; font-weight: bold;">Distance:</td>
                <td style="padding: 8px;">{distance_to_boundary:.2f} ft</td>
            </tr>
        """

    if asd_required is not None:
        html += f"""
            <tr>
                <td style="padding: 8px; font-weight: bold;">ASD Required:</td>
                <td style="padding: 8px;">{asd_required:.2f} ft</td>
            </tr>
        """

    # Coordinates
    html += f"""
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; font-weight: bold;">Coordinates:</td>
                <td style="padding: 8px; font-size: 10px;">
                    {lat:.6f}, {lon:.6f}
                </td>
            </tr>
        </table>

        <div style="margin-top: 10px; padding: 10px; background-color: #e8f4f8; border-radius: 5px;">
            <small><strong>📍 Location Data (NAD83)</strong></small>
        </div>
    </div>
    ]]>
    """

    return html


# ============================================================================
# PLACEMARK CREATION
# ============================================================================

def create_kml_placemark(
    tank_id: str,
    capacity: str,
    lat: float,
    lon: float,
    compliance: str,
    product: str = "",
    distance_to_boundary: Optional[float] = None,
    asd_required: Optional[float] = None,
    measurements: Optional[str] = None
) -> Element:
    """Create a KML Placemark element for a tank with rich formatting"""

    placemark = Element("Placemark")

    # Name with capacity
    name = SubElement(placemark, "name")
    try:
        cap_num = float(str(capacity).replace(",", "").replace("gal", "").strip())
        name.text = f"{tank_id} ({cap_num:,.0f} gal)"
    except:
        name.text = f"{tank_id} ({capacity})"

    # Rich HTML description
    description = SubElement(placemark, "description")
    description.text = create_html_description(
        tank_id, capacity, lat, lon, compliance,
        product, distance_to_boundary, asd_required, measurements
    )

    # Style based on compliance
    style_url = SubElement(placemark, "styleUrl")
    compliance_upper = str(compliance).upper()
    if compliance_upper in ["YES", "COMPLIANT"]:
        style_url.text = "#greenIcon"
    elif compliance_upper in ["NO", "NON-COMPLIANT"]:
        style_url.text = "#redIcon"
    else:
        style_url.text = "#yellowIcon"

    # Point coordinates
    point = SubElement(placemark, "Point")
    coordinates = SubElement(point, "coordinates")
    coordinates.text = f"{lon},{lat},0"

    return placemark


# ============================================================================
# BOUNDARY POLYGON
# ============================================================================

def create_boundary_polygon(
    coordinates: List[Tuple[float, float]],
    name: str = "Site Boundary"
) -> Element:
    """Create boundary polygon placemark"""

    placemark = Element("Placemark")

    # Name
    name_elem = SubElement(placemark, "name")
    name_elem.text = name

    # Description
    description = SubElement(placemark, "description")
    description.text = f"""
    <![CDATA[
    <div style="font-family: Arial, sans-serif;">
        <h3>Site Boundary</h3>
        <p>This polygon represents the site boundary used for compliance distance calculations.</p>
        <p><strong>Buffer:</strong> 1 mile (5,280 feet)</p>
    </div>
    ]]>
    """

    # Style
    style_url = SubElement(placemark, "styleUrl")
    style_url.text = "#boundaryStyle"

    # Polygon
    polygon = SubElement(placemark, "Polygon")
    SubElement(polygon, "extrude").text = "1"
    SubElement(polygon, "altitudeMode").text = "clampToGround"

    outer_boundary = SubElement(polygon, "outerBoundaryIs")
    linear_ring = SubElement(outer_boundary, "LinearRing")
    coords = SubElement(linear_ring, "coordinates")

    # Format coordinates
    coord_strings = [f"{lon},{lat},0" for lon, lat in coordinates]
    coords.text = " ".join(coord_strings)

    return placemark


# ============================================================================
# LEGEND FOLDER
# ============================================================================

def create_legend_folder() -> Element:
    """Create a legend folder explaining the symbols"""

    folder = Element("Folder")

    name = SubElement(folder, "name")
    name.text = "📖 Legend"

    description = SubElement(folder, "description")
    description.text = """
    <![CDATA[
    <div style="font-family: Arial, sans-serif; padding: 15px;">
        <h2 style="border-bottom: 2px solid #333;">Symbol Legend</h2>

        <div style="margin: 15px 0;">
            <h3 style="color: green;">🟢 Green Circle - Compliant</h3>
            <p>Tank meets all separation distance requirements.</p>
        </div>

        <div style="margin: 15px 0;">
            <h3 style="color: red;">🔴 Red Circle - Non-Compliant</h3>
            <p>Tank does not meet required separation distance.</p>
        </div>

        <div style="margin: 15px 0;">
            <h3 style="color: orange;">🟡 Yellow Circle - Review Required</h3>
            <p>Tank status requires additional review or data is incomplete.</p>
        </div>

        <div style="margin: 15px 0; padding: 10px; background-color: #f0f0f0;">
            <h3>📏 Distance Calculations</h3>
            <ul>
                <li><strong>ASD</strong>: Acceptable Separation Distance (from HUD)</li>
                <li><strong>Distance</strong>: Measured distance to site boundary</li>
                <li><strong>Compliance</strong>: YES if Distance ≥ ASD, NO otherwise</li>
            </ul>
        </div>
    </div>
    ]]>
    """

    return folder


# ============================================================================
# MAIN KMZ GENERATOR
# ============================================================================

def create_professional_kmz(
    compliance_excel: str,
    output_kmz: str,
    boundary_coordinates: Optional[List[Tuple[float, float]]] = None,
    include_legend: bool = True
) -> Dict[str, Any]:
    """
    Create professional KMZ with styling, HTML descriptions, and optional boundary.

    Args:
        compliance_excel: Path to final compliance Excel file
        output_kmz: Path for output KMZ file
        boundary_coordinates: Optional boundary polygon coordinates
        include_legend: Whether to include legend folder

    Returns:
        Dictionary with success status and output path
    """
    try:
        # Read compliance results
        df = pd.read_excel(compliance_excel)

        print(f"\n📊 Creating professional KMZ from: {Path(compliance_excel).name}")
        print(f"   Tanks to process: {len(df)}")

        # Create KML structure
        kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        document = SubElement(kml, "Document")

        # Document metadata
        name = SubElement(document, "name")
        name.text = "Tank Compliance Analysis - Professional Report"

        doc_description = SubElement(document, "description")
        doc_description.text = f"""
        <![CDATA[
        <h2>Tank Compliance Analysis</h2>
        <p>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Total Tanks: {len(df)}</p>
        ]]>
        """

        # Add styles
        for style in create_kml_styles():
            document.append(style)

        # Add legend folder if requested
        if include_legend:
            document.append(create_legend_folder())

        # Create tanks folder
        tanks_folder = SubElement(document, "Folder")
        SubElement(tanks_folder, "name").text = "🏭 Tank Locations"

        # Add placemarks for each tank
        tanks_added = 0
        compliant_count = 0
        non_compliant_count = 0
        review_count = 0

        for _, row in df.iterrows():
            # Extract data
            tank_id = str(row.get("Site Name or Business Name", "Unknown"))
            capacity = str(row.get("Tank Capacity", "Unknown"))
            lat = row.get("Latitude (NAD83)", None)
            lon = row.get("Longitude (NAD83)", None)
            compliance = str(row.get("Compliance", "REVIEW")).upper()
            product = str(row.get("Product Stored", ""))
            distance = row.get("Calculated Distance to Polygon (ft)", None)

            # Parse ASD (might be complex string like "ASDPPU: 351.50 ft, ASDBPU: 65.61 ft")
            asd_raw = row.get("Acceptable Separation Distance Calculated", None)
            asd = None
            if not pd.isna(asd_raw):
                import re
                # Try to extract first number
                match = re.search(r'(\d+\.?\d*)\s*ft', str(asd_raw))
                if match:
                    asd = float(match.group(1))

            measurements = row.get("Tank Measurements", None)

            # Skip if no coordinates
            if pd.isna(lat) or pd.isna(lon):
                continue

            # Track compliance stats
            if compliance in ["YES", "COMPLIANT"]:
                compliant_count += 1
            elif compliance in ["NO", "NON-COMPLIANT"]:
                non_compliant_count += 1
            else:
                review_count += 1

            # Create placemark
            placemark = create_kml_placemark(
                tank_id=tank_id,
                capacity=capacity,
                lat=float(lat),
                lon=float(lon),
                compliance=compliance,
                product=product if not pd.isna(product) else "",
                distance_to_boundary=float(distance) if not pd.isna(distance) else None,
                asd_required=float(asd) if not pd.isna(asd) else None,
                measurements=str(measurements) if not pd.isna(measurements) else None
            )
            tanks_folder.append(placemark)
            tanks_added += 1

        print(f"\n📍 Added {tanks_added} tank locations:")
        print(f"   ✅ Compliant: {compliant_count}")
        print(f"   ❌ Non-compliant: {non_compliant_count}")
        print(f"   ⚠️  Review: {review_count}")

        # Add boundary polygon if provided
        if boundary_coordinates:
            boundary_folder = SubElement(document, "Folder")
            SubElement(boundary_folder, "name").text = "📐 Site Boundary"

            boundary_placemark = create_boundary_polygon(boundary_coordinates)
            boundary_folder.append(boundary_placemark)
            print(f"\n✅ Added boundary polygon ({len(boundary_coordinates)} points)")

        # Convert to pretty XML string
        xml_str = minidom.parseString(tostring(kml, encoding='utf-8')).toprettyxml(indent="  ")

        # Create KMZ (zipped KML)
        output_path = Path(output_kmz)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            kmz.writestr('doc.kml', xml_str)

        print(f"\n✅ Professional KMZ created: {output_path.name}")
        print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")

        return {
            "success": True,
            "output_kmz": str(output_path),
            "tanks_added": tanks_added,
            "compliant": compliant_count,
            "non_compliant": non_compliant_count,
            "review": review_count,
            "message": f"Created professional KMZ with {tanks_added} tanks"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create KMZ: {str(e)}"
        }


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Create professional KMZ with styling and rich descriptions"
    )
    parser.add_argument("compliance_excel", help="Path to compliance Excel file")
    parser.add_argument("-o", "--output", default="professional_output.kmz",
                        help="Output KMZ path")
    parser.add_argument("--boundary", help="JSON file with boundary coordinates")
    parser.add_argument("--no-legend", action="store_true",
                        help="Don't include legend folder")

    args = parser.parse_args()

    # Load boundary if provided
    boundary_coords = None
    if args.boundary:
        with open(args.boundary, 'r') as f:
            boundary_data = json.load(f)
            boundary_coords = [(lon, lat) for lat, lon in boundary_data]

    # Create KMZ
    result = create_professional_kmz(
        args.compliance_excel,
        args.output,
        boundary_coords,
        not args.no_legend
    )

    if result["success"]:
        print(f"\n🎉 Success! Open in Google Earth:")
        print(f"   {result['output_kmz']}")
        return 0
    else:
        print(f"\n❌ Error: {result['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())