#!/usr/bin/env python3
"""
Test script for HUD Pipeline
Creates a sample Excel file and runs it through the pipeline
"""

import pandas as pd
from pathlib import Path
from hud_pipeline import HUDPipeline
import sys


def create_sample_excel():
    """Create a sample Excel file for testing"""

    # Sample tank data
    data = {
        'Tank ID': ['T-001', 'T-002', 'T-003', 'T-004', 'T-005'],
        'Tank Dimensions': ['10 x 20 ft', '15 x 30 ft', None, '8 x 16 ft', None],
        'Tank Capacity': [None, None, '50000 gal', None, '25000 gal'],
        'Type': ['Diesel', 'Gasoline', 'LPG', 'Diesel', 'Fuel'],
        'Has Dike': ['Yes', 'Yes', 'No', 'Yes', 'No'],
        'Dike Dimensions': ['12 x 22 ft', '17 x 32 ft', None, '10 x 18 ft', None],
        'Location': ['Site A', 'Site A', 'Site B', 'Site C', 'Site C']
    }

    df = pd.DataFrame(data)

    # Save to Excel
    excel_path = Path("sample_tanks.xlsx")
    df.to_excel(excel_path, index=False, sheet_name='Tanks')

    print(f"✅ Created sample Excel: {excel_path}")
    print(f"   Contains {len(df)} tanks")

    return str(excel_path)


def test_individual_tools(excel_path):
    """Test individual tools separately"""
    print("\n" + "="*60)
    print("Testing Individual Tools")
    print("="*60)

    import subprocess

    # Test 1: Excel to JSON
    print("\n1. Testing Excel to JSON conversion...")
    result = subprocess.run(
        [sys.executable, "excel_to_json_improved.py", excel_path, "-o", "test_config.json"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("   ✅ Excel to JSON: SUCCESS")
    else:
        print(f"   ❌ Excel to JSON: FAILED\n   {result.stderr}")
        return False

    # Test 2: Validate JSON created
    if Path("test_config.json").exists():
        print("   ✅ JSON file created")
    else:
        print("   ❌ JSON file not found")
        return False

    print("\n✅ Individual tool tests passed")
    return True


def test_full_pipeline(excel_path):
    """Test the complete pipeline"""
    print("\n" + "="*60)
    print("Testing Complete Pipeline")
    print("="*60)

    # Initialize pipeline
    pipeline = HUDPipeline(output_dir="test_output")

    # Run pipeline
    results = pipeline.run(excel_path)

    # Check results
    print("\n" + "="*60)
    print("Test Results")
    print("="*60)

    if results["success"]:
        print("✅ Pipeline completed successfully")

        # Check outputs
        output_dir = Path(results["output_dir"])

        files_to_check = [
            ("tank_config.json", "Tank configuration"),
            ("hud_results.json", "HUD results"),
            ("HUD_Results.pdf", "PDF report"),
            ("Updated_Excel_with_HUD.xlsx", "Updated Excel")
        ]

        print("\nOutput files:")
        for filename, description in files_to_check:
            file_path = output_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✅ {description}: {filename} ({size} bytes)")
            else:
                print(f"  ⚠️ {description}: {filename} (not found)")
    else:
        print("❌ Pipeline failed")

        # Show which steps failed
        for step_name, step_result in results["steps"].items():
            status = "✅" if step_result.get("success") else "❌"
            print(f"  {status} {step_name}")
            if not step_result.get("success"):
                print(f"      Error: {step_result.get('error')}")

    return results["success"]


def main():
    """Main test function"""
    print("🧪 HUD Pipeline Test Suite")
    print("="*60)

    # Create sample data
    excel_path = create_sample_excel()

    # Test individual tools
    if not test_individual_tools(excel_path):
        print("\n⚠️ Skipping pipeline test due to tool failures")
        return 1

    # Test full pipeline
    if not test_full_pipeline(excel_path):
        return 1

    print("\n" + "="*60)
    print("✅ All tests completed successfully!")
    print("="*60)

    # Cleanup
    print("\nCleanup:")
    print("  - Sample Excel: sample_tanks.xlsx")
    print("  - Test outputs: test_output/")
    print("  - Test config: test_config.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())