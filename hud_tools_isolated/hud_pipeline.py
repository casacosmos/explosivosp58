#!/usr/bin/env python3
"""
Isolated HUD Pipeline
Complete pipeline for processing Excel files through HUD tool
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import shutil
from datetime import datetime


class HUDPipeline:
    """Isolated HUD processing pipeline"""

    def __init__(self, output_dir: Optional[str] = None):
        """Initialize pipeline with output directory"""
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = Path(f"hud_output_{timestamp}")

        self.output_dir.mkdir(exist_ok=True, parents=True)

    def convert_excel_to_json(self, excel_path: str) -> Dict[str, Any]:
        """
        Step 1: Convert Excel to JSON format for HUD tool

        Args:
            excel_path: Path to Excel file with tank data

        Returns:
            Dict with success status and JSON path
        """
        print(f"\n📄 Converting Excel to JSON...")

        json_path = self.output_dir / "tank_config.json"

        cmd = [
            sys.executable, "excel_to_json_improved.py",
            excel_path,
            "-o", str(json_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"❌ Conversion failed: {result.stderr}")
                return {"success": False, "error": result.stderr, "json_path": None}

            # Verify JSON was created
            if json_path.exists():
                with open(json_path) as f:
                    data = json.load(f)
                    tank_count = len(data.get('tanks', []))
                print(f"✅ Converted {tank_count} tanks to JSON")
                return {"success": True, "json_path": str(json_path), "tank_count": tank_count}
            else:
                return {"success": False, "error": "JSON file not created", "json_path": None}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Conversion timeout", "json_path": None}
        except Exception as e:
            return {"success": False, "error": str(e), "json_path": None}

    def process_hud(self, json_path: str) -> Dict[str, Any]:
        """
        Step 2: Process tanks through HUD website

        Args:
            json_path: Path to tank configuration JSON

        Returns:
            Dict with success status and results path
        """
        print(f"\n🌐 Processing tanks through HUD...")

        results_path = self.output_dir / "hud_results.json"

        cmd = [
            sys.executable, "fast_hud_processor.py",
            "--config", json_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            if result.returncode != 0:
                print(f"❌ HUD processing failed: {result.stderr}")
                return {"success": False, "error": result.stderr, "results_path": None}

            # Look for results file
            default_results = Path("fast_results.json")
            if default_results.exists():
                # Move to output directory
                shutil.move(str(default_results), str(results_path))
                print(f"✅ HUD processing complete")
                return {"success": True, "results_path": str(results_path)}
            else:
                return {"success": False, "error": "Results file not created", "results_path": None}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "HUD processing timeout", "results_path": None}
        except Exception as e:
            return {"success": False, "error": str(e), "results_path": None}

    def generate_pdf(self) -> Dict[str, Any]:
        """
        Step 3: Generate PDF from screenshots

        Returns:
            Dict with success status and PDF path
        """
        print(f"\n📑 Generating PDF from screenshots...")

        pdf_path = self.output_dir / "HUD_Results.pdf"

        cmd = [
            sys.executable, "generate_pdf.py",
            "-d", ".playwright-mcp",  # Screenshots directory
            "-o", str(pdf_path),
            "--summary"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"❌ PDF generation failed: {result.stderr}")
                return {"success": False, "error": result.stderr, "pdf_path": None}

            if pdf_path.exists():
                print(f"✅ PDF generated: {pdf_path.name}")
                return {"success": True, "pdf_path": str(pdf_path)}
            else:
                return {"success": False, "error": "PDF file not created", "pdf_path": None}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "PDF generation timeout", "pdf_path": None}
        except Exception as e:
            return {"success": False, "error": str(e), "pdf_path": None}

    def update_excel(self, original_excel: str, results_path: str) -> Dict[str, Any]:
        """
        Step 4: Update Excel with HUD results

        Args:
            original_excel: Path to original Excel file
            results_path: Path to HUD results JSON

        Returns:
            Dict with success status and updated Excel path
        """
        print(f"\n📊 Updating Excel with HUD results...")

        updated_excel = self.output_dir / "Updated_Excel_with_HUD.xlsx"

        cmd = [
            sys.executable, "update_excel_with_results.py",
            original_excel,
            results_path,
            "-o", str(updated_excel)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"❌ Excel update failed: {result.stderr}")
                return {"success": False, "error": result.stderr, "excel_path": None}

            if updated_excel.exists():
                print(f"✅ Excel updated: {updated_excel.name}")
                return {"success": True, "excel_path": str(updated_excel)}
            else:
                return {"success": False, "error": "Updated Excel not created", "excel_path": None}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Excel update timeout", "excel_path": None}
        except Exception as e:
            return {"success": False, "error": str(e), "excel_path": None}

    def run(self, excel_path: str) -> Dict[str, Any]:
        """
        Run complete HUD pipeline

        Args:
            excel_path: Path to Excel file with tank data

        Returns:
            Dict with all output paths and status
        """
        print("=" * 60)
        print("🚀 Starting HUD Pipeline")
        print(f"📁 Input: {excel_path}")
        print(f"📂 Output Directory: {self.output_dir}")
        print("=" * 60)

        results = {
            "success": True,
            "input_excel": excel_path,
            "output_dir": str(self.output_dir),
            "steps": {}
        }

        # Step 1: Convert Excel to JSON
        json_result = self.convert_excel_to_json(excel_path)
        results["steps"]["excel_to_json"] = json_result

        if not json_result["success"]:
            results["success"] = False
            print(f"\n❌ Pipeline failed at Excel conversion")
            return results

        # Step 2: Process through HUD
        hud_result = self.process_hud(json_result["json_path"])
        results["steps"]["hud_processing"] = hud_result

        if not hud_result["success"]:
            results["success"] = False
            print(f"\n⚠️ Pipeline completed with HUD errors")
            # Continue anyway - might have partial results

        # Step 3: Generate PDF
        pdf_result = self.generate_pdf()
        results["steps"]["pdf_generation"] = pdf_result

        if not pdf_result["success"]:
            print(f"⚠️ PDF generation failed - continuing")

        # Step 4: Update Excel with results
        if hud_result.get("results_path"):
            excel_result = self.update_excel(excel_path, hud_result["results_path"])
            results["steps"]["excel_update"] = excel_result

            if excel_result["success"]:
                results["updated_excel"] = excel_result["excel_path"]
        else:
            print("⚠️ Skipping Excel update - no HUD results")

        # Summary
        print("\n" + "=" * 60)
        print("✨ Pipeline Complete!")
        print(f"📂 Output Directory: {self.output_dir}")

        if results.get("updated_excel"):
            print(f"📊 Updated Excel: {Path(results['updated_excel']).name}")

        if pdf_result.get("pdf_path"):
            print(f"📑 PDF Report: {Path(pdf_result['pdf_path']).name}")

        print("=" * 60)

        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Process Excel file through HUD pipeline"
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

    args = parser.parse_args()

    # Verify input file exists
    if not Path(args.excel_file).exists():
        print(f"❌ Error: File not found: {args.excel_file}")
        sys.exit(1)

    # Run pipeline
    pipeline = HUDPipeline(output_dir=args.output)
    results = pipeline.run(args.excel_file)

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()