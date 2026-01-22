#!/usr/bin/env python3
"""
Excel Analysis Tool for AI Agents
Provides analysis and options - Agent makes decisions
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import re
import math
from datetime import datetime


class ExcelAnalysisTool:
    """
    Tool that analyzes Excel data and provides options for AI agents.
    Does NOT make decisions - only presents information for agent judgment.
    """

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

    def analyze_excel_for_agent(self, excel_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze Excel and provide all information for agent decision-making.

        Args:
            excel_path: Path to Excel file
            sheet_name: Optional specific sheet to analyze

        Returns:
            Complete analysis with options, NOT decisions
        """
        analysis = {
            "file": excel_path,
            "sheets_available": [],
            "recommended_sheet": None,
            "columns_found": [],
            "column_analysis": {},
            "rows_analyzed": [],
            "metadata": {},
            "success": False
        }

        try:
            # Get available sheets
            xl_file = pd.ExcelFile(excel_path)
            analysis["sheets_available"] = xl_file.sheet_names

            # Analyze each sheet to find best one
            sheet_scores = []
            for sheet in xl_file.sheet_names:
                score = self._analyze_sheet_relevance(xl_file, sheet)
                sheet_scores.append({"sheet": sheet, "score": score})

            # Recommend best sheet
            if sheet_scores:
                best = max(sheet_scores, key=lambda x: x["score"])
                analysis["recommended_sheet"] = best["sheet"]
                analysis["sheet_analysis"] = sheet_scores

                # Use specified sheet or recommended
                target_sheet = sheet_name or best["sheet"]
                df = pd.read_excel(excel_path, sheet_name=target_sheet)
                df = df.dropna(how='all').reset_index(drop=True)

                # Analyze columns
                analysis["columns_found"] = list(df.columns)
                analysis["column_analysis"] = self._analyze_columns(df)

                # Analyze each row and provide conversion options
                for idx, row in df.iterrows():
                    row_analysis = self._analyze_row(row, idx, analysis["column_analysis"])
                    analysis["rows_analyzed"].append(row_analysis)

                # Provide summary statistics
                analysis["metadata"] = {
                    "total_rows": len(df),
                    "non_empty_rows": len([r for r in analysis["rows_analyzed"] if r["has_data"]]),
                    "sheet_used": target_sheet,
                    "timestamp": datetime.now().isoformat()
                }

                analysis["success"] = True

        except Exception as e:
            analysis["error"] = str(e)
            analysis["success"] = False

        return analysis

    def _analyze_sheet_relevance(self, xl_file: pd.ExcelFile, sheet_name: str) -> int:
        """Analyze how relevant a sheet is for tank data"""
        score = 0
        tank_keywords = ["tank", "fuel", "diesel", "capacity", "volume", "dimension", "gallon", "barrel"]

        # Check sheet name
        sheet_lower = sheet_name.lower()
        for keyword in tank_keywords:
            if keyword in sheet_lower:
                score += 10

        # Check content
        try:
            df = pd.read_excel(xl_file, sheet_name=sheet_name, nrows=5)

            # Check column names
            for col in df.columns:
                col_lower = str(col).lower()
                for keyword in tank_keywords:
                    if keyword in col_lower:
                        score += 5

            # Bonus for having numeric data
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            score += len(numeric_cols) * 2

            # Bonus for having data
            if len(df) > 0:
                score += len(df) * 2
        except:
            pass

        return score

    def _analyze_columns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze columns and suggest what they might contain"""
        column_analysis = {}

        for col in df.columns:
            col_lower = str(col).lower()
            analysis = {
                "column_name": col,
                "possible_types": [],
                "sample_values": [],
                "data_type": str(df[col].dtype),
                "has_numeric": False,
                "has_text": False,
                "null_percentage": 0,
                "unique_count": 0
            }

            # Get sample values
            non_null = df[col].dropna()
            if len(non_null) > 0:
                analysis["sample_values"] = [str(v) for v in non_null.head(3).tolist()]
                analysis["has_numeric"] = pd.api.types.is_numeric_dtype(df[col])
                analysis["has_text"] = pd.api.types.is_string_dtype(df[col])
                analysis["null_percentage"] = round((df[col].isnull().sum() / len(df)) * 100, 1)
                analysis["unique_count"] = df[col].nunique()

            # Suggest possible types based on name and content
            if any(x in col_lower for x in ["id", "name", "tank", "number", "no", "code", "identifier"]):
                analysis["possible_types"].append("tank_identifier")

            if any(x in col_lower for x in ["dimension", "size", "measurement", "diameter", "length"]):
                analysis["possible_types"].append("dimensions")

            if any(x in col_lower for x in ["capacity", "volume", "gallon", "barrel", "liter"]):
                analysis["possible_types"].append("volume")

            if any(x in col_lower for x in ["type", "fuel", "product", "material", "content"]):
                analysis["possible_types"].append("tank_type")

            if any(x in col_lower for x in ["dike", "containment", "berm", "secondary"]):
                analysis["possible_types"].append("containment_info")

            if any(x in col_lower for x in ["location", "site", "coordinate", "gps", "position"]):
                analysis["possible_types"].append("location")

            column_analysis[col] = analysis

        return column_analysis

    def _analyze_row(self, row: pd.Series, idx: int, column_analysis: Dict) -> Dict[str, Any]:
        """Analyze a single row and provide all possible interpretations"""
        row_analysis = {
            "row_index": idx,
            "has_data": False,
            "possible_tank_ids": [],
            "measurements_found": [],
            "conversion_possibilities": [],
            "other_data": {}
        }

        # Check if row has any data
        non_null_values = row.dropna()
        if len(non_null_values) == 0:
            return row_analysis

        row_analysis["has_data"] = True

        # Analyze each cell in the row
        for col, value in row.items():
            if pd.isna(value):
                continue

            value_str = str(value).strip()
            col_info = column_analysis.get(col, {})

            # Check if it could be a tank ID
            if "tank_identifier" in col_info.get("possible_types", []):
                confidence = self._assess_id_confidence(value_str)
                row_analysis["possible_tank_ids"].append({
                    "column": col,
                    "value": value_str,
                    "confidence": confidence
                })
            # Also check content even if column name doesn't match
            elif self._looks_like_tank_id(value_str):
                confidence = self._assess_id_confidence(value_str)
                row_analysis["possible_tank_ids"].append({
                    "column": col,
                    "value": value_str,
                    "confidence": confidence
                })

            # Check if it could be measurement/volume
            if any(t in col_info.get("possible_types", []) for t in ["dimensions", "volume"]):
                measurement_analysis = self._analyze_measurement(value_str)
                if measurement_analysis["has_numeric_content"]:
                    row_analysis["measurements_found"].append({
                        "column": col,
                        "raw_value": value_str,
                        "analysis": measurement_analysis
                    })
            # Also check content for measurements
            elif re.search(r'\d+', value_str):
                measurement_analysis = self._analyze_measurement(value_str)
                if measurement_analysis["has_numeric_content"]:
                    row_analysis["measurements_found"].append({
                        "column": col,
                        "raw_value": value_str,
                        "analysis": measurement_analysis
                    })

            # Collect other potentially useful data
            if "tank_type" in col_info.get("possible_types", []):
                row_analysis["other_data"]["tank_type"] = value_str.lower()

            if "containment_info" in col_info.get("possible_types", []):
                row_analysis["other_data"]["has_dike"] = self._parse_boolean(value_str)

            if "location" in col_info.get("possible_types", []):
                row_analysis["other_data"]["location"] = value_str

        # For each measurement, provide conversion possibilities
        for measurement in row_analysis["measurements_found"]:
            possibilities = self._get_conversion_possibilities(measurement["analysis"])
            row_analysis["conversion_possibilities"].append({
                "column": measurement["column"],
                "raw_value": measurement["raw_value"],
                "possibilities": possibilities
            })

        return row_analysis

    def _looks_like_tank_id(self, value: str) -> bool:
        """Check if a value looks like it could be a tank ID"""
        if len(value) > 30:  # Too long for an ID
            return False

        # Common tank ID patterns
        patterns = [
            r'^[Tt]ank',
            r'^T-?\d+',
            r'^[A-Z]{1,3}-?\d+',
            r'^\d{1,4}$'
        ]

        return any(re.match(pattern, value) for pattern in patterns)

    def _assess_id_confidence(self, value: str) -> str:
        """Assess confidence that a value is a tank ID"""
        if re.match(r'^[Tt]ank[-_\s]?\d+$', value):
            return "high"
        elif re.match(r'^[A-Z]{1,3}-?\d+$', value):
            return "high"
        elif re.match(r'^\d{1,4}$', value):
            return "medium"
        elif "tank" in value.lower():
            return "medium"
        else:
            return "low"

    def _analyze_measurement(self, value_str: str) -> Dict[str, Any]:
        """Analyze a potential measurement value"""
        analysis = {
            "raw_value": value_str,
            "has_numeric_content": False,
            "numeric_values_found": [],
            "units_detected": [],
            "patterns_matched": [],
            "interpretations": []
        }

        # Extract all numbers
        numbers = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', value_str)
        if numbers:
            analysis["has_numeric_content"] = True
            # Remove commas and convert to float
            analysis["numeric_values_found"] = [float(n.replace(',', '')) for n in numbers]

        # Detect units
        value_lower = value_str.lower()
        unit_patterns = {
            "gallons": ["gal", "gallon", "gallons"],
            "barrels": ["bbl", "barrel", "barrels"],
            "liters": ["liter", "litre", "l", "liters"],
            "feet": ["ft", "feet", "'", "foot"],
            "meters": ["m", "meter", "metre", "meters"]
        }

        for unit_type, patterns in unit_patterns.items():
            for pattern in patterns:
                # Use word boundaries for better matching
                if re.search(r'\b' + re.escape(pattern) + r'\b', value_lower):
                    if unit_type not in analysis["units_detected"]:
                        analysis["units_detected"].append(unit_type)
                    break

        # Check for dimension patterns
        dimension_patterns = [
            (r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)', "standard_dimension"),
            (r'(\d+(?:\.\d+)?)\s*(?:ft|\')\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:ft|\')?', "dimension_with_units"),
            (r'[Dd](?:ia)?[:\s]*(\d+(?:\.\d+)?)[,\s]+[Ll](?:en)?[:\s]*(\d+(?:\.\d+)?)', "diameter_length_format")
        ]

        for pattern, pattern_name in dimension_patterns:
            match = re.search(pattern, value_str)
            if match:
                analysis["patterns_matched"].append(pattern_name)
                try:
                    dim1 = float(match.group(1))
                    dim2 = float(match.group(2))
                    analysis["interpretations"].append({
                        "type": "cylindrical_dimensions",
                        "diameter": dim1,
                        "length": dim2,
                        "assumed_unit": "feet" if "feet" in analysis["units_detected"] else "feet"
                    })
                except:
                    pass
                break

        # Check for single number that could be volume
        if not analysis["interpretations"] and len(analysis["numeric_values_found"]) == 1:
            value = analysis["numeric_values_found"][0]

            # Could be gallons
            if "gallons" in analysis["units_detected"]:
                analysis["interpretations"].append({
                    "type": "volume_gallons",
                    "value": value,
                    "certainty": "high"
                })
            elif 100 <= value <= 100000 and not analysis["units_detected"]:
                analysis["interpretations"].append({
                    "type": "volume_gallons",
                    "value": value,
                    "certainty": "medium"
                })

            # Could be barrels
            if "barrels" in analysis["units_detected"]:
                analysis["interpretations"].append({
                    "type": "volume_barrels",
                    "value": value,
                    "certainty": "high"
                })
            elif 2 <= value <= 2000 and not analysis["units_detected"]:
                analysis["interpretations"].append({
                    "type": "volume_barrels",
                    "value": value,
                    "certainty": "low"
                })

        return analysis

    def _get_conversion_possibilities(self, measurement_analysis: Dict) -> List[Dict]:
        """Get all possible conversions for a measurement"""
        possibilities = []

        for interpretation in measurement_analysis.get("interpretations", []):
            if interpretation["type"] == "cylindrical_dimensions":
                # Calculate volume from dimensions
                d = interpretation["diameter"]
                l = interpretation["length"]
                radius = d / 2
                volume_cuft = math.pi * radius * radius * l
                volume_gal = volume_cuft * self.conversion_factors['cuft_to_gal']

                possibilities.append({
                    "method": "calculate_from_dimensions",
                    "interpretation": f"{d} ft diameter x {l} ft length",
                    "result_gallons": round(volume_gal, 0),
                    "confidence": "high" if any("dimension" in p for p in measurement_analysis["patterns_matched"]) else "medium",
                    "formula_used": "π × r² × length × 7.48 gal/ft³"
                })

            elif interpretation["type"] == "volume_gallons":
                possibilities.append({
                    "method": "direct_gallons",
                    "interpretation": f"{interpretation['value']} gallons",
                    "result_gallons": interpretation['value'],
                    "confidence": interpretation["certainty"]
                })

            elif interpretation["type"] == "volume_barrels":
                gallons = interpretation['value'] * self.conversion_factors['bbl_to_gal']
                possibilities.append({
                    "method": "convert_from_barrels",
                    "interpretation": f"{interpretation['value']} barrels × 42 gal/bbl",
                    "result_gallons": round(gallons, 0),
                    "confidence": interpretation["certainty"]
                })

        # If no clear interpretation, provide as unknown
        if not possibilities and measurement_analysis["has_numeric_content"]:
            possibilities.append({
                "method": "unknown",
                "interpretation": f"Unable to interpret: {measurement_analysis['raw_value']}",
                "result_gallons": None,
                "confidence": "none",
                "needs_agent_decision": True,
                "numeric_values": measurement_analysis["numeric_values_found"]
            })

        return possibilities

    def _parse_boolean(self, value: Any) -> bool:
        """Parse boolean from various formats"""
        if isinstance(value, bool):
            return value

        str_val = str(value).lower().strip()
        return str_val in ["yes", "y", "true", "1", "si", "sí", "x", "✓"]

    def apply_agent_decisions(
        self,
        analysis: Dict[str, Any],
        decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply agent's decisions to create final tank configuration.

        Args:
            analysis: The analysis from analyze_excel_for_agent
            decisions: Agent's decisions on how to interpret each row
                      [{"row_index": 0, "tank_id": "T-001", "use_conversion": {...}, ...}]

        Returns:
            Final tank configuration based on agent's decisions
        """
        result = {
            "tanks": [],
            "skipped_rows": [],
            "agent_decisions_applied": len(decisions),
            "timestamp": datetime.now().isoformat()
        }

        for decision in decisions:
            row_idx = decision["row_index"]

            # Find the row analysis
            row_analysis = next(
                (r for r in analysis["rows_analyzed"] if r["row_index"] == row_idx),
                None
            )

            if not row_analysis:
                result["skipped_rows"].append(row_idx)
                continue

            # Build tank based on agent's decision
            tank = {
                "name": decision.get("tank_id", f"Tank_{row_idx + 1}"),
                "capacity": 0,
                "type": decision.get("tank_type", "diesel"),
                "hasDike": decision.get("has_dike", False)
            }

            # Apply conversion decision
            if "use_conversion" in decision:
                conversion = decision["use_conversion"]
                if conversion.get("result_gallons"):
                    tank["capacity"] = float(conversion["result_gallons"])
                    tank["_conversion_method"] = conversion.get("method", "agent_decision")

            # Add any agent-provided values
            if "override_capacity" in decision:
                tank["capacity"] = float(decision["override_capacity"])
                tank["_conversion_method"] = "agent_override"

            # Add other data from row analysis if agent didn't override
            if "other_data" in row_analysis and not decision.get("override_all"):
                if "tank_type" in row_analysis["other_data"] and "tank_type" not in decision:
                    tank["type"] = row_analysis["other_data"]["tank_type"]
                if "has_dike" in row_analysis["other_data"] and "has_dike" not in decision:
                    tank["hasDike"] = row_analysis["other_data"]["has_dike"]
                if "location" in row_analysis["other_data"]:
                    tank["location"] = row_analysis["other_data"]["location"]

            # Add agent's reasoning if provided
            if "agent_reasoning" in decision:
                tank["_agent_reasoning"] = decision["agent_reasoning"]

            result["tanks"].append(tank)

        return result


# ==============================================================================
# EXPORTED FUNCTIONS FOR AI AGENTS
# ==============================================================================

def analyze_excel_for_conversion(excel_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze Excel file and provide options for agent to decide on conversions.

    This tool does NOT make decisions - it provides analysis for the agent.

    Args:
        excel_path: Path to Excel file
        sheet_name: Optional specific sheet to analyze

    Returns:
        Complete analysis with all conversion possibilities
    """
    tool = ExcelAnalysisTool()
    return tool.analyze_excel_for_agent(excel_path, sheet_name)


def apply_conversion_decisions(analysis: Dict[str, Any], decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply agent's decisions to create final tank configuration.

    Args:
        analysis: The analysis from analyze_excel_for_conversion
        decisions: Agent's decisions on how to interpret each row

    Returns:
        Final tank configuration
    """
    tool = ExcelAnalysisTool()
    return tool.apply_agent_decisions(analysis, decisions)