#!/usr/bin/env python3
"""
Intelligent Excel to JSON Converter with Agent Decision-Making
The agent judges when and how to convert measurements to volumes
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import re
import math
from datetime import datetime
from enum import Enum


# ==============================================================================
# CONVERSION DECISION TYPES
# ==============================================================================

class ConversionDecision(str, Enum):
    """Agent's decision on how to handle measurements"""
    CONVERT = "convert"              # Definitely convert to volume
    KEEP_AS_IS = "keep_as_is"       # Keep original measurement
    NEEDS_CLARIFICATION = "clarify" # Ask for clarification
    CALCULATE = "calculate"          # Calculate from dimensions
    INFER = "infer"                 # Infer from context
    SKIP = "skip"                   # Skip this tank


class ConfidenceLevel(str, Enum):
    """Confidence in conversion decision"""
    HIGH = "high"           # 90-100% confident
    MEDIUM = "medium"       # 60-90% confident
    LOW = "low"            # 30-60% confident
    UNCERTAIN = "uncertain" # <30% confident


# ==============================================================================
# INTELLIGENT VOLUME CALCULATOR WITH JUDGMENT
# ==============================================================================

class IntelligentVolumeCalculator:
    """Volume calculator that makes intelligent decisions"""

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
        self.decision_log = []

    def analyze_measurement(self, measurement_str: str, context: Dict = None) -> Dict[str, Any]:
        """
        Analyze a measurement and decide how to handle it.

        Args:
            measurement_str: The measurement string
            context: Additional context (tank_id, type, location, etc.)

        Returns:
            Dict with decision, confidence, reasoning, and result
        """
        result = {
            "original": measurement_str,
            "decision": ConversionDecision.SKIP,
            "confidence": ConfidenceLevel.UNCERTAIN,
            "reasoning": [],
            "volume_gallons": None,
            "warnings": [],
            "suggestions": []
        }

        if not measurement_str or pd.isna(measurement_str):
            result["decision"] = ConversionDecision.SKIP
            result["reasoning"].append("No measurement provided")
            return result

        measurement_str = str(measurement_str).strip()

        # Check if it's already a volume
        if self._is_volume(measurement_str):
            result["decision"] = ConversionDecision.KEEP_AS_IS
            result["confidence"] = ConfidenceLevel.HIGH
            volume = self._parse_volume(measurement_str)
            if volume:
                result["volume_gallons"] = volume
                result["reasoning"].append(f"Recognized as volume: {volume:.0f} gallons")
            return result

        # Check if it's dimensions
        if self._is_dimensions(measurement_str):
            # Analyze dimension quality
            dim_analysis = self._analyze_dimensions(measurement_str)

            if dim_analysis["confidence"] == ConfidenceLevel.HIGH:
                result["decision"] = ConversionDecision.CALCULATE
                result["confidence"] = ConfidenceLevel.HIGH
                result["volume_gallons"] = dim_analysis["volume"]
                result["reasoning"].append(f"Clear cylindrical dimensions: {dim_analysis['diameter']} x {dim_analysis['length']} ft")

            elif dim_analysis["confidence"] == ConfidenceLevel.MEDIUM:
                result["decision"] = ConversionDecision.CALCULATE
                result["confidence"] = ConfidenceLevel.MEDIUM
                result["volume_gallons"] = dim_analysis["volume"]
                result["reasoning"].append("Dimensions appear valid but may need verification")
                result["warnings"].append(f"Please verify: {measurement_str} interpreted as diameter x length")

            else:
                result["decision"] = ConversionDecision.NEEDS_CLARIFICATION
                result["confidence"] = ConfidenceLevel.LOW
                result["reasoning"].append(f"Ambiguous dimensions: {measurement_str}")
                result["suggestions"].append("Specify format as 'diameter x length ft'")

            return result

        # Check if we can infer from context
        if context:
            inference = self._infer_from_context(measurement_str, context)
            if inference["success"]:
                result["decision"] = ConversionDecision.INFER
                result["confidence"] = inference["confidence"]
                result["volume_gallons"] = inference["volume"]
                result["reasoning"] = inference["reasoning"]
                return result

        # Unable to determine
        result["decision"] = ConversionDecision.NEEDS_CLARIFICATION
        result["confidence"] = ConfidenceLevel.UNCERTAIN
        result["reasoning"].append(f"Cannot interpret: {measurement_str}")
        result["suggestions"].append("Please provide as 'diameter x length ft' or 'capacity gallons'")

        return result

    def _is_volume(self, text: str) -> bool:
        """Check if text represents a volume"""
        volume_indicators = ['gal', 'gallon', 'bbl', 'barrel', 'liter', 'litre', 'm3', 'cubic']
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in volume_indicators)

    def _is_dimensions(self, text: str) -> bool:
        """Check if text represents dimensions"""
        # Look for patterns like "10 x 20", "10x20", "D:10 L:20"
        patterns = [
            r'\d+\s*[xX×]\s*\d+',  # Basic dimension pattern
            r'[Dd](?:ia)?[:\s]+\d+',  # Diameter notation
            r'\d+\s*(?:ft|feet|m|meter|\')',  # With units
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    def _analyze_dimensions(self, dim_str: str) -> Dict[str, Any]:
        """
        Analyze dimension string and determine confidence level.
        """
        analysis = {
            "confidence": ConfidenceLevel.UNCERTAIN,
            "diameter": None,
            "length": None,
            "volume": None
        }

        # Try different patterns
        patterns = [
            # High confidence patterns
            (r'(\d+(?:\.\d+)?)\s*(?:ft|\')\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:ft|\')', ConfidenceLevel.HIGH),
            (r'[Dd](?:iameter)?[:\s]*(\d+(?:\.\d+)?)\s*(?:ft)?\s*[,\s]+[Ll](?:ength)?[:\s]*(\d+(?:\.\d+)?)', ConfidenceLevel.HIGH),

            # Medium confidence patterns
            (r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)', ConfidenceLevel.MEDIUM),

            # Low confidence patterns
            (r'(\d+)\s+(\d+)', ConfidenceLevel.LOW),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, dim_str)
            if match:
                try:
                    dim1 = float(match.group(1))
                    dim2 = float(match.group(2))

                    # Validate dimensions are reasonable
                    if self._validate_dimensions(dim1, dim2):
                        analysis["diameter"] = dim1
                        analysis["length"] = dim2
                        analysis["confidence"] = confidence
                        analysis["volume"] = self._calculate_cylindrical_volume(dim1, dim2)
                        break
                except:
                    continue

        return analysis

    def _validate_dimensions(self, dim1: float, dim2: float) -> bool:
        """Validate that dimensions are reasonable for a tank"""
        # Check reasonable ranges (feet)
        min_dim = 1  # Minimum 1 ft
        max_dim = 100  # Maximum 100 ft

        if min_dim <= dim1 <= max_dim and min_dim <= dim2 <= max_dim:
            # Check aspect ratio is reasonable
            aspect_ratio = max(dim1, dim2) / min(dim1, dim2)
            if aspect_ratio <= 10:  # Not too elongated
                return True
        return False

    def _calculate_cylindrical_volume(self, diameter: float, length: float, unit: str = 'ft') -> float:
        """Calculate cylindrical tank volume"""
        if unit == 'm':
            diameter = diameter * self.conversion_factors['m_to_ft']
            length = length * self.conversion_factors['m_to_ft']

        radius = diameter / 2
        volume_cuft = math.pi * radius * radius * length
        volume_gal = volume_cuft * self.conversion_factors['cuft_to_gal']

        return round(volume_gal, 0)

    def _parse_volume(self, vol_str: str) -> Optional[float]:
        """Parse volume string to gallons"""
        match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', vol_str)
        if not match:
            return None

        try:
            value = float(match.group(1).replace(',', ''))

            vol_lower = vol_str.lower()
            if 'bbl' in vol_lower or 'barrel' in vol_lower:
                value *= self.conversion_factors['bbl_to_gal']
            elif 'liter' in vol_lower or 'litre' in vol_lower:
                value *= self.conversion_factors['liter_to_gal']
            elif 'm3' in vol_lower or 'cubic meter' in vol_lower:
                value *= self.conversion_factors['m3_to_gal']

            return round(value, 0)
        except:
            return None

    def _infer_from_context(self, measurement: str, context: Dict) -> Dict[str, Any]:
        """Try to infer volume from context clues"""
        result = {
            "success": False,
            "volume": None,
            "confidence": ConfidenceLevel.UNCERTAIN,
            "reasoning": []
        }

        # Check if measurement is just a number
        try:
            value = float(measurement.replace(',', ''))

            # Use context to determine if it's gallons or dimensions
            if context.get("type") in ["diesel", "gasoline", "fuel"]:
                # Fuel tanks are typically measured in gallons
                if 100 <= value <= 100000:  # Reasonable gallon range
                    result["success"] = True
                    result["volume"] = value
                    result["confidence"] = ConfidenceLevel.MEDIUM
                    result["reasoning"].append(f"Interpreted {value} as gallons based on fuel type context")
                elif 1 <= value <= 2000:  # Might be barrels
                    result["success"] = True
                    result["volume"] = value * 42  # Convert to gallons
                    result["confidence"] = ConfidenceLevel.LOW
                    result["reasoning"].append(f"Interpreted {value} as barrels based on range")

            # Check tank naming patterns
            tank_id = context.get("tank_id", "")
            if "bbl" in tank_id.lower():
                result["success"] = True
                result["volume"] = value * 42
                result["confidence"] = ConfidenceLevel.MEDIUM
                result["reasoning"].append(f"Tank ID suggests barrels: {tank_id}")
            elif "gal" in tank_id.lower():
                result["success"] = True
                result["volume"] = value
                result["confidence"] = ConfidenceLevel.MEDIUM
                result["reasoning"].append(f"Tank ID suggests gallons: {tank_id}")

        except:
            pass

        return result


# ==============================================================================
# INTELLIGENT EXCEL TO JSON AGENT
# ==============================================================================

class IntelligentExcelToJsonAgent:
    """Excel to JSON converter with intelligent agent decision-making"""

    def __init__(self):
        self.volume_calc = IntelligentVolumeCalculator()
        self.column_mappings = self._get_default_mappings()
        self.conversion_decisions = []
        self.agent_log = []

    def _get_default_mappings(self) -> Dict[str, List[str]]:
        """Get default column name mappings"""
        return {
            "tank_id": ["tank id", "tank_id", "id", "tank", "name", "tank name", "tank number"],
            "measurements": ["dimensions", "measurements", "size", "capacity", "volume", "tank dimensions"],
            "type": ["type", "tank type", "fuel type", "fuel", "product"],
            "has_dike": ["has dike", "dike", "containment", "secondary containment"],
            "location": ["location", "site", "coordinates", "position"]
        }

    def parse_with_judgment(
        self,
        excel_path: str,
        decision_mode: str = "intelligent",
        override_decisions: Optional[Dict] = None,
        confidence_threshold: str = "medium"
    ) -> Dict[str, Any]:
        """
        Parse Excel with intelligent judgment on measurement conversions.

        Args:
            excel_path: Path to Excel file
            decision_mode: How to make decisions
                - "intelligent": Agent makes smart decisions
                - "conservative": Only convert high-confidence items
                - "aggressive": Convert everything possible
                - "interactive": Ask for each decision
            override_decisions: Manual decision overrides {tank_id: decision}
            confidence_threshold: Minimum confidence level to auto-convert

        Returns:
            Parsed data with decision log
        """
        result = {
            "success": False,
            "tanks": [],
            "decisions": [],
            "warnings": [],
            "clarifications_needed": [],
            "agent_log": []
        }

        try:
            # Read Excel
            df = pd.read_excel(excel_path)
            df = df.dropna(how='all').reset_index(drop=True)

            # Detect columns
            column_map = self._detect_columns(df)

            # Process each row with intelligent decisions
            for idx, row in df.iterrows():
                tank_result = self._process_tank_with_judgment(
                    row, column_map, idx,
                    decision_mode, override_decisions,
                    confidence_threshold
                )

                if tank_result["tank"]:
                    result["tanks"].append(tank_result["tank"])
                    result["decisions"].append(tank_result["decision"])

                    if tank_result.get("warnings"):
                        result["warnings"].extend(tank_result["warnings"])

                    if tank_result.get("needs_clarification"):
                        result["clarifications_needed"].append({
                            "tank_id": tank_result["tank"]["name"],
                            "issue": tank_result["needs_clarification"]
                        })

            result["success"] = True
            result["agent_log"] = self.agent_log

            # Summary
            self._add_summary(result)

        except Exception as e:
            result["error"] = str(e)
            self.agent_log.append(f"Error: {e}")

        return result

    def _process_tank_with_judgment(
        self,
        row: pd.Series,
        column_map: Dict,
        idx: int,
        decision_mode: str,
        override_decisions: Optional[Dict],
        confidence_threshold: str
    ) -> Dict[str, Any]:
        """Process a single tank with intelligent judgment"""

        tank_result = {
            "tank": None,
            "decision": None,
            "warnings": [],
            "needs_clarification": None
        }

        # Extract basic info
        tank_id = self._extract_tank_id(row, column_map, idx)
        tank_type = self._extract_tank_type(row, column_map)

        # Build context for decision-making
        context = {
            "tank_id": tank_id,
            "type": tank_type,
            "row_index": idx
        }

        # Extract measurement/capacity info
        measurement = self._extract_measurement(row, column_map)

        if measurement:
            # Make intelligent decision
            analysis = self.volume_calc.analyze_measurement(measurement, context)

            # Check for manual override
            if override_decisions and tank_id in override_decisions:
                decision = override_decisions[tank_id]
                self.agent_log.append(f"Tank {tank_id}: Using manual override - {decision}")
            else:
                decision = self._make_conversion_decision(
                    analysis, decision_mode, confidence_threshold
                )

            # Apply decision
            tank_data = self._apply_conversion_decision(
                tank_id, measurement, analysis, decision
            )

            tank_result["tank"] = tank_data
            tank_result["decision"] = {
                "tank_id": tank_id,
                "original": measurement,
                "decision": decision,
                "confidence": analysis["confidence"],
                "volume": tank_data.get("capacity"),
                "reasoning": analysis["reasoning"]
            }

            if analysis["warnings"]:
                tank_result["warnings"] = analysis["warnings"]

            if decision == ConversionDecision.NEEDS_CLARIFICATION:
                tank_result["needs_clarification"] = analysis["suggestions"][0] if analysis["suggestions"] else "Please verify measurement"

        else:
            # No measurement found
            tank_result["tank"] = {
                "name": tank_id,
                "capacity": 0,
                "type": tank_type or "unknown",
                "hasDike": False,
                "_status": "no_measurement"
            }

            self.agent_log.append(f"Tank {tank_id}: No measurement found")

        return tank_result

    def _make_conversion_decision(
        self,
        analysis: Dict,
        decision_mode: str,
        confidence_threshold: str
    ) -> ConversionDecision:
        """Make decision based on mode and analysis"""

        confidence_levels = {
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW: 1,
            ConfidenceLevel.UNCERTAIN: 0
        }

        threshold_levels = {
            "high": 3,
            "medium": 2,
            "low": 1,
            "any": 0
        }

        confidence_score = confidence_levels[analysis["confidence"]]
        threshold_score = threshold_levels.get(confidence_threshold, 2)

        if decision_mode == "intelligent":
            # Smart decision based on confidence
            if confidence_score >= threshold_score:
                return analysis["decision"]
            else:
                return ConversionDecision.NEEDS_CLARIFICATION

        elif decision_mode == "conservative":
            # Only convert if highly confident
            if analysis["confidence"] == ConfidenceLevel.HIGH:
                return analysis["decision"]
            else:
                return ConversionDecision.KEEP_AS_IS

        elif decision_mode == "aggressive":
            # Convert everything possible
            if analysis["volume_gallons"] is not None:
                return ConversionDecision.CALCULATE
            else:
                return ConversionDecision.NEEDS_CLARIFICATION

        elif decision_mode == "interactive":
            # Would prompt user here
            return ConversionDecision.NEEDS_CLARIFICATION

        else:
            return analysis["decision"]

    def _apply_conversion_decision(
        self,
        tank_id: str,
        original: str,
        analysis: Dict,
        decision: ConversionDecision
    ) -> Dict[str, Any]:
        """Apply the conversion decision to create tank data"""

        tank = {
            "name": tank_id,
            "original_measurement": original,
            "_conversion_decision": decision.value,
            "_confidence": analysis["confidence"].value
        }

        if decision in [ConversionDecision.CALCULATE, ConversionDecision.CONVERT, ConversionDecision.INFER]:
            tank["capacity"] = float(analysis["volume_gallons"]) if analysis["volume_gallons"] else 0
            tank["_volume_source"] = decision.value
            self.agent_log.append(f"Tank {tank_id}: Converted to {tank['capacity']:.0f} gallons ({decision.value})")

        elif decision == ConversionDecision.KEEP_AS_IS:
            tank["capacity"] = float(analysis["volume_gallons"]) if analysis["volume_gallons"] else 0
            tank["_volume_source"] = "original"
            self.agent_log.append(f"Tank {tank_id}: Kept original value")

        elif decision == ConversionDecision.NEEDS_CLARIFICATION:
            tank["capacity"] = 0
            tank["_needs_clarification"] = True
            tank["_suggestion"] = analysis["suggestions"][0] if analysis["suggestions"] else None
            self.agent_log.append(f"Tank {tank_id}: Needs clarification")

        else:  # SKIP
            tank["capacity"] = 0
            tank["_skipped"] = True
            self.agent_log.append(f"Tank {tank_id}: Skipped")

        # Add standard fields
        tank["type"] = "diesel"  # Default
        tank["hasDike"] = False  # Default

        return tank

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Detect columns in dataframe"""
        column_map = {}

        for std_name, variations in self.column_mappings.items():
            for col in df.columns:
                col_lower = str(col).lower().strip()
                for variation in variations:
                    if variation in col_lower:
                        column_map[std_name] = col
                        break
                if std_name in column_map:
                    break

        return column_map

    def _extract_tank_id(self, row: pd.Series, column_map: Dict, idx: int) -> str:
        """Extract tank ID from row"""
        if "tank_id" in column_map:
            tank_id = row[column_map["tank_id"]]
            if pd.notna(tank_id):
                return str(tank_id).strip()
        return f"Tank_{idx + 1}"

    def _extract_tank_type(self, row: pd.Series, column_map: Dict) -> Optional[str]:
        """Extract tank type from row"""
        if "type" in column_map:
            tank_type = row[column_map["type"]]
            if pd.notna(tank_type):
                return str(tank_type).lower().strip()
        return None

    def _extract_measurement(self, row: pd.Series, column_map: Dict) -> Optional[str]:
        """Extract measurement/capacity from row"""
        if "measurements" in column_map:
            measurement = row[column_map["measurements"]]
            if pd.notna(measurement):
                return str(measurement).strip()
        return None

    def _add_summary(self, result: Dict) -> None:
        """Add summary statistics to result"""
        if result["tanks"]:
            total = len(result["tanks"])
            converted = len([t for t in result["tanks"] if t.get("capacity", 0) > 0])
            needs_clarification = len(result["clarifications_needed"])

            result["summary"] = {
                "total_tanks": total,
                "successfully_converted": converted,
                "needs_clarification": needs_clarification,
                "conversion_rate": f"{(converted/total)*100:.1f}%" if total > 0 else "0%"
            }

            # Decision breakdown
            decision_counts = {}
            for decision in result["decisions"]:
                dec_type = decision["decision"]
                decision_counts[dec_type] = decision_counts.get(dec_type, 0) + 1

            result["summary"]["decision_breakdown"] = decision_counts

    def generate_clarification_request(self, clarifications: List[Dict]) -> str:
        """Generate a clarification request for unclear measurements"""

        if not clarifications:
            return "No clarifications needed."

        request = "Please clarify the following measurements:\n\n"

        for item in clarifications:
            request += f"Tank {item['tank_id']}:\n"
            request += f"  Current value: {item.get('original', 'unknown')}\n"
            request += f"  Issue: {item['issue']}\n"
            request += f"  Please provide as: 'diameter x length ft' or 'capacity gallons'\n\n"

        return request


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def parse_excel_with_intelligent_judgment(
    excel_path: str,
    decision_mode: str = "intelligent",
    confidence_threshold: str = "medium"
) -> Dict[str, Any]:
    """Parse Excel with intelligent judgment on conversions"""
    agent = IntelligentExcelToJsonAgent()
    return agent.parse_with_judgment(
        excel_path,
        decision_mode=decision_mode,
        confidence_threshold=confidence_threshold
    )


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Intelligent Excel parser with agent judgment on conversions"
    )
    parser.add_argument("excel_file", help="Excel file to parse")
    parser.add_argument("-m", "--mode", default="intelligent",
                       choices=["intelligent", "conservative", "aggressive", "interactive"],
                       help="Decision mode")
    parser.add_argument("-c", "--confidence", default="medium",
                       choices=["high", "medium", "low", "any"],
                       help="Minimum confidence threshold")
    parser.add_argument("-o", "--output", default="intelligent_output.json",
                       help="Output JSON file")

    args = parser.parse_args()

    print(f"🤖 Intelligent Excel Parser")
    print(f"   Mode: {args.mode}")
    print(f"   Confidence: {args.confidence}")
    print(f"   File: {args.excel_file}")
    print()

    # Parse with judgment
    result = parse_excel_with_intelligent_judgment(
        args.excel_file,
        decision_mode=args.mode,
        confidence_threshold=args.confidence
    )

    if result["success"]:
        print(f"✅ Parsed {len(result['tanks'])} tanks")

        if result.get("summary"):
            summary = result["summary"]
            print(f"\n📊 Summary:")
            print(f"   Total tanks: {summary['total_tanks']}")
            print(f"   Converted: {summary['successfully_converted']}")
            print(f"   Need clarification: {summary['needs_clarification']}")
            print(f"   Success rate: {summary['conversion_rate']}")

            if summary.get("decision_breakdown"):
                print(f"\n🎯 Decisions:")
                for decision, count in summary["decision_breakdown"].items():
                    print(f"   {decision}: {count}")

        if result["warnings"]:
            print(f"\n⚠️  Warnings:")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        if result["clarifications_needed"]:
            print(f"\n❓ Clarifications needed:")
            for item in result["clarifications_needed"]:
                print(f"   - {item['tank_id']}: {item['issue']}")

        # Save output
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n📁 Saved to: {args.output}")

    else:
        print(f"❌ Failed: {result.get('error')}")


if __name__ == "__main__":
    main()