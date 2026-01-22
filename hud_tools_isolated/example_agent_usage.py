#!/usr/bin/env python3
"""
Example Agent Using the Excel to JSON Tool
Demonstrates how an AI agent can adjust and correct data during conversion
"""

from excel_to_json_agent_tool import (
    parse_excel_with_adjustments,
    save_json_output,
    suggest_corrections
)
from typing import Dict, Any, List
import json


class ExcelProcessingAgent:
    """Example agent that uses the adjustable Excel tool"""

    def __init__(self):
        self.processing_log = []

    def process_with_corrections(self, excel_path: str) -> Dict[str, Any]:
        """
        Process Excel with intelligent corrections and adjustments.
        This simulates how an AI agent would interact with the tool.
        """

        print("🤖 Agent: Starting Excel analysis...")

        # Step 1: Get suggestions for the file
        suggestions = suggest_corrections(excel_path)

        if suggestions.get("error"):
            return {"error": f"Failed to analyze file: {suggestions['error']}"}

        print(f"📋 Found columns: {suggestions.get('column_mappings', {})}")
        print(f"⚠️  Data issues: {suggestions.get('data_issues', [])}")

        # Step 2: First parsing attempt with auto mode
        print("\n🔍 Agent: Attempting automatic parsing...")

        first_result = parse_excel_with_adjustments(
            excel_path=excel_path,
            mode="auto"
        )

        if not first_result["success"]:
            print(f"❌ Auto parsing failed: {first_result.get('error')}")
            print("🔄 Agent: Switching to fuzzy mode...")

            # Try fuzzy mode if auto fails
            first_result = parse_excel_with_adjustments(
                excel_path=excel_path,
                mode="fuzzy"
            )

        # Step 3: Analyze the results and determine if corrections are needed
        tanks = first_result.get("tanks", [])
        print(f"\n✅ Found {len(tanks)} tanks initially")

        corrections_needed = []

        for tank in tanks:
            # Check for missing critical data
            if not tank.get("capacity"):
                print(f"⚠️ Tank {tank['name']} missing capacity")

                # Agent could attempt to infer from dimensions or other data
                if "10 x 20" in str(tank.get("name", "")):
                    corrections_needed.append({
                        "tank_id": tank["name"],
                        "field": "capacity",
                        "value": 11000  # Calculated from dimensions
                    })

        # Step 4: Apply corrections if needed
        if corrections_needed:
            print(f"\n🔧 Agent: Applying {len(corrections_needed)} corrections...")

            corrected_result = parse_excel_with_adjustments(
                excel_path=excel_path,
                mode="auto",
                value_corrections=corrections_needed
            )

            return corrected_result

        return first_result

    def process_with_column_mapping(self, excel_path: str) -> Dict[str, Any]:
        """
        Process Excel with custom column mappings.
        Useful when column names don't match standard patterns.
        """

        print("🤖 Agent: Processing with custom column mappings...")

        # Example: Spanish column names
        column_overrides = {
            "tank_id": "Código del Tanque",
            "dimensions": "Medidas",
            "capacity": "Capacidad (galones)",
            "type": "Tipo de Combustible",
            "has_dike": "Tiene Dique",
            "location": "Ubicación"
        }

        result = parse_excel_with_adjustments(
            excel_path=excel_path,
            mode="manual",
            column_overrides=column_overrides
        )

        return result

    def process_with_ai_guidance(self, excel_path: str) -> Dict[str, Any]:
        """
        Process Excel with AI-guided hints and corrections.
        This represents the most intelligent processing mode.
        """

        print("🤖 Agent: Using AI-guided processing...")

        # AI provides parsing hints based on understanding the data
        parsing_hints = {
            "units": "gallons",  # Expected units
            "date_format": "MM/DD/YYYY",  # Date format if dates present
            "skip_rows": [0, 1],  # Skip header rows if needed
            "tank_id_pattern": r"T-\d{3}",  # Expected ID format
            "capacity_multiplier": 1.0,  # Scaling factor if needed
            "default_type": "diesel",  # Default fuel type
            "coordinate_format": "decimal"  # For location data
        }

        # AI determines best column mappings based on content analysis
        smart_overrides = {
            "tank_id": "Tank Number",  # AI detected this is the ID column
            "dimensions": "Size (D x L)",  # AI recognized dimension format
            "capacity": "Volume",  # AI identified this as capacity
        }

        # Process with all AI guidance
        result = parse_excel_with_adjustments(
            excel_path=excel_path,
            mode="ai_guided",
            column_overrides=smart_overrides,
            parsing_hints=parsing_hints
        )

        # Post-process to ensure data quality
        if result["success"]:
            tanks = result["tanks"]

            # AI adds calculated fields
            for tank in tanks:
                # Ensure all tanks have required fields
                if not tank.get("hasDike"):
                    # AI infers from other data
                    if float(tank.get("capacity", 0)) > 10000:
                        tank["hasDike"] = True  # Large tanks usually have dikes
                    else:
                        tank["hasDike"] = False

                # Add risk assessment (AI-generated)
                capacity = float(tank.get("capacity", 0))
                if capacity > 50000:
                    tank["risk_level"] = "high"
                elif capacity > 10000:
                    tank["risk_level"] = "medium"
                else:
                    tank["risk_level"] = "low"

        return result

    def interactive_correction_session(self, excel_path: str) -> Dict[str, Any]:
        """
        Simulates an interactive session where the agent asks for clarification.
        """

        print("🤖 Agent: Starting interactive correction session...")

        # Initial parse
        result = parse_excel_with_adjustments(
            excel_path=excel_path,
            mode="auto"
        )

        if not result["success"]:
            print("❌ Initial parsing failed")

            # Agent asks for help
            print("\n🤖 Agent: I need help with column mapping.")
            print("   Available columns:", result.get("metadata", {}).get("columns_found", []))

            # Simulate user providing mapping
            user_mappings = {
                "tank_id": input("   Which column contains tank IDs? ") or "Tank ID",
                "capacity": input("   Which column contains capacity? ") or "Capacity"
            }

            # Retry with user guidance
            result = parse_excel_with_adjustments(
                excel_path=excel_path,
                mode="manual",
                column_overrides=user_mappings
            )

        # Review results
        tanks = result.get("tanks", [])
        print(f"\n📊 Parsed {len(tanks)} tanks")

        # Show sample for verification
        if tanks:
            print("\nSample tank data:")
            sample = tanks[0]
            print(json.dumps(sample, indent=2))

            # Ask for confirmation
            confirm = input("\n🤖 Does this look correct? (y/n): ")

            if confirm.lower() != 'y':
                print("🤖 Agent: What corrections should I make?")
                # Collect corrections...

        return result

    def batch_process_with_learning(self, excel_files: List[str]) -> Dict[str, Any]:
        """
        Process multiple files, learning from each one.
        """

        print("🤖 Agent: Batch processing with learning...")

        learned_mappings = {}
        results = {}

        for file_path in excel_files:
            print(f"\n📁 Processing: {file_path}")

            # Use learned mappings from previous files
            if learned_mappings:
                result = parse_excel_with_adjustments(
                    excel_path=file_path,
                    mode="manual",
                    column_overrides=learned_mappings
                )
            else:
                result = parse_excel_with_adjustments(
                    excel_path=file_path,
                    mode="auto"
                )

            # Learn from successful parsing
            if result["success"] and not learned_mappings:
                # Extract the column mappings that worked
                metadata = result.get("metadata", {})
                if "column_mappings" in metadata:
                    learned_mappings = metadata["column_mappings"]
                    print(f"✅ Learned column mappings: {learned_mappings}")

            results[file_path] = result

        return results


def demonstrate_agent_capabilities():
    """Demonstrate various agent capabilities"""

    print("="*60)
    print("Excel to JSON Agent Tool - Demonstration")
    print("="*60)

    agent = ExcelProcessingAgent()

    # Create sample Excel file
    import pandas as pd

    sample_data = {
        "Tank ID": ["T-001", "T-002", "T-003"],
        "Tank Dimensions": ["10 x 20 ft", "15 x 30 ft", None],
        "Tank Capacity": [None, None, "50000 gal"],
        "Type": ["Diesel", "Gasoline", "LPG"],
        "Has Dike": ["Yes", "Yes", "No"]
    }

    df = pd.DataFrame(sample_data)
    sample_file = "sample_tanks_demo.xlsx"
    df.to_excel(sample_file, index=False)

    print("\n1. Basic Processing with Corrections")
    print("-"*40)
    result1 = agent.process_with_corrections(sample_file)
    print(f"Result: {result1.get('metadata', {}).get('tank_count', 0)} tanks processed")

    print("\n2. AI-Guided Processing")
    print("-"*40)
    result2 = agent.process_with_ai_guidance(sample_file)
    print(f"Result: {result2.get('metadata', {}).get('tank_count', 0)} tanks with AI enhancements")

    # Save results
    if result2["success"]:
        save_result = save_json_output(result2, "demo_output.json")
        print(f"\n✅ Saved to: {save_result.get('path')}")

    print("\n" + "="*60)
    print("Demonstration complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Process provided file
        agent = ExcelProcessingAgent()
        result = agent.process_with_corrections(sys.argv[1])

        if result["success"]:
            print(f"\n✅ Processed {len(result['tanks'])} tanks")
            save_result = save_json_output(result, "agent_output.json")
            print(f"📁 Saved to: {save_result.get('path')}")
        else:
            print(f"❌ Processing failed: {result.get('error')}")
    else:
        # Run demonstration
        demonstrate_agent_capabilities()