#!/usr/bin/env python3
"""
HUD Pipeline with AI Agent Integration
Combines the agent-adjustable Excel parser with the HUD pipeline
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import the agent tool
from excel_to_json_agent_tool import (
    parse_excel_with_adjustments,
    save_json_output,
    suggest_corrections
)

# Import original pipeline
from hud_pipeline import HUDPipeline


class IntelligentHUDPipeline(HUDPipeline):
    """Enhanced HUD Pipeline with AI agent capabilities"""

    def __init__(self, output_dir: Optional[str] = None, ai_mode: str = "auto"):
        """
        Initialize intelligent pipeline.

        Args:
            output_dir: Output directory
            ai_mode: AI parsing mode (auto/strict/fuzzy/manual/ai_guided)
        """
        super().__init__(output_dir)
        self.ai_mode = ai_mode
        self.corrections_log = []

    def convert_excel_to_json_with_ai(
        self,
        excel_path: str,
        corrections: Optional[List[Dict]] = None,
        column_overrides: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Step 1: Convert Excel to JSON with AI assistance.

        Args:
            excel_path: Path to Excel file
            corrections: Manual corrections to apply
            column_overrides: Column mapping overrides

        Returns:
            Dict with success status and JSON path
        """
        print(f"\n🤖 AI Agent: Analyzing Excel file...")

        # First, get suggestions
        suggestions = suggest_corrections(excel_path)

        if suggestions.get("column_mappings"):
            print(f"📋 Detected columns: {list(suggestions['column_mappings'].keys())}")

        if suggestions.get("data_issues"):
            print(f"⚠️  Issues found: {suggestions['data_issues']}")

        if suggestions.get("recommendations"):
            print(f"💡 Recommendations: {suggestions['recommendations']}")

        # Parse with AI assistance
        print(f"\n📄 Converting Excel to JSON with {self.ai_mode} mode...")

        # Prepare parsing hints for AI-guided mode
        parsing_hints = None
        if self.ai_mode == "ai_guided":
            parsing_hints = {
                "units": "gallons",
                "default_type": "diesel",
                "skip_rows": []
            }

        # Parse Excel
        parse_result = parse_excel_with_adjustments(
            excel_path=excel_path,
            mode=self.ai_mode,
            column_overrides=column_overrides,
            value_corrections=corrections,
            parsing_hints=parsing_hints
        )

        if not parse_result["success"]:
            # Try fallback mode
            print(f"⚠️ {self.ai_mode} mode failed, trying fuzzy mode...")

            parse_result = parse_excel_with_adjustments(
                excel_path=excel_path,
                mode="fuzzy",
                column_overrides=column_overrides
            )

        if not parse_result["success"]:
            print(f"❌ Conversion failed: {parse_result.get('error')}")
            return {
                "success": False,
                "error": parse_result.get("error"),
                "json_path": None
            }

        # Validate and enhance data
        tanks = parse_result.get("tanks", [])
        enhanced_tanks = self._enhance_tank_data(tanks)

        # Save to JSON
        json_path = self.output_dir / "tank_config.json"
        save_result = save_json_output(
            {"tanks": enhanced_tanks, "metadata": parse_result.get("metadata", {})},
            str(json_path)
        )

        if save_result["success"]:
            print(f"✅ Converted {len(enhanced_tanks)} tanks to JSON")
            print(f"   - Valid tanks: {len([t for t in enhanced_tanks if t.get('capacity', 0) > 0])}")
            print(f"   - Tanks with dikes: {len([t for t in enhanced_tanks if t.get('hasDike')])}")
            return {
                "success": True,
                "json_path": str(json_path),
                "tank_count": len(enhanced_tanks),
                "corrections_applied": len(corrections) if corrections else 0
            }
        else:
            return {
                "success": False,
                "error": save_result.get("error"),
                "json_path": None
            }

    def _enhance_tank_data(self, tanks: List[Dict]) -> List[Dict]:
        """
        Enhance tank data with AI intelligence.

        Args:
            tanks: List of tank dictionaries

        Returns:
            Enhanced tank list
        """
        enhanced = []

        for tank in tanks:
            # Ensure required fields
            if not tank.get("name"):
                tank["name"] = f"Tank_{len(enhanced) + 1}"

            # Validate capacity
            capacity = tank.get("capacity", 0)
            if capacity <= 0:
                print(f"⚠️ Tank {tank['name']} has invalid capacity: {capacity}")
                # Try to infer from name or notes
                if "50000" in str(tank.get("name", "")) or "50000" in str(tank.get("notes", "")):
                    tank["capacity"] = 50000
                    self.corrections_log.append(f"Inferred capacity for {tank['name']}")
                else:
                    # Skip tanks without capacity
                    continue

            # Validate type
            valid_types = ["diesel", "gasoline", "lpg", "pressurized_gas", "fuel"]
            if tank.get("type") not in valid_types:
                tank["type"] = "diesel"  # Default
                self.corrections_log.append(f"Set default type for {tank['name']}")

            # Ensure boolean for hasDike
            tank["hasDike"] = bool(tank.get("hasDike", False))

            enhanced.append(tank)

        return enhanced

    def run_with_ai(
        self,
        excel_path: str,
        manual_corrections: Optional[List[Dict]] = None,
        column_mappings: Optional[Dict] = None,
        skip_hud: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete HUD pipeline with AI assistance.

        Args:
            excel_path: Path to Excel file
            manual_corrections: Manual corrections to apply
            column_mappings: Column name mappings
            skip_hud: Skip HUD processing (for testing)

        Returns:
            Dict with all output paths and status
        """
        print("=" * 60)
        print("🚀 Starting Intelligent HUD Pipeline")
        print(f"🤖 AI Mode: {self.ai_mode}")
        print(f"📁 Input: {excel_path}")
        print(f"📂 Output Directory: {self.output_dir}")
        print("=" * 60)

        results = {
            "success": True,
            "input_excel": excel_path,
            "output_dir": str(self.output_dir),
            "ai_mode": self.ai_mode,
            "steps": {}
        }

        # Step 1: AI-powered Excel to JSON conversion
        json_result = self.convert_excel_to_json_with_ai(
            excel_path,
            corrections=manual_corrections,
            column_overrides=column_mappings
        )
        results["steps"]["excel_to_json"] = json_result

        if not json_result["success"]:
            results["success"] = False
            print(f"\n❌ Pipeline failed at Excel conversion")
            return results

        # Log corrections applied
        if self.corrections_log:
            print(f"\n🔧 AI Corrections Applied:")
            for correction in self.corrections_log:
                print(f"   - {correction}")
            results["ai_corrections"] = self.corrections_log

        # Skip HUD if requested (for testing)
        if skip_hud:
            print("\n⏭️  Skipping HUD processing (test mode)")
            results["steps"]["hud_skipped"] = True
            return results

        # Continue with standard pipeline steps
        # Step 2: Process through HUD
        hud_result = self.process_hud(json_result["json_path"])
        results["steps"]["hud_processing"] = hud_result

        if not hud_result["success"]:
            results["success"] = False
            print(f"\n⚠️ Pipeline completed with HUD errors")

        # Step 3: Generate PDF
        pdf_result = self.generate_pdf()
        results["steps"]["pdf_generation"] = pdf_result

        # Step 4: Update Excel with results
        if hud_result.get("results_path"):
            excel_result = self.update_excel(excel_path, hud_result["results_path"])
            results["steps"]["excel_update"] = excel_result

            if excel_result["success"]:
                results["updated_excel"] = excel_result["excel_path"]

        # Summary
        print("\n" + "=" * 60)
        print("✨ Intelligent Pipeline Complete!")
        print(f"📂 Output Directory: {self.output_dir}")

        if self.corrections_log:
            print(f"🔧 AI Corrections: {len(self.corrections_log)}")

        if results.get("updated_excel"):
            print(f"📊 Updated Excel: {Path(results['updated_excel']).name}")

        if pdf_result.get("pdf_path"):
            print(f"📑 PDF Report: {Path(pdf_result['pdf_path']).name}")

        print("=" * 60)

        return results

    def interactive_process(self, excel_path: str) -> Dict[str, Any]:
        """
        Process Excel with interactive AI assistance.

        Args:
            excel_path: Path to Excel file

        Returns:
            Processing results
        """
        print("=" * 60)
        print("🤖 Interactive AI Processing Mode")
        print("=" * 60)

        # Get suggestions first
        suggestions = suggest_corrections(excel_path)

        print("\n📋 Excel Analysis:")
        print(f"Detected columns: {list(suggestions.get('column_mappings', {}).keys())}")

        if suggestions.get("data_issues"):
            print(f"\n⚠️ Issues found:")
            for issue in suggestions["data_issues"]:
                print(f"  - {issue}")

        # Ask for user input
        print("\n🤖 AI Agent: How should I process this file?")
        print("  1. Auto mode (automatic detection)")
        print("  2. Strict mode (exact column matches)")
        print("  3. Fuzzy mode (approximate matches)")
        print("  4. AI-guided mode (intelligent processing)")

        choice = input("\nSelect mode (1-4) [default: 1]: ") or "1"

        mode_map = {
            "1": "auto",
            "2": "strict",
            "3": "fuzzy",
            "4": "ai_guided"
        }

        self.ai_mode = mode_map.get(choice, "auto")

        # Ask about corrections
        corrections = []
        if input("\n🤖 Do you want to provide manual corrections? (y/n): ").lower() == 'y':
            print("\nEnter corrections (format: tank_id,field,value)")
            print("Example: T-001,capacity,50000")
            print("Enter blank line when done.")

            while True:
                correction_str = input("> ")
                if not correction_str:
                    break

                parts = correction_str.split(',')
                if len(parts) == 3:
                    corrections.append({
                        "tank_id": parts[0],
                        "field": parts[1],
                        "value": parts[2]
                    })

        # Process with selected options
        return self.run_with_ai(
            excel_path,
            manual_corrections=corrections if corrections else None
        )


def main():
    """Main entry point for intelligent pipeline"""
    parser = argparse.ArgumentParser(
        description="Process Excel through HUD pipeline with AI assistance"
    )
    parser.add_argument(
        "excel_file",
        help="Path to Excel file with tank data"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: auto-generated timestamp)",
        default=None
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["auto", "strict", "fuzzy", "manual", "ai_guided"],
        default="auto",
        help="AI parsing mode"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--skip-hud",
        action="store_true",
        help="Skip HUD processing (for testing)"
    )
    parser.add_argument(
        "--corrections",
        help="JSON file with manual corrections",
        default=None
    )
    parser.add_argument(
        "--mappings",
        help="JSON file with column mappings",
        default=None
    )

    args = parser.parse_args()

    # Verify input file exists
    if not Path(args.excel_file).exists():
        print(f"❌ Error: File not found: {args.excel_file}")
        sys.exit(1)

    # Load corrections if provided
    corrections = None
    if args.corrections:
        with open(args.corrections) as f:
            corrections = json.load(f)

    # Load mappings if provided
    mappings = None
    if args.mappings:
        with open(args.mappings) as f:
            mappings = json.load(f)

    # Create pipeline
    pipeline = IntelligentHUDPipeline(
        output_dir=args.output,
        ai_mode=args.mode
    )

    # Run pipeline
    if args.interactive:
        results = pipeline.interactive_process(args.excel_file)
    else:
        results = pipeline.run_with_ai(
            args.excel_file,
            manual_corrections=corrections,
            column_mappings=mappings,
            skip_hud=args.skip_hud
        )

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()