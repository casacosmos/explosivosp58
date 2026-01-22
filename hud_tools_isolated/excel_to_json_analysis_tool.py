#!/usr/bin/env python3
"""
Excel to JSON Analysis Tool
Provides analysis and options for AI agents to make decisions
The TOOL analyzes - the AGENT decides
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import re
import math
from datetime import datetime


# ==============================================================================
# ANALYSIS TOOL - NO DECISIONS, ONLY ANALYSIS
# ==============================================================================

class ExcelAnalysisTool:
    """
    Tool that analyzes Excel data and provides options for the agent.
    Does NOT make decisions - only presents information.
    """

    def __init__(self):
        self.conversion_factors = {
            'gal_to_bbl': 1/42,
            'bbl_to_gal': 42,
            'gal_to_liter': 3.78541,
            'liter_to_gal': 0.264172,
            'cuft_to_gal': 7.48052,
            'm3_to_gal': 264.172
        }

    def analyze_excel_for_agent(self, excel_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze Excel and provide all information for agent decision-making.

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
            "conversion_options": [],
            "metadata": {}
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
                row_analysis = self._analyze_row(row, idx)
                analysis["rows_analyzed"].append(row_analysis)

            # Provide summary statistics
            analysis["metadata"] = {
                "total_rows": len(df),
                "non_empty_rows": len([r for r in analysis["rows_analyzed"] if r["has_data"]]),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_sheet_relevance(self, xl_file: pd.ExcelFile, sheet_name: str) -> int:
        """Analyze how relevant a sheet is for tank data"""
        score = 0
        tank_keywords = ["tank", "fuel", "diesel", "capacity", "volume", "dimension"]

        # Check sheet name
        sheet_lower = sheet_name.lower()
        for keyword in tank_keywords:
            if keyword in sheet_lower:
                score += 10

        # Check content
        try:
            df = pd.read_excel(xl_file, sheet_name=sheet_name, nrows=5)
            for col in df.columns:
                col_lower = str(col).lower()
                for keyword in tank_keywords:
                    if keyword in col_lower:
                        score += 5

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
                "has_numeric": False,
                "has_text": False,
                "null_percentage": 0
            }

            # Get sample values
            non_null = df[col].dropna()
            if len(non_null) > 0:
                analysis["sample_values"] = non_null.head(3).tolist()
                analysis["has_numeric"] = pd.api.types.is_numeric_dtype(df[col])
                analysis["has_text"] = pd.api.types.is_string_dtype(df[col])
                analysis["null_percentage"] = (df[col].isnull().sum() / len(df)) * 100

            # Suggest possible types based on name
            if any(x in col_lower for x in ["id", "name", "tank", "number", "no"]):
                analysis["possible_types"].append("tank_identifier")

            if any(x in col_lower for x in ["dimension", "size", "measurement"]):
                analysis["possible_types"].append("dimensions")

            if any(x in col_lower for x in ["capacity", "volume", "gallon", "barrel"]):
                analysis["possible_types"].append("volume")

            if any(x in col_lower for x in ["type", "fuel", "product"]):
                analysis["possible_types"].append("tank_type")

            if any(x in col_lower for x in ["dike", "containment", "berm"]):
                analysis["possible_types"].append("containment_info")

            column_analysis[col] = analysis

        return column_analysis

    def _analyze_row(self, row: pd.Series, idx: int) -> Dict[str, Any]:
        """Analyze a single row and provide all possible interpretations"""
        row_analysis = {
            "row_index": idx,
            "has_data": False,
            "possible_tank_ids": [],
            "measurements_found": [],
            "conversion_possibilities": []
        }

        # Check if row has any data
        non_null_values = row.dropna()
        if len(non_null_values) > 0:
            row_analysis["has_data"] = True

        # Find possible tank IDs
        for col, value in row.items():
            if pd.notna(value):
                value_str = str(value).strip()

                # Could be tank ID if it's short and has letters/numbers
                if len(value_str) < 20 and (
                    re.search(r'[Tt]ank', value_str) or
                    re.search(r'^[A-Z]-?\d+', value_str) or
                    re.search(r'^\d+$', value_str)
                ):
                    row_analysis["possible_tank_ids"].append({
                        "column": col,
                        "value": value_str,
                        "confidence": self._assess_id_confidence(value_str)
                    })

                # Could be measurement/volume
                if re.search(r'\d+', value_str):
                    measurement_analysis = self._analyze_measurement(value_str)
                    if measurement_analysis["has_numeric_content"]:
                        row_analysis["measurements_found"].append({
                            "column": col,
                            "raw_value": value_str,
                            "analysis": measurement_analysis
                        })

        # For each measurement, provide conversion possibilities
        for measurement in row_analysis["measurements_found"]:
            possibilities = self._get_conversion_possibilities(measurement["analysis"])
            row_analysis["conversion_possibilities"].append({
                "column": measurement["column"],
                "raw_value": measurement["raw_value"],
                "possibilities": possibilities
            })

        return row_analysis

    def _assess_id_confidence(self, value: str) -> str:
        """Assess confidence that a value is a tank ID"""
        if re.match(r'^[Tt]ank[-_\s]?\d+$', value):
            return "high"
        elif re.match(r'^[A-Z]{1,3}-?\d+$', value):
            return "high"
        elif re.match(r'^\d{1,4}$', value):
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
        numbers = re.findall(r'(\d+(?:\.\d+)?)', value_str)
        if numbers:
            analysis["has_numeric_content"] = True
            analysis["numeric_values_found"] = [float(n) for n in numbers]

        # Detect units
        value_lower = value_str.lower()
        unit_patterns = {
            "gallons": ["gal", "gallon"],
            "barrels": ["bbl", "barrel"],
            "liters": ["liter", "litre", "l"],
            "feet": ["ft", "feet", "'"],
            "meters": ["m", "meter", "metre"]
        }

        for unit_type, patterns in unit_patterns.items():
            for pattern in patterns:
                if pattern in value_lower:
                    analysis["units_detected"].append(unit_type)
                    break

        # Check for dimension patterns
        if re.search(r'\d+\s*[xX×]\s*\d+', value_str):
            analysis["patterns_matched"].append("dimension_pattern")
            if len(analysis["numeric_values_found"]) >= 2:
                analysis["interpretations"].append({
                    "type": "cylindrical_dimensions",
                    "diameter": analysis["numeric_values_found"][0],
                    "length": analysis["numeric_values_found"][1],
                    "assumed_unit": "feet" if "feet" in analysis["units_detected"] else "feet"
                })

        # Check for single number that could be volume
        elif len(analysis["numeric_values_found"]) == 1:
            value = analysis["numeric_values_found"][0]

            # Could be gallons
            if "gallons" in analysis["units_detected"] or (100 <= value <= 100000):
                analysis["interpretations"].append({
                    "type": "volume_gallons",
                    "value": value,
                    "certainty": "high" if "gallons" in analysis["units_detected"] else "medium"
                })

            # Could be barrels
            if "barrels" in analysis["units_detected"] or (2 <= value <= 2000):
                analysis["interpretations"].append({
                    "type": "volume_barrels",
                    "value": value,
                    "certainty": "high" if "barrels" in analysis["units_detected"] else "low"
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
                    "confidence": "high" if "dimension_pattern" in measurement_analysis["patterns_matched"] else "medium"
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
                    "interpretation": f"{interpretation['value']} barrels",
                    "result_gallons": round(gallons, 0),
                    "confidence": interpretation["certainty"]
                })

        # If no clear interpretation, provide as unknown
        if not possibilities and measurement_analysis["has_numeric_content"]:
            possibilities.append({
                "method": "unknown",
                "interpretation": "Unable to determine unit or type",
                "result_gallons": None,
                "confidence": "none",
                "needs_agent_decision": True
            })

        return possibilities

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
            "agent_decisions_applied": len(decisions)
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
                    tank["capacity"] = conversion["result_gallons"]
                    tank["_conversion_method"] = conversion.get("method", "agent_decision")

            # Add any agent-provided values
            if "override_capacity" in decision:
                tank["capacity"] = decision["override_capacity"]
                tank["_conversion_method"] = "agent_override"

            # Add agent's reasoning if provided
            if "agent_reasoning" in decision:
                tank["_agent_reasoning"] = decision["agent_reasoning"]

            result["tanks"].append(tank)

        return result


# ==============================================================================
# TOOL FUNCTIONS FOR AGENTS
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


# ==============================================================================
# EXAMPLE AGENT USAGE
# ==============================================================================

class ExampleAgent:
    """
    Example of how an AI agent would use this tool to make decisions.
    """

    def process_excel(self, excel_path: str) -> Dict[str, Any]:
        """
        Example agent workflow using the analysis tool.
        """
        print("🤖 Agent: Analyzing Excel file...")

        # Step 1: Get analysis from tool
        analysis = analyze_excel_for_conversion(excel_path)

        print(f"📊 Found {len(analysis['rows_analyzed'])} rows to process")

        # Step 2: Agent makes decisions for each row
        decisions = []

        for row in analysis["rows_analyzed"]:
            if not row["has_data"]:
                continue

            decision = {
                "row_index": row["row_index"],
                "agent_reasoning": []
            }

            # Agent decides on tank ID
            if row["possible_tank_ids"]:
                # Agent picks the highest confidence ID
                best_id = max(row["possible_tank_ids"], key=lambda x:
                             {"high": 3, "medium": 2, "low": 1}[x["confidence"]])
                decision["tank_id"] = best_id["value"]
                decision["agent_reasoning"].append(f"Selected tank ID: {best_id['value']}")
            else:
                decision["tank_id"] = f"Tank_{row['row_index'] + 1}"
                decision["agent_reasoning"].append("Generated tank ID")

            # Agent decides on conversion
            if row["conversion_possibilities"]:
                for possibility in row["conversion_possibilities"]:
                    conversions = possibility["possibilities"]

                    if conversions:
                        # Agent's logic: prefer high confidence conversions
                        high_conf = [c for c in conversions if c["confidence"] == "high"]
                        medium_conf = [c for c in conversions if c["confidence"] == "medium"]

                        if high_conf:
                            # Use high confidence conversion
                            decision["use_conversion"] = high_conf[0]
                            decision["agent_reasoning"].append(
                                f"Using high-confidence conversion: {high_conf[0]['interpretation']}"
                            )
                        elif medium_conf:
                            # Use medium confidence with note
                            decision["use_conversion"] = medium_conf[0]
                            decision["agent_reasoning"].append(
                                f"Using medium-confidence conversion: {medium_conf[0]['interpretation']} (needs verification)"
                            )
                        else:
                            # Agent must decide what to do with low confidence
                            if conversions[0].get("needs_agent_decision"):
                                # Agent makes judgment based on context
                                raw_value = possibility["raw_value"]

                                # Example agent logic: if it's a big number, assume gallons
                                try:
                                    num = float(re.search(r'\d+', raw_value).group())
                                    if num > 1000:
                                        decision["override_capacity"] = num
                                        decision["agent_reasoning"].append(
                                            f"Assumed {num} is gallons based on magnitude"
                                        )
                                except:
                                    decision["agent_reasoning"].append(
                                        f"Could not interpret: {raw_value}"
                                    )

            decisions.append(decision)

        print(f"🎯 Agent made {len(decisions)} decisions")

        # Step 3: Apply agent's decisions
        result = apply_conversion_decisions(analysis, decisions)

        print(f"✅ Created {len(result['tanks'])} tanks")

        return result


# ==============================================================================
# MAIN - FOR TESTING
# ==============================================================================

def main():
    """Test/demo the tool"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python excel_to_json_analysis_tool.py <excel_file>")
        sys.exit(1)

    excel_file = sys.argv[1]

    # Show what the tool provides (no decisions)
    print("="*60)
    print("TOOL OUTPUT (Analysis Only)")
    print("="*60)

    analysis = analyze_excel_for_conversion(excel_file)

    print(f"\n📁 File: {analysis['file']}")
    print(f"📊 Sheets: {analysis['sheets_available']}")
    print(f"✨ Recommended sheet: {analysis['recommended_sheet']}")
    print(f"📋 Columns found: {len(analysis['columns_found'])}")

    print("\n🔍 Sample Row Analysis:")
    for row in analysis["rows_analyzed"][:3]:
        if row["has_data"]:
            print(f"\nRow {row['row_index']}:")
            print(f"  Possible IDs: {[id['value'] for id in row['possible_tank_ids']]}")

            for conv in row["conversion_possibilities"]:
                print(f"  Column '{conv['column']}': {conv['raw_value']}")
                for poss in conv["possibilities"]:
                    print(f"    → {poss['interpretation']} = {poss['result_gallons']} gal ({poss['confidence']} confidence)")

    # Now show agent usage
    print("\n" + "="*60)
    print("AGENT USAGE (Making Decisions)")
    print("="*60)

    agent = ExampleAgent()
    result = agent.process_excel(excel_file)

    print("\n📊 Final tanks created by agent:")
    for tank in result["tanks"][:5]:
        print(f"  {tank['name']}: {tank.get('capacity', 0):.0f} gallons")
        if "_agent_reasoning" in tank:
            for reason in tank["_agent_reasoning"]:
                print(f"    → {reason}")


if __name__ == "__main__":
    main()