#!/usr/bin/env python3
"""
AI Agent-Adjustable Excel to JSON Tool
Allows AI agents to parse, adjust, and correct tank data during conversion
"""

import json
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import re
from datetime import datetime
from enum import Enum

# For tool decorator (works with or without LangChain)
try:
    from langchain_core.tools import tool
    HAS_LANGCHAIN = True
except ImportError:
    # Fallback decorator if LangChain not available
    def tool(func):
        func.is_tool = True
        return func
    HAS_LANGCHAIN = False

# Import volume calculator
try:
    from volume_calculator import VolumeCalculator
    HAS_VOLUME_CALC = True
except ImportError:
    HAS_VOLUME_CALC = False
    print("Warning: volume_calculator not found, using basic calculations")


class ParseMode(str, Enum):
    """Parsing modes for different scenarios"""
    AUTO = "auto"              # Automatic detection
    STRICT = "strict"          # Strict column matching
    FUZZY = "fuzzy"            # Fuzzy column matching
    MANUAL = "manual"          # Manual specification
    AI_GUIDED = "ai_guided"    # AI provides guidance


class ExcelToJsonAgent:
    """Agent-controllable Excel to JSON converter"""

    def __init__(self):
        """Initialize the converter"""
        self.volume_calc = VolumeCalculator() if HAS_VOLUME_CALC else None
        self.column_mappings = self._get_default_mappings()
        self.parse_history = []

    def _get_default_mappings(self) -> Dict[str, List[str]]:
        """Get default column name mappings"""
        return {
            "tank_id": ["tank id", "tank_id", "id", "tank", "name", "tank name", "nombre del tanque"],
            "dimensions": ["dimensions", "tank dimensions", "dimensiones", "size", "medidas"],
            "capacity": ["capacity", "volume", "tank capacity", "capacidad", "volumen"],
            "type": ["type", "tank type", "fuel type", "tipo", "fuel"],
            "has_dike": ["has dike", "dike", "containment", "has_dike", "dique"],
            "dike_dimensions": ["dike dimensions", "dike size", "containment dimensions"],
            "location": ["location", "site", "ubicacion", "coordinates"],
            "notes": ["notes", "comments", "notas", "observaciones"]
        }

    @tool
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
        Parse Excel to JSON with AI-adjustable parameters.

        Args:
            excel_path: Path to Excel file
            mode: Parsing mode (auto/strict/fuzzy/manual/ai_guided)
            sheet_name: Specific sheet to parse (None = auto-detect)
            column_overrides: Manual column mappings {"standard_name": "actual_column"}
            value_corrections: List of corrections [{"tank_id": "T1", "field": "capacity", "value": 50000}]
            parsing_hints: AI hints {"date_format": "MM/DD/YYYY", "units": "gallons", etc}

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

            result["success"] = True
            result["tanks"] = formatted_tanks
            result["metadata"]["tank_count"] = len(formatted_tanks)

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

    def _auto_detect_sheet(self, xl_file: pd.ExcelFile) -> str:
        """Auto-detect the most likely sheet containing tank data"""
        tank_keywords = ["tank", "tanque", "fuel", "diesel", "capacity", "dimension"]

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

        # Detect columns
        column_map = self._detect_columns(df, overrides)

        for idx, row in df.iterrows():
            tank = self._extract_tank_from_row(row, column_map, idx)
            if tank and tank.get("tank_id"):  # Only add if has ID
                tanks.append(tank)

        return tanks

    def _parse_fuzzy(self, df: pd.DataFrame, overrides: Optional[Dict]) -> List[Dict]:
        """Fuzzy parsing with loose matching"""
        tanks = []

        # Use fuzzy matching for columns
        column_map = self._fuzzy_match_columns(df, overrides)

        for idx, row in df.iterrows():
            tank = self._extract_tank_from_row(row, column_map, idx, fuzzy=True)
            if tank:
                tanks.append(tank)

        return tanks

    def _parse_strict(self, df: pd.DataFrame, overrides: Optional[Dict]) -> List[Dict]:
        """Strict parsing requiring exact column matches"""
        tanks = []

        # Require exact matches
        column_map = {}
        for std_name, variations in self.column_mappings.items():
            for col in df.columns:
                if str(col).lower() in variations:
                    column_map[std_name] = col
                    break

        # Apply overrides
        if overrides:
            column_map.update(overrides)

        # Must have minimum required columns
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

        # Use only provided mappings
        column_map = overrides

        for idx, row in df.iterrows():
            tank = {}
            for std_name, actual_col in column_map.items():
                if actual_col in df.columns:
                    value = row[actual_col]
                    if pd.notna(value):
                        tank[std_name] = value

            if tank:
                tanks.append(tank)

        return tanks

    def _parse_ai_guided(self, df: pd.DataFrame, overrides: Optional[Dict], hints: Optional[Dict]) -> List[Dict]:
        """AI-guided parsing using hints and intelligence"""
        tanks = []

        # Start with auto-detection
        column_map = self._detect_columns(df, overrides)

        # Apply AI hints
        if hints:
            # Use hints to refine parsing
            units = hints.get("units", "gallons")
            date_format = hints.get("date_format")
            skip_rows = hints.get("skip_rows", [])

            for idx, row in df.iterrows():
                if idx in skip_rows:
                    continue

                tank = self._extract_tank_from_row(row, column_map, idx)

                # Apply unit conversions if needed
                if tank and units != "gallons":
                    tank = self._convert_units(tank, units, "gallons")

                if tank:
                    tanks.append(tank)
        else:
            # Fallback to auto parsing
            tanks = self._parse_auto(df, overrides)

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

        # Apply overrides
        if overrides:
            column_map.update(overrides)

        return column_map

    def _fuzzy_match_columns(self, df: pd.DataFrame, overrides: Optional[Dict]) -> Dict[str, str]:
        """Fuzzy match columns using similarity"""
        from difflib import SequenceMatcher

        column_map = {}
        threshold = 0.6  # Similarity threshold

        for std_name, variations in self.column_mappings.items():
            best_match = None
            best_score = 0

            for col in df.columns:
                col_lower = str(col).lower().strip()
                for variation in variations:
                    score = SequenceMatcher(None, col_lower, variation).ratio()
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = col

            if best_match:
                column_map[std_name] = best_match

        # Apply overrides
        if overrides:
            column_map.update(overrides)

        return column_map

    def _extract_tank_from_row(self, row: pd.Series, column_map: Dict, idx: int,
                               strict: bool = False, fuzzy: bool = False) -> Optional[Dict]:
        """Extract tank data from a row"""
        tank = {}

        # Extract tank ID (required)
        if "tank_id" in column_map:
            tank_id = row[column_map["tank_id"]]
            if pd.notna(tank_id):
                tank["tank_id"] = str(tank_id).strip()
            elif strict:
                return None  # Skip if no ID in strict mode
            else:
                tank["tank_id"] = f"Tank_{idx+1}"  # Generate ID
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
                tank["type"] = str(tank_type).lower()

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
        return str_val in ["yes", "y", "true", "1", "si", "sí", "x"]

    def _apply_corrections(self, tanks: List[Dict], corrections: List[Dict]) -> List[Dict]:
        """Apply manual corrections to parsed data"""
        for correction in corrections:
            tank_id = correction.get("tank_id")
            field = correction.get("field")
            value = correction.get("value")

            if not tank_id or not field:
                continue

            # Find and update tank
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
                dims_str = tank["dimensions_raw"]

                if self.volume_calc:
                    # Use VolumeCalculator if available
                    result = self.volume_calc.calculate_from_string(dims_str)
                    if result["success"]:
                        tank["volume_gallons"] = result["volume_gallons"]
                        tank["volume_source"] = "calculated"
                else:
                    # Basic parsing
                    volume = self._basic_volume_calc(dims_str)
                    if volume:
                        tank["volume_gallons"] = volume
                        tank["volume_source"] = "estimated"

            # Parse capacity if no calculated volume
            if "volume_gallons" not in tank and "capacity_raw" in tank:
                volume = self._parse_capacity(tank["capacity_raw"])
                if volume:
                    tank["volume_gallons"] = volume
                    tank["volume_source"] = "provided"

        return tanks

    def _basic_volume_calc(self, dims_str: str) -> Optional[float]:
        """Basic volume calculation from dimensions string"""
        import re

        # Try to extract numbers
        numbers = re.findall(r'(\d+(?:\.\d+)?)', dims_str)
        if len(numbers) >= 2:
            # Assume cylindrical tank (diameter x length)
            try:
                diameter = float(numbers[0])
                length = float(numbers[1])
                # Volume in cubic feet
                radius = diameter / 2
                volume_cuft = 3.14159 * radius * radius * length
                # Convert to gallons (1 cubic foot = 7.48 gallons)
                return round(volume_cuft * 7.48, 0)
            except:
                return None
        return None

    def _parse_capacity(self, cap_str: str) -> Optional[float]:
        """Parse capacity string to gallons"""
        import re

        # Extract number
        match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', str(cap_str))
        if match:
            # Remove commas and convert
            try:
                value = float(match.group(1).replace(',', ''))

                # Check for units
                cap_lower = str(cap_str).lower()
                if 'bbl' in cap_lower or 'barrel' in cap_lower:
                    value *= 42  # 1 barrel = 42 gallons
                elif 'liter' in cap_lower or 'litre' in cap_lower:
                    value *= 0.264172  # 1 liter = 0.264172 gallons
                elif 'm3' in cap_lower or 'cubic meter' in cap_lower:
                    value *= 264.172  # 1 m³ = 264.172 gallons

                return round(value, 0)
            except:
                return None
        return None

    def _convert_units(self, tank: Dict, from_unit: str, to_unit: str) -> Dict:
        """Convert volume units"""
        if "volume_gallons" in tank and from_unit != to_unit:
            # Conversion logic here
            pass
        return tank

    def _format_for_hud(self, tanks: List[Dict]) -> List[Dict]:
        """Format tanks for HUD tool compatibility"""
        formatted = []

        for tank in tanks:
            hud_tank = {
                "name": tank.get("tank_id", "Unknown"),
                "capacity": tank.get("volume_gallons", 0),
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

            formatted.append(hud_tank)

        return formatted

    @tool
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

            # Create output structure for HUD
            output_data = {
                "tanks": data.get("tanks", []),
                "metadata": data.get("metadata", {}),
                "timestamp": datetime.now().isoformat()
            }

            # Save to file
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)

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

    @tool
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
            "recommendations": []
        }

        try:
            df = pd.read_excel(excel_path)

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
                if count > len(df) * 0.5:  # More than 50% missing
                    suggestions["data_issues"].append(f"Column '{col}' has {count} missing values")

            # Recommendations
            if not suggestions["column_mappings"].get("tank_id"):
                suggestions["recommendations"].append("Add a column with tank IDs")

            if not suggestions["column_mappings"].get("dimensions") and not suggestions["column_mappings"].get("capacity"):
                suggestions["recommendations"].append("Add either tank dimensions or capacity")

            return suggestions

        except Exception as e:
            return {"error": str(e)}


# Create singleton instance
excel_agent = ExcelToJsonAgent()

# Export tools for use by AI agents
parse_excel_with_adjustments = excel_agent.parse_excel_with_adjustments
save_json_output = excel_agent.save_json_output
suggest_corrections = excel_agent.suggest_corrections


def main():
    """Command-line interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description="AI-adjustable Excel to JSON converter")
    parser.add_argument("excel_file", help="Path to Excel file")
    parser.add_argument("-o", "--output", default="output.json", help="Output JSON file")
    parser.add_argument("-m", "--mode", default="auto",
                       choices=["auto", "strict", "fuzzy", "manual", "ai_guided"],
                       help="Parsing mode")
    parser.add_argument("-s", "--sheet", help="Sheet name to parse")
    parser.add_argument("--suggest", action="store_true", help="Suggest corrections")

    args = parser.parse_args()

    if args.suggest:
        # Get suggestions
        suggestions = suggest_corrections(args.excel_file)
        print(json.dumps(suggestions, indent=2))
    else:
        # Parse Excel
        result = parse_excel_with_adjustments(
            excel_path=args.excel_file,
            mode=args.mode,
            sheet_name=args.sheet
        )

        if result["success"]:
            # Save to file
            save_result = save_json_output(result, args.output)
            if save_result["success"]:
                print(f"✅ Saved {save_result['tank_count']} tanks to {save_result['path']}")
            else:
                print(f"❌ Save failed: {save_result['error']}")
        else:
            print(f"❌ Parse failed: {result.get('error')}")
            print(f"Metadata: {json.dumps(result.get('metadata', {}), indent=2)}")


if __name__ == "__main__":
    main()