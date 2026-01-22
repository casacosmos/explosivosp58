#!/usr/bin/env python3
"""
Standalone Excel to JSON Converter with AI Agent Adjustability
Self-contained version with no external dependencies except pandas
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import re
import math
from datetime import datetime
from enum import Enum
import argparse
import sys


# ==============================================================================
# EMBEDDED VOLUME CALCULATOR
# ==============================================================================

class EmbeddedVolumeCalculator:
    """Embedded volume calculation logic"""

    def __init__(self):
        self.conversion_factors = {
            'gal_to_bbl': 1/42,
            'bbl_to_gal': 42,
            'gal_to_liter': 3.78541,
            'liter_to_gal': 0.264172,
            'cuft_to_gal': 7.48052,
            'm3_to_gal': 264.172,
            'ft_to_m': 0.3048,
            'm_to_ft': 3.28084
        }

    def parse_dimensions(self, dim_str: str) -> Optional[Dict[str, Any]]:
        """Parse dimension string into components"""
        if not dim_str:
            return None

        dim_str = str(dim_str).strip()

        # Common patterns
        patterns = [
            # "10 x 20 ft" or "10x20ft"
            r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|\')?',
            # "10' x 20'" or "10ft x 20ft"
            r'(\d+(?:\.\d+)?)\s*(?:ft|feet|\')\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|\')?',
            # "D:10 L:20" or "Dia:10 Len:20"
            r'[Dd](?:ia)?[:\s]+(\d+(?:\.\d+)?)\s*[,\s]+[Ll](?:en)?[:\s]+(\d+(?:\.\d+)?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, dim_str)
            if match:
                try:
                    dim1 = float(match.group(1))
                    dim2 = float(match.group(2))

                    # Detect units
                    unit = 'ft'  # Default
                    if 'm' in dim_str.lower() and 'ft' not in dim_str.lower():
                        unit = 'm'

                    return {
                        'diameter': dim1,
                        'length': dim2,
                        'unit': unit,
                        'raw': dim_str
                    }
                except:
                    continue

        return None

    def calculate_cylindrical_volume(self, diameter: float, length: float, unit: str = 'ft') -> float:
        """Calculate volume of cylindrical tank in gallons"""
        # Convert to feet if needed
        if unit == 'm':
            diameter = diameter * self.conversion_factors['m_to_ft']
            length = length * self.conversion_factors['m_to_ft']

        # Calculate volume in cubic feet
        radius = diameter / 2
        volume_cuft = math.pi * radius * radius * length

        # Convert to gallons
        volume_gal = volume_cuft * self.conversion_factors['cuft_to_gal']

        return round(volume_gal, 0)

    def parse_capacity(self, cap_str: str) -> Optional[float]:
        """Parse capacity string to gallons"""
        if not cap_str:
            return None

        cap_str = str(cap_str).strip()

        # Extract number
        number_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', cap_str)
        if not number_match:
            return None

        try:
            value = float(number_match.group(1).replace(',', ''))

            # Check for units and convert
            cap_lower = cap_str.lower()
            if 'bbl' in cap_lower or 'barrel' in cap_lower:
                value *= self.conversion_factors['bbl_to_gal']
            elif 'liter' in cap_lower or 'litre' in cap_lower or ' l ' in cap_lower:
                value *= self.conversion_factors['liter_to_gal']
            elif 'm3' in cap_lower or 'cubic meter' in cap_lower:
                value *= self.conversion_factors['m3_to_gal']

            return round(value, 0)
        except:
            return None

    def calculate_from_string(self, input_str: str) -> Dict[str, Any]:
        """Calculate volume from dimension or capacity string"""
        result = {
            'success': False,
            'volume_gallons': 0,
            'method': None
        }

        # Try parsing as dimensions first
        dims = self.parse_dimensions(input_str)
        if dims:
            volume = self.calculate_cylindrical_volume(
                dims['diameter'],
                dims['length'],
                dims.get('unit', 'ft')
            )
            result['success'] = True
            result['volume_gallons'] = volume
            result['method'] = 'calculated_from_dimensions'
            result['dimensions'] = dims
            return result

        # Try parsing as capacity
        capacity = self.parse_capacity(input_str)
        if capacity:
            result['success'] = True
            result['volume_gallons'] = capacity
            result['method'] = 'parsed_from_capacity'
            return result

        return result


# ==============================================================================
# PARSING MODES
# ==============================================================================

class ParseMode(str, Enum):
    """Parsing modes for different scenarios"""
    AUTO = "auto"              # Automatic detection
    STRICT = "strict"          # Strict column matching
    FUZZY = "fuzzy"            # Fuzzy column matching
    MANUAL = "manual"          # Manual specification
    AI_GUIDED = "ai_guided"    # AI provides guidance


# ==============================================================================
# MAIN EXCEL TO JSON AGENT
# ==============================================================================

class StandaloneExcelToJsonAgent:
    """Standalone Excel to JSON converter with AI adjustability"""

    def __init__(self):
        """Initialize the converter"""
        self.volume_calc = EmbeddedVolumeCalculator()
        self.column_mappings = self._get_default_mappings()
        self.parse_history = []

    def _get_default_mappings(self) -> Dict[str, List[str]]:
        """Get default column name mappings"""
        return {
            "tank_id": ["tank id", "tank_id", "id", "tank", "name", "tank name",
                       "nombre del tanque", "tank no", "tank number", "no"],
            "dimensions": ["dimensions", "tank dimensions", "dimensiones", "size",
                          "medidas", "tank size", "diameter x length", "d x l"],
            "capacity": ["capacity", "volume", "tank capacity", "capacidad",
                        "volumen", "gallons", "gal", "barrels", "bbl"],
            "type": ["type", "tank type", "fuel type", "tipo", "fuel",
                    "product", "content", "material"],
            "has_dike": ["has dike", "dike", "containment", "has_dike",
                        "dique", "secondary containment", "berm"],
            "dike_dimensions": ["dike dimensions", "dike size", "containment dimensions",
                               "dike measurements", "berm size"],
            "location": ["location", "site", "ubicacion", "coordinates",
                        "gps", "lat/lon", "position"],
            "notes": ["notes", "comments", "notas", "observaciones",
                     "remarks", "description"]
        }

    def parse_excel_with_adjustments(
        self,
        excel_path: str,
        mode: str = "auto",
        sheet_name: Optional[str] = None,
        column_overrides: Optional[Dict[str, str]] = None,
        value_corrections: Optional[List[Dict[str, Any]]] = None,
        parsing_hints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse Excel to JSON with adjustable parameters.

        Args:
            excel_path: Path to Excel file
            mode: Parsing mode (auto/strict/fuzzy/manual/ai_guided)
            sheet_name: Specific sheet to parse (None = auto-detect)
            column_overrides: Manual column mappings {"standard_name": "actual_column"}
            value_corrections: List of corrections [{"tank_id": "T1", "field": "capacity", "value": 50000}]
            parsing_hints: Hints {"date_format": "MM/DD/YYYY", "units": "gallons", etc}

        Returns:
            Dict with parsed data and metadata
        """
        try:
            result = {
                "success": False,
                "tanks": [],
                "metadata": {},
                "warnings": [],
                "adjustments_applied": []
            }

            # Read Excel file
            excel_path = Path(excel_path)
            if not excel_path.exists():
                result["error"] = f"File not found: {excel_path}"
                return result

            # Load Excel with all sheets
            xl_file = pd.ExcelFile(excel_path)
            available_sheets = xl_file.sheet_names
            result["metadata"]["available_sheets"] = available_sheets

            # Determine which sheet to use
            if sheet_name:
                if sheet_name not in available_sheets:
                    result["error"] = f"Sheet '{sheet_name}' not found. Available: {available_sheets}"
                    return result
                target_sheet = sheet_name
            else:
                # Auto-detect most likely sheet
                target_sheet = self._auto_detect_sheet(xl_file)
                result["metadata"]["auto_selected_sheet"] = target_sheet

            # Read the sheet
            df = pd.read_excel(excel_path, sheet_name=target_sheet)

            # Clean the dataframe
            df = self._clean_dataframe(df)

            result["metadata"]["rows_found"] = len(df)
            result["metadata"]["columns_found"] = list(df.columns)

            # Apply parsing based on mode
            if mode == "auto" or mode == ParseMode.AUTO:
                parsed_data = self._parse_auto(df, column_overrides)
            elif mode == "strict" or mode == ParseMode.STRICT:
                parsed_data = self._parse_strict(df, column_overrides)
            elif mode == "fuzzy" or mode == ParseMode.FUZZY:
                parsed_data = self._parse_fuzzy(df, column_overrides)
            elif mode == "manual" or mode == ParseMode.MANUAL:
                if not column_overrides:
                    result["error"] = "Manual mode requires column_overrides"
                    return result
                parsed_data = self._parse_manual(df, column_overrides)
            elif mode == "ai_guided" or mode == ParseMode.AI_GUIDED:
                parsed_data = self._parse_ai_guided(df, column_overrides, parsing_hints)
            else:
                result["error"] = f"Unknown parsing mode: {mode}"
                return result

            # Apply value corrections if provided
            if value_corrections:
                parsed_data = self._apply_corrections(parsed_data, value_corrections)
                result["adjustments_applied"] = value_corrections

            # Calculate volumes where needed
            parsed_data = self._calculate_volumes(parsed_data, parsing_hints)

            # Format for HUD tool
            formatted_tanks = self._format_for_hud(parsed_data)

            # Add metadata to result
            result["success"] = True
            result["tanks"] = formatted_tanks
            result["metadata"]["tank_count"] = len(formatted_tanks)
            result["metadata"]["parsing_mode"] = mode
            result["metadata"]["timestamp"] = datetime.now().isoformat()

            # Track parsing in history
            self.parse_history.append({
                "timestamp": datetime.now().isoformat(),
                "file": str(excel_path),
                "mode": mode,
                "tank_count": len(formatted_tanks)
            })

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tanks": [],
                "metadata": {"exception": type(e).__name__}
            }

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataframe by removing empty rows and columns"""
        # Remove completely empty rows
        df = df.dropna(how='all')

        # Remove completely empty columns
        df = df.dropna(axis=1, how='all')

        # Reset index
        df = df.reset_index(drop=True)

        return df

    def _auto_detect_sheet(self, xl_file: pd.ExcelFile) -> str:
        """Auto-detect the most likely sheet containing tank data"""
        tank_keywords = ["tank", "tanque", "fuel", "diesel", "capacity",
                        "dimension", "volume", "gallons"]

        best_sheet = None
        best_score = 0

        for sheet in xl_file.sheet_names:
            score = 0

            # Check sheet name
            sheet_lower = sheet.lower()
            for keyword in tank_keywords:
                if keyword in sheet_lower:
                    score += 10

            # Check content (first 5 rows)
            try:
                df = pd.read_excel(xl_file, sheet_name=sheet, nrows=5)

                # Check column names
                for col in df.columns:
                    col_lower = str(col).lower()
                    for keyword in tank_keywords:
                        if keyword in col_lower:
                            score += 5

                # Check if has numeric data (likely volumes/dimensions)
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                score += len(numeric_cols) * 2

                # Check if has data
                if len(df) > 0:
                    score += len(df)
            except:
                continue

            if score > best_score:
                best_score = score
                best_sheet = sheet

        return best_sheet or xl_file.sheet_names[0]

    def _parse_auto(self, df: pd.DataFrame, overrides: Optional[Dict]) -> List[Dict]:
        """Automatic parsing with smart column detection"""
        tanks = []
        column_map = self._detect_columns(df, overrides)

        for idx, row in df.iterrows():
            tank = self._extract_tank_from_row(row, column_map, idx)
            if tank and (tank.get("tank_id") or tank.get("dimensions_raw") or tank.get("capacity_raw")):
                tanks.append(tank)

        return tanks

    def _parse_fuzzy(self, df: pd.DataFrame, overrides: Optional[Dict]) -> List[Dict]:
        """Fuzzy parsing with loose matching"""
        tanks = []
        column_map = self._fuzzy_match_columns(df, overrides)

        for idx, row in df.iterrows():
            tank = self._extract_tank_from_row(row, column_map, idx, fuzzy=True)
            if tank:
                tanks.append(tank)

        return tanks

    def _parse_strict(self, df: pd.DataFrame, overrides: Optional[Dict]) -> List[Dict]:
        """Strict parsing requiring exact column matches"""
        tanks = []
        column_map = {}

        for std_name, variations in self.column_mappings.items():
            for col in df.columns:
                if str(col).lower().strip() in variations:
                    column_map[std_name] = col
                    break

        if overrides:
            column_map.update(overrides)

        if "tank_id" not in column_map:
            raise ValueError("Strict mode requires 'tank_id' column")

        for idx, row in df.iterrows():
            tank = self._extract_tank_from_row(row, column_map, idx, strict=True)
            if tank:
                tanks.append(tank)

        return tanks

    def _parse_manual(self, df: pd.DataFrame, overrides: Dict) -> List[Dict]:
        """Manual parsing with explicit column mappings"""
        tanks = []
        column_map = overrides

        for idx, row in df.iterrows():
            tank = {}
            for std_name, actual_col in column_map.items():
                if actual_col in df.columns:
                    value = row[actual_col]
                    if pd.notna(value):
                        tank[f"{std_name}_raw"] = value

            if tank:
                if not tank.get("tank_id_raw"):
                    tank["tank_id"] = f"Tank_{idx+1}"
                else:
                    tank["tank_id"] = str(tank.pop("tank_id_raw"))
                tanks.append(tank)

        return tanks

    def _parse_ai_guided(self, df: pd.DataFrame, overrides: Optional[Dict], hints: Optional[Dict]) -> List[Dict]:
        """AI-guided parsing using hints and intelligence"""
        tanks = []
        column_map = self._detect_columns(df, overrides)

        # Apply AI hints if provided
        skip_rows = []
        units = "gallons"
        default_type = "diesel"

        if hints:
            skip_rows = hints.get("skip_rows", [])
            units = hints.get("units", "gallons")
            default_type = hints.get("default_type", "diesel")

        for idx, row in df.iterrows():
            if idx in skip_rows:
                continue

            tank = self._extract_tank_from_row(row, column_map, idx)

            # Apply defaults from hints
            if tank:
                if not tank.get("type"):
                    tank["type"] = default_type

                if units != "gallons" and "capacity_raw" in tank:
                    # Convert units if needed
                    tank["capacity_raw"] = f"{tank['capacity_raw']} {units}"

                tanks.append(tank)

        return tanks

    def _detect_columns(self, df: pd.DataFrame, overrides: Optional[Dict]) -> Dict[str, str]:
        """Detect column mappings automatically"""
        column_map = {}

        for std_name, variations in self.column_mappings.items():
            for col in df.columns:
                col_lower = str(col).lower().strip()
                for variation in variations:
                    if variation in col_lower or col_lower in variation:
                        column_map[std_name] = col
                        break
                if std_name in column_map:
                    break

        if overrides:
            column_map.update(overrides)

        return column_map

    def _fuzzy_match_columns(self, df: pd.DataFrame, overrides: Optional[Dict]) -> Dict[str, str]:
        """Fuzzy match columns using similarity"""
        def similarity(s1: str, s2: str) -> float:
            """Simple similarity calculation"""
            s1 = s1.lower()
            s2 = s2.lower()

            if s1 == s2:
                return 1.0

            # Check if one contains the other
            if s1 in s2 or s2 in s1:
                return 0.8

            # Count common words
            words1 = set(s1.split())
            words2 = set(s2.split())
            if words1 and words2:
                common = len(words1.intersection(words2))
                total = max(len(words1), len(words2))
                return common / total

            return 0.0

        column_map = {}
        threshold = 0.6

        for std_name, variations in self.column_mappings.items():
            best_match = None
            best_score = 0

            for col in df.columns:
                col_str = str(col).strip()
                for variation in variations:
                    score = similarity(col_str, variation)
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = col

            if best_match:
                column_map[std_name] = best_match

        if overrides:
            column_map.update(overrides)

        return column_map

    def _extract_tank_from_row(self, row: pd.Series, column_map: Dict, idx: int,
                               strict: bool = False, fuzzy: bool = False) -> Optional[Dict]:
        """Extract tank data from a row"""
        tank = {}

        # Extract tank ID
        if "tank_id" in column_map:
            tank_id = row[column_map["tank_id"]]
            if pd.notna(tank_id):
                tank["tank_id"] = str(tank_id).strip()
            elif strict:
                return None
            else:
                tank["tank_id"] = f"Tank_{idx+1}"
        elif not strict:
            tank["tank_id"] = f"Tank_{idx+1}"
        else:
            return None

        # Extract dimensions
        if "dimensions" in column_map:
            dims = row[column_map["dimensions"]]
            if pd.notna(dims):
                tank["dimensions_raw"] = str(dims)

        # Extract capacity
        if "capacity" in column_map:
            cap = row[column_map["capacity"]]
            if pd.notna(cap):
                tank["capacity_raw"] = str(cap)

        # Extract type
        if "type" in column_map:
            tank_type = row[column_map["type"]]
            if pd.notna(tank_type):
                tank["type"] = str(tank_type).lower().strip()

        # Extract dike info
        if "has_dike" in column_map:
            has_dike = row[column_map["has_dike"]]
            if pd.notna(has_dike):
                tank["has_dike"] = self._parse_boolean(has_dike)

        # Extract dike dimensions
        if "dike_dimensions" in column_map:
            dike_dims = row[column_map["dike_dimensions"]]
            if pd.notna(dike_dims):
                tank["dike_dimensions_raw"] = str(dike_dims)

        # Extract location
        if "location" in column_map:
            loc = row[column_map["location"]]
            if pd.notna(loc):
                tank["location"] = str(loc)

        # Extract notes
        if "notes" in column_map:
            notes = row[column_map["notes"]]
            if pd.notna(notes):
                tank["notes"] = str(notes)

        return tank if tank else None

    def _parse_boolean(self, value: Any) -> bool:
        """Parse boolean from various formats"""
        if isinstance(value, bool):
            return value

        str_val = str(value).lower().strip()
        return str_val in ["yes", "y", "true", "1", "si", "sí", "x", "✓", "√"]

    def _apply_corrections(self, tanks: List[Dict], corrections: List[Dict]) -> List[Dict]:
        """Apply manual corrections to parsed data"""
        for correction in corrections:
            tank_id = correction.get("tank_id")
            field = correction.get("field")
            value = correction.get("value")

            if not tank_id or not field:
                continue

            for tank in tanks:
                if tank.get("tank_id") == tank_id:
                    tank[field] = value
                    tank["corrected"] = True
                    break

        return tanks

    def _calculate_volumes(self, tanks: List[Dict], hints: Optional[Dict]) -> List[Dict]:
        """Calculate volumes from dimensions"""
        for tank in tanks:
            # Skip if already has volume
            if "volume_gallons" in tank:
                continue

            # Try to calculate from dimensions
            if "dimensions_raw" in tank:
                result = self.volume_calc.calculate_from_string(tank["dimensions_raw"])
                if result["success"]:
                    tank["volume_gallons"] = result["volume_gallons"]
                    tank["volume_source"] = "calculated"
                    if "dimensions" in result:
                        tank["parsed_dimensions"] = result["dimensions"]

            # Parse capacity if no calculated volume
            if "volume_gallons" not in tank and "capacity_raw" in tank:
                volume = self.volume_calc.parse_capacity(tank["capacity_raw"])
                if volume:
                    tank["volume_gallons"] = volume
                    tank["volume_source"] = "provided"

            # Set default if still no volume
            if "volume_gallons" not in tank:
                tank["volume_gallons"] = 0
                tank["volume_source"] = "missing"

        return tanks

    def _format_for_hud(self, tanks: List[Dict]) -> List[Dict]:
        """Format tanks for HUD tool compatibility"""
        formatted = []

        for tank in tanks:
            hud_tank = {
                "name": tank.get("tank_id", "Unknown"),
                "capacity": float(tank.get("volume_gallons", 0)),
                "type": tank.get("type", "diesel"),
                "hasDike": tank.get("has_dike", False)
            }

            # Add optional fields
            if "location" in tank:
                hud_tank["location"] = tank["location"]
            if "notes" in tank:
                hud_tank["notes"] = tank["notes"]
            if "dike_dimensions_raw" in tank:
                hud_tank["dikeDimensions"] = tank["dike_dimensions_raw"]

            # Add metadata
            hud_tank["_metadata"] = {
                "volume_source": tank.get("volume_source", "unknown"),
                "corrected": tank.get("corrected", False)
            }

            formatted.append(hud_tank)

        return formatted

    def save_json_output(self, data: Dict[str, Any], output_path: str) -> Dict[str, Any]:
        """
        Save parsed data to JSON file.

        Args:
            data: Parsed tank data
            output_path: Output JSON file path

        Returns:
            Dict with save status
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create output structure
            output_data = {
                "tanks": data.get("tanks", []),
                "metadata": data.get("metadata", {}),
                "timestamp": datetime.now().isoformat()
            }

            # Save to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "path": str(output_path),
                "tank_count": len(output_data["tanks"])
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def suggest_corrections(self, excel_path: str) -> Dict[str, Any]:
        """
        Analyze Excel and suggest corrections/improvements.

        Args:
            excel_path: Path to Excel file

        Returns:
            Dict with suggestions for improving parsing
        """
        suggestions = {
            "column_mappings": {},
            "data_issues": [],
            "recommendations": [],
            "sample_data": {}
        }

        try:
            df = pd.read_excel(excel_path)
            df = self._clean_dataframe(df)

            # Suggest column mappings
            for col in df.columns:
                col_lower = str(col).lower()
                for std_name, variations in self.column_mappings.items():
                    for var in variations:
                        if var in col_lower:
                            suggestions["column_mappings"][std_name] = col
                            break

            # Check for data issues
            if df.empty:
                suggestions["data_issues"].append("No data found in Excel")

            # Check for missing values
            null_counts = df.isnull().sum()
            for col, count in null_counts.items():
                if count > len(df) * 0.5:
                    suggestions["data_issues"].append(f"Column '{col}' has {count}/{len(df)} missing values")

            # Sample data
            if len(df) > 0:
                sample = df.head(3).to_dict(orient='records')
                suggestions["sample_data"] = sample

            # Recommendations
            if not suggestions["column_mappings"].get("tank_id"):
                suggestions["recommendations"].append("Add a column with tank IDs")

            if not suggestions["column_mappings"].get("dimensions") and not suggestions["column_mappings"].get("capacity"):
                suggestions["recommendations"].append("Add either tank dimensions or capacity")

            suggestions["success"] = True
            return suggestions

        except Exception as e:
            return {"success": False, "error": str(e)}


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

# Create singleton instance
_agent = StandaloneExcelToJsonAgent()

def parse_excel_with_adjustments(
    excel_path: str,
    mode: str = "auto",
    sheet_name: Optional[str] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    value_corrections: Optional[List[Dict[str, Any]]] = None,
    parsing_hints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Standalone function for parsing Excel with adjustments"""
    return _agent.parse_excel_with_adjustments(
        excel_path, mode, sheet_name, column_overrides,
        value_corrections, parsing_hints
    )

def save_json_output(data: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """Standalone function for saving JSON output"""
    return _agent.save_json_output(data, output_path)

def suggest_corrections(excel_path: str) -> Dict[str, Any]:
    """Standalone function for suggesting corrections"""
    return _agent.suggest_corrections(excel_path)


# ==============================================================================
# COMMAND-LINE INTERFACE
# ==============================================================================

def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Standalone Excel to JSON converter with AI adjustability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python excel_to_json_standalone.py tanks.xlsx

  # Specify output file
  python excel_to_json_standalone.py tanks.xlsx -o output.json

  # Use fuzzy mode for non-standard columns
  python excel_to_json_standalone.py tanks.xlsx -m fuzzy

  # Get suggestions for column mappings
  python excel_to_json_standalone.py tanks.xlsx --suggest

  # Use specific sheet
  python excel_to_json_standalone.py tanks.xlsx -s "Sheet2"

  # Apply corrections from file
  python excel_to_json_standalone.py tanks.xlsx --corrections fixes.json
        """
    )

    parser.add_argument("excel_file", help="Path to Excel file")
    parser.add_argument("-o", "--output", default="tank_config.json",
                       help="Output JSON file (default: tank_config.json)")
    parser.add_argument("-m", "--mode", default="auto",
                       choices=["auto", "strict", "fuzzy", "manual", "ai_guided"],
                       help="Parsing mode (default: auto)")
    parser.add_argument("-s", "--sheet", help="Sheet name to parse")
    parser.add_argument("--suggest", action="store_true",
                       help="Suggest corrections and column mappings")
    parser.add_argument("--corrections", help="JSON file with corrections")
    parser.add_argument("--mappings", help="JSON file with column mappings")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    # Check file exists
    if not Path(args.excel_file).exists():
        print(f"❌ Error: File not found: {args.excel_file}")
        sys.exit(1)

    if args.suggest:
        # Get suggestions
        print(f"📋 Analyzing {args.excel_file}...")
        suggestions = suggest_corrections(args.excel_file)

        if suggestions.get("success"):
            print("\n✅ Analysis Complete\n")

            if suggestions.get("column_mappings"):
                print("📊 Detected Column Mappings:")
                for std, actual in suggestions["column_mappings"].items():
                    print(f"  {std:20} → {actual}")

            if suggestions.get("data_issues"):
                print("\n⚠️  Data Issues:")
                for issue in suggestions["data_issues"]:
                    print(f"  - {issue}")

            if suggestions.get("recommendations"):
                print("\n💡 Recommendations:")
                for rec in suggestions["recommendations"]:
                    print(f"  - {rec}")

            if suggestions.get("sample_data"):
                print("\n📄 Sample Data (first 3 rows):")
                print(json.dumps(suggestions["sample_data"], indent=2))
        else:
            print(f"❌ Analysis failed: {suggestions.get('error')}")

        sys.exit(0)

    # Load corrections if provided
    corrections = None
    if args.corrections:
        try:
            with open(args.corrections) as f:
                corrections = json.load(f)
                print(f"📝 Loaded {len(corrections)} corrections")
        except Exception as e:
            print(f"⚠️  Failed to load corrections: {e}")

    # Load mappings if provided
    mappings = None
    if args.mappings:
        try:
            with open(args.mappings) as f:
                mappings = json.load(f)
                print(f"🗺️  Loaded column mappings")
        except Exception as e:
            print(f"⚠️  Failed to load mappings: {e}")

    # Parse Excel
    print(f"📄 Parsing {args.excel_file} with {args.mode} mode...")

    result = parse_excel_with_adjustments(
        excel_path=args.excel_file,
        mode=args.mode,
        sheet_name=args.sheet,
        column_overrides=mappings,
        value_corrections=corrections
    )

    if result["success"]:
        # Save to file
        save_result = save_json_output(result, args.output)

        if save_result["success"]:
            print(f"✅ Success!")
            print(f"   Tanks parsed: {save_result['tank_count']}")
            print(f"   Output file: {save_result['path']}")

            if args.verbose and result.get("metadata"):
                print("\n📊 Metadata:")
                for key, value in result["metadata"].items():
                    if key != "columns_found":  # Skip long column list
                        print(f"   {key}: {value}")
        else:
            print(f"❌ Save failed: {save_result['error']}")
            sys.exit(1)
    else:
        print(f"❌ Parse failed: {result.get('error')}")
        if result.get("metadata"):
            print(f"   Metadata: {json.dumps(result['metadata'], indent=2)}")
        sys.exit(1)


if __name__ == "__main__":
    main()