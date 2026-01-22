#!/usr/bin/env python3
"""
Test Script for Agent Excel Tool
Creates sample data and tests agent decision-making
"""

import pandas as pd
from pathlib import Path
import json
import sys
from excel_analysis_tool import analyze_excel_for_conversion, apply_conversion_decisions
from agent_example import TankProcessingAgent


def create_sample_excel(filename="sample_tanks.xlsx"):
    """Create a sample Excel file with various scenarios"""

    # Create test data with different challenges for the agent
    data = {
        'Tank ID': ['T-001', 'T-002', None, 'Tank-004', '005', 'T-006', None],
        'Dimensions': ['10 x 20 ft', '15 x 30', '8x16', None, None, 'D:12 L:24', None],
        'Capacity': [None, None, None, '50000 gal', '1000 bbl', None, '30000'],
        'Type': ['Diesel', 'Gasoline', None, 'LPG', 'diesel', 'FUEL', None],
        'Has Dike': ['Yes', 'No', True, False, 'Y', None, 'Si'],
        'Notes': ['Standard tank', None, 'Small tank', 'Large capacity', 'In barrels', 'Check dimensions', 'Ambiguous']
    }

    df = pd.DataFrame(data)

    # Create Excel with multiple sheets to test sheet selection
    with pd.ExcelWriter(filename) as writer:
        df.to_excel(writer, sheet_name='Tank Data', index=False)

        # Add a decoy sheet
        decoy = pd.DataFrame({'Random': [1, 2, 3], 'Data': ['A', 'B', 'C']})
        decoy.to_excel(writer, sheet_name='Other Info', index=False)

        # Add an empty sheet
        empty = pd.DataFrame()
        empty.to_excel(writer, sheet_name='Empty', index=False)

    print(f"✅ Created sample Excel: {filename}")
    print(f"   Rows: {len(df)}")
    print(f"   Sheets: Tank Data, Other Info, Empty")

    return filename


def test_analysis_only(excel_file):
    """Test the analysis tool without agent decisions"""
    print("\n" + "="*60)
    print("TEST 1: Analysis Tool Output (No Decisions)")
    print("="*60)

    # Get analysis from tool
    analysis = analyze_excel_for_conversion(excel_file)

    if not analysis["success"]:
        print(f"❌ Analysis failed: {analysis.get('error')}")
        return False

    print(f"\n✅ Analysis successful")
    print(f"   Sheets found: {analysis['sheets_available']}")
    print(f"   Recommended: {analysis['recommended_sheet']}")
    print(f"   Rows analyzed: {len(analysis['rows_analyzed'])}")

    # Show sample analysis
    print("\n📊 Sample Row Analysis:")
    for row in analysis["rows_analyzed"][:3]:
        if row["has_data"]:
            print(f"\nRow {row['row_index']}:")

            # Tank IDs found
            if row["possible_tank_ids"]:
                print("  Possible Tank IDs:")
                for id_opt in row["possible_tank_ids"]:
                    print(f"    - {id_opt['value']} (confidence: {id_opt['confidence']})")

            # Conversions possible
            if row["conversion_possibilities"]:
                print("  Conversion Options:")
                for conv in row["conversion_possibilities"]:
                    print(f"    Column: {conv['column']} = '{conv['raw_value']}'")
                    for poss in conv["possibilities"]:
                        conf = poss.get("confidence", "unknown")
                        result = poss.get("result_gallons", "N/A")
                        print(f"      → {poss.get('interpretation', 'Unknown')}")
                        print(f"        Result: {result} gal (confidence: {conf})")

    return True


def test_agent_decisions(excel_file, confidence="medium"):
    """Test agent making decisions"""
    print("\n" + "="*60)
    print(f"TEST 2: Agent Decision Making (Confidence: {confidence})")
    print("="*60)

    # Create agent
    agent = TankProcessingAgent(confidence_threshold=confidence, verbose=False)

    # Process Excel
    result = agent.process_excel(excel_file)

    if "error" in result:
        print(f"❌ Processing failed: {result['error']}")
        return False

    print(f"\n✅ Agent processed {len(result.get('tanks', []))} tanks")

    # Show decisions made
    print("\n🎯 Agent Decisions:")
    for tank in result.get("tanks", [])[:5]:
        print(f"\nTank: {tank['name']}")
        print(f"  Capacity: {tank.get('capacity', 0):,.0f} gallons")
        print(f"  Method: {tank.get('_conversion_method', 'unknown')}")
        print(f"  Type: {tank.get('type', 'unknown')}")
        print(f"  Has Dike: {tank.get('hasDike', False)}")

        if "_agent_reasoning" in tank:
            print("  Reasoning:")
            for reason in tank["_agent_reasoning"]:
                print(f"    → {reason}")

    # Show statistics
    print("\n📊 Statistics:")
    total_capacity = sum(t.get("capacity", 0) for t in result.get("tanks", []))
    methods = {}
    for tank in result.get("tanks", []):
        method = tank.get("_conversion_method", "unknown")
        methods[method] = methods.get(method, 0) + 1

    print(f"  Total Capacity: {total_capacity:,.0f} gallons")
    print(f"  Conversion Methods:")
    for method, count in methods.items():
        print(f"    - {method}: {count}")

    return True


def test_manual_decisions(excel_file):
    """Test manual decision application"""
    print("\n" + "="*60)
    print("TEST 3: Manual Decision Application")
    print("="*60)

    # Get analysis
    analysis = analyze_excel_for_conversion(excel_file)

    if not analysis["success"]:
        print(f"❌ Analysis failed")
        return False

    # Create manual decisions (simulating what an agent would do)
    decisions = []

    for row in analysis["rows_analyzed"]:
        if not row["has_data"]:
            continue

        decision = {
            "row_index": row["row_index"],
            "tank_id": f"MANUAL-{row['row_index'] + 1}",
            "agent_reasoning": ["Manual test decision"]
        }

        # Pick first conversion option if available
        if row["conversion_possibilities"]:
            for conv in row["conversion_possibilities"]:
                if conv["possibilities"]:
                    decision["use_conversion"] = conv["possibilities"][0]
                    break

        decisions.append(decision)

    print(f"📝 Created {len(decisions)} manual decisions")

    # Apply decisions
    result = apply_conversion_decisions(analysis, decisions)

    print(f"✅ Applied decisions: {result['agent_decisions_applied']}")
    print(f"   Tanks created: {len(result['tanks'])}")
    print(f"   Skipped rows: {len(result['skipped_rows'])}")

    return True


def test_confidence_levels(excel_file):
    """Test different confidence thresholds"""
    print("\n" + "="*60)
    print("TEST 4: Confidence Level Comparison")
    print("="*60)

    results = {}

    for confidence in ["high", "medium", "low"]:
        agent = TankProcessingAgent(confidence_threshold=confidence, verbose=False)
        result = agent.process_excel(excel_file)

        tanks = result.get("tanks", [])
        total_capacity = sum(t.get("capacity", 0) for t in tanks)
        tanks_with_capacity = len([t for t in tanks if t.get("capacity", 0) > 0])

        results[confidence] = {
            "total_tanks": len(tanks),
            "with_capacity": tanks_with_capacity,
            "total_gallons": total_capacity
        }

        print(f"\n{confidence.upper()} Confidence:")
        print(f"  Tanks: {len(tanks)}")
        print(f"  With Capacity: {tanks_with_capacity}")
        print(f"  Total: {total_capacity:,.0f} gallons")

    return True


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("AGENT EXCEL TOOL - TEST SUITE")
    print("="*60)

    # Create sample data
    excel_file = create_sample_excel()

    tests = [
        ("Analysis Only", lambda: test_analysis_only(excel_file)),
        ("Agent Decisions", lambda: test_agent_decisions(excel_file)),
        ("Manual Decisions", lambda: test_manual_decisions(excel_file)),
        ("Confidence Levels", lambda: test_confidence_levels(excel_file))
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(tests)}")

    return failed == 0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Agent Excel Tool")
    parser.add_argument("excel_file", nargs="?", help="Excel file to test")
    parser.add_argument("--create", action="store_true", help="Just create sample Excel")
    parser.add_argument("--confidence", default="medium", help="Confidence threshold")

    args = parser.parse_args()

    if args.create:
        # Just create sample file
        create_sample_excel()
        print("\n✅ Sample file created: sample_tanks.xlsx")

    elif args.excel_file:
        # Test specific file
        if not Path(args.excel_file).exists():
            print(f"❌ File not found: {args.excel_file}")
            sys.exit(1)

        print(f"Testing with: {args.excel_file}")
        test_agent_decisions(args.excel_file, args.confidence)

    else:
        # Run full test suite
        success = run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()