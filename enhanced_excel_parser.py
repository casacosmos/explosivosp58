#!/usr/bin/env python3
"""
Enhanced Excel Parser with Multi-Sheet Support
Handles complex Excel files with multiple sheets, merged cells, and flexible column structures.
"""

import pandas as pd
import openpyxl
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import re
import json


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class SheetInfo:
    """Information about an Excel sheet"""
    name: str
    row_count: int
    col_count: int
    has_data: bool
    detected_type: str  # "tanks", "features", "metadata", "empty"
    columns: List[str]
    sample_data: Optional[Dict[str, Any]] = None


@dataclass
class ParsedExcel:
    """Complete parsed Excel structure"""
    file_path: str
    sheet_count: int
    sheets: List[SheetInfo]
    primary_sheet: Optional[str]  # Main data sheet
    tank_data: Optional[pd.DataFrame] = None
    features_data: Optional[pd.DataFrame] = None
    metadata: Dict[str, Any] = None


# ============================================================================
# COLUMN NORMALIZATION
# ============================================================================

# Canonical column names
CANON_NAME = "Site Name or Business Name"
CANON_LAT = "Latitude (NAD83)"
CANON_LON = "Longitude (NAD83)"
CANON_CAPACITY = "Tank Capacity"
CANON_MEASUREMENTS = "Tank Measurements"
CANON_NOTES = "Additional information"
CANON_CONTACT = "Person Contacted"
CANON_COMPLIANCE = "Compliance"
CANON_ASD = "Acceptable Separation Distance Calculated"
CANON_DISTANCE = "Calculated Distance to Polygon (ft)"


def normalize_header(header: str) -> str:
    """Normalize header by removing special chars and lowercasing"""
    s = (header or "").strip().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


# Header alias mapping
HEADER_ALIASES: Dict[str, str] = {
    # Name variations
    "sitenameorbusinessname": CANON_NAME,
    "sitename": CANON_NAME,
    "businessname": CANON_NAME,
    "name": CANON_NAME,
    "facilityname": CANON_NAME,
    "site": CANON_NAME,

    # Coordinates
    "latitude": CANON_LAT,
    "lat": CANON_LAT,
    "latitude(nad83)": CANON_LAT,
    "latitudenad83": CANON_LAT,
    "longitude": CANON_LON,
    "long": CANON_LON,
    "lon": CANON_LON,
    "longitude(nad83)": CANON_LON,
    "longitudenad83": CANON_LON,

    # Tank info
    "tankcapacity": CANON_CAPACITY,
    "capacity": CANON_CAPACITY,
    "tankmeasurements": CANON_MEASUREMENTS,
    "measurements": CANON_MEASUREMENTS,
    "dimensions": CANON_MEASUREMENTS,

    # Compliance
    "compliance": CANON_COMPLIANCE,
    "compliancestatus": CANON_COMPLIANCE,
    "status": CANON_COMPLIANCE,

    # Distances
    "acceptableseparationdistance": CANON_ASD,
    "acceptableseparationdistancecalculated": CANON_ASD,
    "asd": CANON_ASD,
    "calculateddistancetopolygon": CANON_DISTANCE,
    "calculateddistancetopolygonft": CANON_DISTANCE,
    "distance": CANON_DISTANCE,
    "distanceft": CANON_DISTANCE,

    # Other
    "additionalinformation": CANON_NOTES,
    "notes": CANON_NOTES,
    "personcontacted": CANON_CONTACT,
    "contact": CANON_CONTACT,
}


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map DataFrame columns to canonical names using aliases"""
    rename_map = {}

    for col in df.columns:
        normalized = normalize_header(str(col))
        if normalized in HEADER_ALIASES:
            rename_map[col] = HEADER_ALIASES[normalized]

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


# ============================================================================
# SHEET TYPE DETECTION
# ============================================================================

def detect_sheet_type(df: pd.DataFrame, sheet_name: str) -> str:
    """
    Detect the type of data in a sheet.

    Returns: "tanks", "features", "metadata", "empty"
    """
    # Check if empty
    if df.empty or len(df) == 0:
        return "empty"

    # Normalize columns for detection
    norm_cols = [normalize_header(str(col)) for col in df.columns]

    # Check for tank data indicators
    tank_indicators = {'tankcapacity', 'capacity', 'tank', 'latitude', 'longitude'}
    if any(indicator in ''.join(norm_cols) for indicator in tank_indicators):
        # Check if we have actual data (not all NaN)
        if df.iloc[:, 0].notna().sum() > 0:
            return "tanks"

    # Check for features/geometry data
    feature_indicators = {'type', 'coordinates', 'geometry', 'feature'}
    if any(indicator in ''.join(norm_cols) for indicator in feature_indicators):
        return "features"

    # Check if it's just metadata (few rows, no clear structure)
    if len(df) < 5 and df.shape[1] < 3:
        return "metadata"

    # Default: if has data but unknown type
    if df.notna().sum().sum() > 0:
        return "tanks"  # Assume tanks as default

    return "empty"


# ============================================================================
# MULTI-SHEET PARSER
# ============================================================================

def parse_excel_advanced(
    excel_path: str,
    output_json: Optional[str] = None
) -> ParsedExcel:
    """
    Parse Excel file with multi-sheet support and advanced detection.

    Args:
        excel_path: Path to Excel file
        output_json: Optional path to save parsed structure as JSON

    Returns:
        ParsedExcel object with all sheets analyzed
    """
    excel_path_obj = Path(excel_path)

    if not excel_path_obj.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    # Read all sheets
    xl_file = pd.ExcelFile(excel_path)
    sheet_names = xl_file.sheet_names

    print(f"📊 Analyzing Excel file: {excel_path_obj.name}")
    print(f"   Found {len(sheet_names)} sheet(s): {sheet_names}")

    sheets_info = []
    tank_data = None
    features_data = None
    metadata = {}
    primary_sheet = None

    # Analyze each sheet
    for sheet_name in sheet_names:
        print(f"\n📄 Analyzing sheet: '{sheet_name}'")

        # Read sheet
        df = pd.read_excel(excel_path, sheet_name=sheet_name)

        # Detect type
        sheet_type = detect_sheet_type(df, sheet_name)
        has_data = len(df) > 0 and df.notna().sum().sum() > 0

        print(f"   Type: {sheet_type}")
        print(f"   Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"   Has data: {has_data}")

        # Map columns to canonical names
        if has_data and sheet_type in ["tanks", "features"]:
            df = map_columns(df)

        # Create sheet info
        sample_data = None
        if has_data and len(df) > 0:
            # Get first non-empty row as sample
            sample_row = df.iloc[0].to_dict()
            sample_data = {k: v for k, v in sample_row.items() if pd.notna(v)}

        sheet_info = SheetInfo(
            name=sheet_name,
            row_count=len(df),
            col_count=len(df.columns),
            has_data=has_data,
            detected_type=sheet_type,
            columns=df.columns.tolist(),
            sample_data=sample_data
        )
        sheets_info.append(sheet_info)

        # Store appropriate data
        if sheet_type == "tanks" and tank_data is None:
            tank_data = df
            primary_sheet = sheet_name
            print(f"   ✓ Identified as primary tank data sheet")
        elif sheet_type == "features" and features_data is None:
            features_data = df
            print(f"   ✓ Identified as features/geometry sheet")
        elif sheet_type == "metadata":
            # Store metadata
            metadata[sheet_name] = df.to_dict('records')
            print(f"   ✓ Stored as metadata")

    # Create parsed result
    parsed = ParsedExcel(
        file_path=str(excel_path),
        sheet_count=len(sheet_names),
        sheets=sheets_info,
        primary_sheet=primary_sheet,
        tank_data=tank_data,
        features_data=features_data,
        metadata=metadata
    )

    # Print summary
    print(f"\n" + "="*70)
    print(f"📋 Parsing Summary")
    print(f"="*70)
    print(f"Total sheets: {parsed.sheet_count}")
    print(f"Primary data sheet: {parsed.primary_sheet or 'None detected'}")
    if tank_data is not None:
        print(f"Tank records: {len(tank_data)}")
    if features_data is not None:
        print(f"Feature records: {len(features_data)}")
    print(f"="*70)

    # Save to JSON if requested
    if output_json:
        save_parsed_structure(parsed, output_json)

    return parsed


def save_parsed_structure(parsed: ParsedExcel, output_path: str):
    """Save parsed Excel structure to JSON"""

    def convert_to_serializable(obj):
        """Convert non-JSON-serializable objects"""
        if isinstance(obj, (pd.Timestamp, pd.DatetimeTZDtype)):
            return str(obj)
        if pd.isna(obj):
            return None
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        return str(obj)

    structure = {
        "file_path": parsed.file_path,
        "sheet_count": int(parsed.sheet_count),
        "primary_sheet": parsed.primary_sheet,
        "sheets": [
            {
                "name": sheet.name,
                "type": sheet.detected_type,
                "rows": int(sheet.row_count),
                "columns": int(sheet.col_count),
                "has_data": bool(sheet.has_data),
                "column_names": sheet.columns,
                "sample": {k: convert_to_serializable(v) for k, v in sheet.sample_data.items()} if sheet.sample_data else None
            }
            for sheet in parsed.sheets
        ],
        "tank_count": int(len(parsed.tank_data)) if parsed.tank_data is not None else 0,
        "feature_count": int(len(parsed.features_data)) if parsed.features_data is not None else 0
    }

    with open(output_path, 'w') as f:
        json.dump(structure, f, indent=2)

    print(f"\n💾 Saved structure to: {output_path}")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Advanced Excel parser with multi-sheet support"
    )
    parser.add_argument("excel_file", help="Path to Excel file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file for structure"
    )
    parser.add_argument(
        "--export-tanks",
        help="Export tank data to CSV"
    )
    parser.add_argument(
        "--export-features",
        help="Export features to CSV"
    )

    args = parser.parse_args()

    # Parse Excel
    parsed = parse_excel_advanced(args.excel_file, args.output)

    # Export tank data if requested
    if args.export_tanks and parsed.tank_data is not None:
        parsed.tank_data.to_csv(args.export_tanks, index=False)
        print(f"\n✅ Exported tank data to: {args.export_tanks}")

    # Export features if requested
    if args.export_features and parsed.features_data is not None:
        parsed.features_data.to_csv(args.export_features, index=False)
        print(f"\n✅ Exported features to: {args.export_features}")


if __name__ == "__main__":
    main()