#!/usr/bin/env python3
"""
Parse Book 1.xlsx and convert to tank compliance template format.
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any
import re

def extract_tank_id(tank_use: str) -> str:
    """Extract tank ID from tank use description."""
    # Look for patterns like TK-001, T-01, Tank 1, etc.
    patterns = [
        r'(TK-\d+)',
        r'(T-\d+)',
        r'Tank (\d+)',
        r'#(\d+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, tank_use, re.IGNORECASE)
        if match:
            return match.group(1)

    # If no pattern found, create ID from first few words
    words = tank_use.split()[:3]
    return '-'.join(words).replace(' ', '_')[:20]

def extract_capacity(capacity_val) -> float:
    """Extract numeric capacity from various formats."""
    if pd.isna(capacity_val):
        return 0.0

    # If already numeric
    if isinstance(capacity_val, (int, float)):
        return float(capacity_val)

    # Extract number from string
    capacity_str = str(capacity_val)
    match = re.search(r'[\d,]+\.?\d*', capacity_str.replace(',', ''))
    if match:
        return float(match.group())

    return 0.0

def parse_location(location: str) -> Dict[str, Any]:
    """Parse location string to extract coordinates if available."""
    # This would normally extract lat/lon if present
    # For now, return location description
    return {
        "description": str(location) if not pd.isna(location) else "Not specified",
        "latitude": None,
        "longitude": None
    }

def parse_book1_excel(excel_path: str, output_path: str) -> Dict[str, Any]:
    """Parse Book 1.xlsx and create compliance template."""

    print(f"📖 Reading Book 1.xlsx from: {excel_path}")

    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"   Found {len(df)} rows, {len(df.columns)} columns")

    # Display columns for debugging
    print(f"   Columns: {list(df.columns)}")

    # Initialize results
    tanks = []

    # Process each row
    for idx, row in df.iterrows():
        # Skip empty rows
        if pd.isna(row.get('Tank Use', row.get('Tank ID', row.iloc[0] if len(row) > 0 else None))):
            continue

        # Extract tank data
        tank_use = str(row.get('Tank Use', f'Tank-{idx+1}'))
        tank_id = extract_tank_id(tank_use)

        # Create tank record
        tank = {
            "tank_id": tank_id,
            "tank_use": tank_use,
            "capacity_gallons": extract_capacity(row.get('Capacity (gal)', 0)),
            "secondary_containment": str(row.get('Secondary containments', 'None')) if not pd.isna(row.get('Secondary containments')) else None,
            "location": parse_location(row.get('Location', '')),
            "asdppu": str(row.get('ASDPPU', '')) if not pd.isna(row.get('ASDPPU')) else None,
            "row_number": idx + 2,  # Excel row number (accounting for header)
            "status": "active"
        }

        tanks.append(tank)

    # Create compliance template structure
    template = {
        "source_file": excel_path,
        "tank_count": len(tanks),
        "tanks": tanks,
        "metadata": {
            "parsed_date": pd.Timestamp.now().isoformat(),
            "original_columns": list(df.columns),
            "total_capacity_gallons": sum(t["capacity_gallons"] for t in tanks)
        }
    }

    # Save to JSON
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(template, f, indent=2)

    print(f"\n✅ Successfully parsed {len(tanks)} tanks")
    print(f"💾 Saved template to: {output_path}")

    # Print summary
    print("\n📊 Tank Summary:")
    for i, tank in enumerate(tanks[:5], 1):  # Show first 5
        print(f"  {i}. {tank['tank_id']}: {tank['capacity_gallons']:,.0f} gal - {tank['tank_use'][:50]}...")

    if len(tanks) > 5:
        print(f"  ... and {len(tanks) - 5} more tanks")

    print(f"\n💧 Total Capacity: {template['metadata']['total_capacity_gallons']:,.0f} gallons")

    return template

def create_pipeline_ready_excel(template: Dict[str, Any], output_path: str):
    """Create an Excel file ready for pipeline processing."""

    # Prepare data for Excel
    excel_data = []

    for tank in template["tanks"]:
        excel_data.append({
            "Tank ID": tank["tank_id"],
            "Tank Use/Description": tank["tank_use"],
            "Capacity (gallons)": tank["capacity_gallons"],
            "Secondary Containment": tank["secondary_containment"],
            "Location": tank["location"]["description"],
            "ASDPPU": tank["asdppu"],
            "Latitude": tank["location"]["latitude"],
            "Longitude": tank["location"]["longitude"],
            "Status": tank["status"]
        })

    # Create DataFrame
    df = pd.DataFrame(excel_data)

    # Save to Excel
    df.to_excel(output_path, index=False)
    print(f"📝 Created pipeline-ready Excel: {output_path}")

    return output_path

if __name__ == "__main__":
    import sys

    # Input and output paths
    input_excel = "/home/avapc/Appspc/agenttanks/Book 1.xlsx"
    output_json = "book1_template.json"
    output_excel = "book1_pipeline_ready.xlsx"

    if len(sys.argv) > 1:
        input_excel = sys.argv[1]

    # Parse Excel to template
    template = parse_book1_excel(input_excel, output_json)

    # Create pipeline-ready Excel
    create_pipeline_ready_excel(template, output_excel)

    print("\n✨ Ready for pipeline processing!")
    print(f"   JSON template: {output_json}")
    print(f"   Excel template: {output_excel}")