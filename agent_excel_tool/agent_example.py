#!/usr/bin/env python3
"""
Example AI Agent Using the Excel Analysis Tool
Shows how an agent makes decisions based on tool's analysis
"""

from excel_analysis_tool import analyze_excel_for_conversion, apply_conversion_decisions
from typing import Dict, List, Any, Optional
import json


class TankProcessingAgent:
    """
    Example AI agent that uses the Excel Analysis Tool.
    The agent makes all decisions - the tool only provides analysis.
    """

    def __init__(self, confidence_threshold: str = "medium", verbose: bool = True):
        """
        Initialize the agent with decision parameters.

        Args:
            confidence_threshold: Minimum confidence to accept ("high", "medium", "low")
            verbose: Whether to print decision reasoning
        """
        self.confidence_threshold = confidence_threshold
        self.verbose = verbose
        self.decision_log = []

    def process_excel(self, excel_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Main agent workflow: analyze Excel and make decisions.

        Args:
            excel_path: Path to Excel file
            sheet_name: Optional specific sheet to use

        Returns:
            Final tank configuration based on agent's decisions
        """
        if self.verbose:
            print(f"🤖 Agent: Starting Excel analysis...")

        # Step 1: Get analysis from tool (no decisions made yet)
        analysis = analyze_excel_for_conversion(excel_path, sheet_name)

        if not analysis["success"]:
            return {"error": f"Analysis failed: {analysis.get('error')}", "tanks": []}

        if self.verbose:
            print(f"📊 Found {len(analysis['sheets_available'])} sheets")
            print(f"📋 Recommended sheet: {analysis['recommended_sheet']}")
            print(f"📝 Rows to process: {analysis['metadata']['non_empty_rows']}")

        # Step 2: Agent makes decisions for each row
        decisions = []

        for row in analysis["rows_analyzed"]:
            if not row["has_data"]:
                continue

            # Agent decides how to process this row
            decision = self._make_row_decision(row)

            if decision:
                decisions.append(decision)

                if self.verbose and decision.get("agent_reasoning"):
                    print(f"\n🎯 Row {row['row_index']}: {decision['tank_id']}")
                    for reason in decision["agent_reasoning"]:
                        print(f"   → {reason}")

        if self.verbose:
            print(f"\n✅ Agent made {len(decisions)} decisions")

        # Step 3: Apply agent's decisions using the tool
        result = apply_conversion_decisions(analysis, decisions)

        # Add agent metadata
        result["agent_metadata"] = {
            "confidence_threshold": self.confidence_threshold,
            "decisions_made": len(decisions),
            "decision_log": self.decision_log
        }

        return result

    def _make_row_decision(self, row_analysis: Dict) -> Optional[Dict]:
        """
        Agent's decision-making logic for a single row.

        This is where the agent's intelligence comes in - deciding:
        - Which tank ID to use
        - Which conversion method to apply
        - Whether to trust the data
        - When to skip or override

        Args:
            row_analysis: Analysis for a single row from the tool

        Returns:
            Decision dictionary or None to skip
        """
        decision = {
            "row_index": row_analysis["row_index"],
            "agent_reasoning": []
        }

        # Decision 1: Choose tank ID
        tank_id = self._choose_tank_id(row_analysis)
        decision["tank_id"] = tank_id
        decision["agent_reasoning"].append(f"Selected tank ID: {tank_id}")

        # Decision 2: Choose conversion method
        conversion = self._choose_conversion(row_analysis)

        if conversion:
            if conversion.get("needs_override"):
                # Agent decides to override with manual value
                decision["override_capacity"] = conversion["override_value"]
                decision["agent_reasoning"].append(f"Override capacity: {conversion['override_value']} gal (agent judgment)")
            else:
                # Agent chooses a conversion from possibilities
                decision["use_conversion"] = conversion
                decision["agent_reasoning"].append(
                    f"Using {conversion.get('method', 'unknown')} conversion: {conversion.get('interpretation', 'N/A')}"
                )
        else:
            # Agent decides to skip this tank
            decision["agent_reasoning"].append("No valid conversion found - setting capacity to 0")

        # Decision 3: Determine tank type (agent's inference)
        tank_type = row_analysis.get("other_data", {}).get("tank_type", "diesel")
        decision["tank_type"] = self._normalize_tank_type(tank_type)

        # Decision 4: Determine dike status
        has_dike = row_analysis.get("other_data", {}).get("has_dike", False)
        decision["has_dike"] = has_dike

        # Log the decision
        self.decision_log.append({
            "row": row_analysis["row_index"],
            "tank_id": tank_id,
            "method": conversion.get("method") if conversion else "none"
        })

        return decision

    def _choose_tank_id(self, row_analysis: Dict) -> str:
        """
        Agent decides which tank ID to use.
        """
        possible_ids = row_analysis.get("possible_tank_ids", [])

        if possible_ids:
            # Agent's strategy: prefer high confidence IDs
            high_conf = [id for id in possible_ids if id["confidence"] == "high"]
            if high_conf:
                return high_conf[0]["value"]

            medium_conf = [id for id in possible_ids if id["confidence"] == "medium"]
            if medium_conf:
                return medium_conf[0]["value"]

            # Use low confidence as last resort
            if possible_ids:
                return possible_ids[0]["value"]

        # Generate ID if none found
        return f"Tank_{row_analysis['row_index'] + 1}"

    def _choose_conversion(self, row_analysis: Dict) -> Optional[Dict]:
        """
        Agent decides which conversion method to use.
        This is the key decision point where agent judgment is applied.
        """
        conversion_options = row_analysis.get("conversion_possibilities", [])

        # Collect all possibilities
        all_possibilities = []
        for option in conversion_options:
            for possibility in option.get("possibilities", []):
                possibility["source_column"] = option["column"]
                all_possibilities.append(possibility)

        if not all_possibilities:
            return None

        # Agent's decision strategy based on confidence threshold
        confidence_priority = {
            "high": ["high"],
            "medium": ["high", "medium"],
            "low": ["high", "medium", "low"]
        }

        acceptable_confidences = confidence_priority.get(self.confidence_threshold, ["high", "medium"])

        # Filter by acceptable confidence
        acceptable = [p for p in all_possibilities if p.get("confidence") in acceptable_confidences]

        if acceptable:
            # Agent prefers calculated dimensions over direct values (more reliable)
            calculated = [p for p in acceptable if p.get("method") == "calculate_from_dimensions"]
            if calculated:
                return calculated[0]

            # Next prefer direct gallons
            direct = [p for p in acceptable if p.get("method") == "direct_gallons"]
            if direct:
                return direct[0]

            # Then converted barrels
            barrels = [p for p in acceptable if p.get("method") == "convert_from_barrels"]
            if barrels:
                return barrels[0]

            # Use first acceptable
            return acceptable[0]

        # If no acceptable confidence, agent must decide what to do
        if all_possibilities:
            # Check if there's a number that could be gallons
            unknown = [p for p in all_possibilities if p.get("needs_agent_decision")]
            if unknown and unknown[0].get("numeric_values"):
                # Agent's heuristic: large numbers are probably gallons
                for num in unknown[0]["numeric_values"]:
                    if 1000 <= num <= 100000:
                        return {
                            "needs_override": True,
                            "override_value": num,
                            "method": "agent_inference",
                            "interpretation": f"Agent inferred {num} as gallons"
                        }

        return None

    def _normalize_tank_type(self, tank_type: str) -> str:
        """
        Agent normalizes tank type to standard values.
        """
        type_mapping = {
            "diesel": "diesel",
            "gasoline": "gasoline",
            "gas": "gasoline",
            "fuel": "diesel",
            "lpg": "lpg",
            "propane": "lpg",
            "pressurized": "pressurized_gas"
        }

        normalized = type_mapping.get(tank_type.lower(), "diesel")
        return normalized

    def generate_report(self, result: Dict) -> str:
        """
        Generate a report of agent's decisions.
        """
        report = []
        report.append("=" * 60)
        report.append("AGENT DECISION REPORT")
        report.append("=" * 60)

        if "tanks" in result:
            report.append(f"\nTanks Processed: {len(result['tanks'])}")

            # Summary statistics
            total_capacity = sum(t.get("capacity", 0) for t in result["tanks"])
            with_dike = sum(1 for t in result["tanks"] if t.get("hasDike"))

            report.append(f"Total Capacity: {total_capacity:,.0f} gallons")
            report.append(f"Tanks with Dike: {with_dike}/{len(result['tanks'])}")

            # Conversion methods used
            methods = {}
            for tank in result["tanks"]:
                method = tank.get("_conversion_method", "unknown")
                methods[method] = methods.get(method, 0) + 1

            report.append("\nConversion Methods Used:")
            for method, count in methods.items():
                report.append(f"  {method}: {count}")

            # Sample tanks
            report.append("\nSample Tanks:")
            for tank in result["tanks"][:5]:
                report.append(f"  {tank['name']}: {tank.get('capacity', 0):,.0f} gal ({tank.get('type')})")
                if "_agent_reasoning" in tank:
                    for reason in tank["_agent_reasoning"]:
                        report.append(f"    → {reason}")

        report.append("=" * 60)
        return "\n".join(report)


# ==============================================================================
# MAIN - Demonstration
# ==============================================================================

def main():
    """Demonstrate agent using the tool"""
    import sys
    from pathlib import Path

    # Check if Excel file provided
    if len(sys.argv) < 2:
        print("Usage: python agent_example.py <excel_file> [confidence_threshold]")
        print("  confidence_threshold: high, medium, or low (default: medium)")
        sys.exit(1)

    excel_file = sys.argv[1]
    confidence = sys.argv[2] if len(sys.argv) > 2 else "medium"

    # Verify file exists
    if not Path(excel_file).exists():
        print(f"❌ File not found: {excel_file}")
        sys.exit(1)

    print("="*60)
    print("AI AGENT EXCEL PROCESSING DEMONSTRATION")
    print("="*60)
    print(f"File: {excel_file}")
    print(f"Confidence Threshold: {confidence}")
    print("="*60)

    # Create agent
    agent = TankProcessingAgent(confidence_threshold=confidence, verbose=True)

    # Process Excel
    result = agent.process_excel(excel_file)

    # Generate report
    report = agent.generate_report(result)
    print("\n" + report)

    # Save results
    output_file = "agent_output.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    main()