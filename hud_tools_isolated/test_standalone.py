#!/usr/bin/env python3
"""
Test script for standalone Excel to JSON converter
Demonstrates it works without any external dependencies
"""

import json
import pandas as pd
from pathlib import Path
import sys

# Import the standalone module
from excel_to_json_standalone import (
    parse_excel_with_adjustments,
    save_json_output,
    suggest_corrections
)


def create_test_excel(filename="test_tanks_standalone.xlsx"):
    """Create a test Excel file with various scenarios"""

    # Create test data with different column names and data types
    data = {
        # English columns
        'Tank ID': ['T-001', 'T-002', 'T-003', 'T-004', 'T-005', None, 'T-007'],
        'Tank Dimensions': ['10 x 20 ft', '15 x 30 ft', None, '8x16', '12 x 24', '10 x 20', None],
        'Capacity': [None, None, '50000 gal', '10000', None, '25000 gallons', '30000 bbl'],
        'Fuel Type': ['Diesel', 'Gasoline', 'LPG', None, 'diesel', 'FUEL', 'Pressurized Gas'],
        'Has Dike': ['Yes', 'Y', 'No', True, False, 'Si', None],
        'Location': ['Site A', 'Site B', 'Site C', None, 'Site D', 'Site E', 'Site F'],
        'Notes': ['Test tank 1', None, 'Large capacity', 'Small tank', None, 'Medium', 'Barrels']
    }

    df = pd.DataFrame(data)

    # Create multi-sheet Excel
    with pd.ExcelWriter(filename) as writer:
        df.to_excel(writer, sheet_name='Tanks', index=False)

        # Add a Spanish sheet
        spanish_data = {
            'Código del Tanque': ['ES-001', 'ES-002', 'ES-003'],
            'Dimensiones': ['10 x 15 ft', '20 x 30 ft', '15 x 25 ft'],
            'Capacidad': ['20000 gal', None, '40000'],
            'Tipo': ['Diesel', 'Gasolina', 'LPG'],
            'Tiene Dique': ['Sí', 'No', 'Sí']
        }
        df_spanish = pd.DataFrame(spanish_data)
        df_spanish.to_excel(writer, sheet_name='Tanques', index=False)

        # Add empty sheet
        df_empty = pd.DataFrame()
        df_empty.to_excel(writer, sheet_name='Empty', index=False)

    print(f"✅ Created test Excel: {filename}")
    return filename


def test_basic_parsing():
    """Test basic parsing functionality"""
    print("\n" + "="*60)
    print("Test 1: Basic AUTO Mode Parsing")
    print("="*60)

    # Create test file
    excel_file = create_test_excel("test_auto.xlsx")

    # Parse with auto mode
    result = parse_excel_with_adjustments(
        excel_path=excel_file,
        mode="auto"
    )

    assert result["success"], f"Auto parsing failed: {result.get('error')}"
    assert len(result["tanks"]) > 0, "No tanks parsed"

    print(f"✅ Parsed {len(result['tanks'])} tanks")
    print(f"   Metadata: {result['metadata'].get('tank_count')} tanks total")

    # Show sample
    if result["tanks"]:
        print("\n📊 Sample tank:")
        print(json.dumps(result["tanks"][0], indent=2))

    return result


def test_fuzzy_parsing():
    """Test fuzzy column matching"""
    print("\n" + "="*60)
    print("Test 2: FUZZY Mode Parsing")
    print("="*60)

    excel_file = "test_auto.xlsx"  # Reuse file

    result = parse_excel_with_adjustments(
        excel_path=excel_file,
        mode="fuzzy"
    )

    assert result["success"], f"Fuzzy parsing failed: {result.get('error')}"
    print(f"✅ Fuzzy mode parsed {len(result['tanks'])} tanks")

    return result


def test_manual_mapping():
    """Test manual column mapping"""
    print("\n" + "="*60)
    print("Test 3: MANUAL Mode with Column Overrides")
    print("="*60)

    excel_file = "test_auto.xlsx"

    # Define manual mappings
    column_mappings = {
        "tank_id": "Tank ID",
        "dimensions": "Tank Dimensions",
        "capacity": "Capacity",
        "type": "Fuel Type",
        "has_dike": "Has Dike",
        "location": "Location"
    }

    result = parse_excel_with_adjustments(
        excel_path=excel_file,
        mode="manual",
        column_overrides=column_mappings
    )

    assert result["success"], f"Manual parsing failed: {result.get('error')}"
    print(f"✅ Manual mode parsed {len(result['tanks'])} tanks")

    return result


def test_corrections():
    """Test value corrections"""
    print("\n" + "="*60)
    print("Test 4: Value Corrections")
    print("="*60)

    excel_file = "test_auto.xlsx"

    # Define corrections
    corrections = [
        {"tank_id": "T-001", "field": "capacity_raw", "value": "15000 gal"},
        {"tank_id": "T-002", "field": "type", "value": "diesel"},
        {"tank_id": "T-004", "field": "has_dike", "value": True}
    ]

    result = parse_excel_with_adjustments(
        excel_path=excel_file,
        mode="auto",
        value_corrections=corrections
    )

    assert result["success"], f"Parsing with corrections failed"
    assert result["adjustments_applied"] == corrections, "Corrections not applied"

    print(f"✅ Applied {len(corrections)} corrections")
    print(f"   Tanks with corrections: {[t['name'] for t in result['tanks'] if t.get('_metadata', {}).get('corrected')]}")

    return result


def test_ai_guided():
    """Test AI-guided parsing with hints"""
    print("\n" + "="*60)
    print("Test 5: AI-Guided Mode with Hints")
    print("="*60)

    excel_file = "test_auto.xlsx"

    # Provide parsing hints
    hints = {
        "units": "gallons",
        "default_type": "diesel",
        "skip_rows": [],
        "tank_id_pattern": r"T-\d{3}"
    }

    result = parse_excel_with_adjustments(
        excel_path=excel_file,
        mode="ai_guided",
        parsing_hints=hints
    )

    assert result["success"], f"AI-guided parsing failed"
    print(f"✅ AI-guided mode parsed {len(result['tanks'])} tanks")
    print(f"   Applied default type to tanks: {[t['name'] for t in result['tanks'] if t.get('type') == 'diesel']}")

    return result


def test_suggestions():
    """Test suggestions feature"""
    print("\n" + "="*60)
    print("Test 6: Suggestions and Analysis")
    print("="*60)

    excel_file = "test_auto.xlsx"

    suggestions = suggest_corrections(excel_file)

    assert suggestions.get("success"), f"Suggestions failed: {suggestions.get('error')}"

    print("✅ Suggestions generated:")
    if suggestions.get("column_mappings"):
        print(f"   Detected {len(suggestions['column_mappings'])} column mappings")

    if suggestions.get("data_issues"):
        print(f"   Found {len(suggestions['data_issues'])} data issues")

    if suggestions.get("recommendations"):
        print("   Recommendations:")
        for rec in suggestions["recommendations"]:
            print(f"     - {rec}")

    return suggestions


def test_volume_calculations():
    """Test embedded volume calculator"""
    print("\n" + "="*60)
    print("Test 7: Volume Calculations")
    print("="*60)

    # Create test data with various dimension formats
    data = {
        'Tank ID': ['V-001', 'V-002', 'V-003', 'V-004', 'V-005'],
        'Dimensions': ['10 x 20 ft', '15x30', 'D:8 L:16', '12 ft x 24 ft', None],
        'Capacity': [None, None, None, None, '1260 bbl']
    }

    df = pd.DataFrame(data)
    test_file = "test_volumes.xlsx"
    df.to_excel(test_file, index=False)

    result = parse_excel_with_adjustments(
        excel_path=test_file,
        mode="auto"
    )

    assert result["success"], "Volume calculation failed"

    print("✅ Volume calculations:")
    for tank in result["tanks"]:
        volume = tank.get("capacity", 0)
        source = tank.get("_metadata", {}).get("volume_source", "unknown")
        print(f"   {tank['name']}: {volume:,.0f} gallons ({source})")

    return result


def test_spanish_columns():
    """Test parsing with Spanish column names"""
    print("\n" + "="*60)
    print("Test 8: Spanish Column Names")
    print("="*60)

    # Create Spanish test file
    data = {
        'Código del Tanque': ['ES-001', 'ES-002', 'ES-003'],
        'Dimensiones': ['10 x 15 ft', '20 x 30 ft', '15 x 25 ft'],
        'Capacidad': ['20000 gal', None, '40000'],
        'Tipo de Combustible': ['Diesel', 'Gasolina', 'LPG'],
        'Tiene Dique': ['Sí', 'No', 'Sí']
    }

    df = pd.DataFrame(data)
    spanish_file = "test_spanish.xlsx"
    df.to_excel(spanish_file, index=False)

    # Parse with manual mappings
    spanish_mappings = {
        "tank_id": "Código del Tanque",
        "dimensions": "Dimensiones",
        "capacity": "Capacidad",
        "type": "Tipo de Combustible",
        "has_dike": "Tiene Dique"
    }

    result = parse_excel_with_adjustments(
        excel_path=spanish_file,
        mode="manual",
        column_overrides=spanish_mappings
    )

    assert result["success"], "Spanish parsing failed"
    print(f"✅ Parsed {len(result['tanks'])} Spanish tanks")

    return result


def test_save_output():
    """Test saving to JSON"""
    print("\n" + "="*60)
    print("Test 9: Save JSON Output")
    print("="*60)

    # Use previous result
    excel_file = "test_auto.xlsx"
    result = parse_excel_with_adjustments(excel_file)

    # Save to JSON
    output_file = "test_output.json"
    save_result = save_json_output(result, output_file)

    assert save_result["success"], f"Save failed: {save_result.get('error')}"
    assert Path(output_file).exists(), "Output file not created"

    # Verify JSON content
    with open(output_file) as f:
        saved_data = json.load(f)

    assert "tanks" in saved_data, "Missing tanks in saved JSON"
    assert "metadata" in saved_data, "Missing metadata in saved JSON"
    assert "timestamp" in saved_data, "Missing timestamp in saved JSON"

    print(f"✅ Saved {save_result['tank_count']} tanks to {save_result['path']}")

    return save_result


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("STANDALONE EXCEL TO JSON CONVERTER - TEST SUITE")
    print("="*60)
    print("Testing without any external dependencies...")

    tests = [
        ("Basic Parsing", test_basic_parsing),
        ("Fuzzy Matching", test_fuzzy_parsing),
        ("Manual Mapping", test_manual_mapping),
        ("Value Corrections", test_corrections),
        ("AI-Guided Mode", test_ai_guided),
        ("Suggestions", test_suggestions),
        ("Volume Calculations", test_volume_calculations),
        ("Spanish Columns", test_spanish_columns),
        ("Save Output", test_save_output)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} failed: {e}")
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(tests)}")

    # Cleanup
    print("\n🧹 Cleaning up test files...")
    for file in Path(".").glob("test_*.xlsx"):
        file.unlink()
        print(f"   Removed: {file}")

    for file in Path(".").glob("test_*.json"):
        file.unlink()
        print(f"   Removed: {file}")

    return failed == 0


def main():
    """Main test runner"""
    if len(sys.argv) > 1:
        # Test with provided file
        excel_file = sys.argv[1]
        print(f"Testing with: {excel_file}")

        result = parse_excel_with_adjustments(excel_file)

        if result["success"]:
            print(f"✅ Parsed {len(result['tanks'])} tanks")
            save_result = save_json_output(result, "standalone_output.json")
            if save_result["success"]:
                print(f"📁 Saved to: {save_result['path']}")
        else:
            print(f"❌ Failed: {result.get('error')}")

    else:
        # Run test suite
        success = run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()