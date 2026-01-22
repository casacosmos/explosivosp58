#!/usr/bin/env python3
"""
Test conversational Excel filling functionality.
Verifies that fill_excel_conversational_tool can properly populate Excel templates.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import tempfile
import shutil

def create_test_excel():
    """Create a test Excel template for filling."""
    # Create sample template matching KMZ workflow output
    data = {
        "Tank ID": ["T-01", "T-02", "T-03"],
        "Tank Capacity": ["", "", ""],
        "Tank Dimensions": ["", "", ""],
        "Product Stored": ["", "", ""],
        "Longitude": [-66.123, -66.124, -66.125],
        "Latitude": [18.234, 18.235, 18.236]
    }

    df = pd.DataFrame(data)

    # Create temp file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False)
    temp_path = temp_file.name
    temp_file.close()

    df.to_excel(temp_path, index=False)
    return temp_path

def test_conversational_excel_filling():
    """Test that the conversational Excel filling tool works correctly."""
    print("=" * 70)
    print("🧪 Conversational Excel Filling Test")
    print("=" * 70)
    print()

    try:
        from pipeline_chatbot import fill_excel_conversational_tool
        print("✅ fill_excel_conversational_tool imported successfully")

        # Create test Excel
        print("\n📝 Creating test Excel template...")
        test_excel_path = create_test_excel()
        print(f"✅ Created test Excel: {test_excel_path}")

        # Read original data
        df_before = pd.read_excel(test_excel_path)
        print(f"\n📊 Before filling:")
        print(df_before.to_string())

        # Test data to fill
        tank_data = [
            {
                "tank_id": "T-01",
                "capacity": "50000 gal",
                "length": "30 ft",
                "width": "20 ft",
                "height": "15 ft",
                "product": "Diesel"
            },
            {
                "tank_id": "T-02",
                "capacity": "75000 gallons",
                "length": "40 ft",
                "width": "25 ft",
                "height": "18 ft",
                "product": "Gasoline"
            },
            {
                "tank_id": "T-03",
                "capacity": "100000 gal",
                "length": "50 ft",
                "width": "30 ft",
                "height": "20 ft",
                "product": "Kerosene"
            }
        ]

        print(f"\n📥 Test tank data:")
        print(json.dumps(tank_data, indent=2))

        # Invoke the tool
        print(f"\n🔧 Invoking fill_excel_conversational_tool...")
        result = fill_excel_conversational_tool.invoke({
            "excel_path": test_excel_path,
            "tank_data": tank_data
        })

        print(f"\n📤 Tool result:")
        print(json.dumps(result, indent=2))

        if result["success"]:
            print(f"✅ Tool completed successfully")
            print(f"✅ Filled {result['tanks_filled']} tanks")

            # Read modified data
            df_after = pd.read_excel(test_excel_path)
            print(f"\n📊 After filling:")
            print(df_after.to_string())

            # Verify data was filled
            verification_passed = True

            # Check T-01
            t01_row = df_after[df_after["Tank ID"] == "T-01"].iloc[0]
            if "50000" not in str(t01_row["Tank Capacity"]):
                print("❌ T-01 capacity not filled correctly")
                verification_passed = False
            else:
                print("✅ T-01 capacity filled correctly")

            if "30" not in str(t01_row["Tank Dimensions"]) or "20" not in str(t01_row["Tank Dimensions"]):
                print("❌ T-01 dimensions not filled correctly")
                verification_passed = False
            else:
                print("✅ T-01 dimensions filled correctly")

            if "Diesel" not in str(t01_row["Product Stored"]):
                print("❌ T-01 product not filled correctly")
                verification_passed = False
            else:
                print("✅ T-01 product filled correctly")

            # Clean up
            Path(test_excel_path).unlink()

            if verification_passed:
                print("\n" + "=" * 70)
                print("✅ All Conversational Excel Filling Tests Passed!")
                print("=" * 70)
                return True
            else:
                print("\n" + "=" * 70)
                print("❌ Some verifications failed")
                print("=" * 70)
                return False
        else:
            print(f"❌ Tool failed: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def print_usage_example():
    """Print example of how to use conversational Excel filling in chatbot."""
    print("\n" + "=" * 70)
    print("📖 Usage Example in Chatbot")
    print("=" * 70)
    print("""
Scenario: Processing a KMZ file that creates an Excel template

User: Process tanks_juncos.kmz with session juncos_2025

Bot: [Parses KMZ, creates Excel template]
     I found 24 tanks and created a template at outputs/juncos_2025/tanks_template.xlsx.
     Please provide the tank details, or I can fill them from your description.

User: Tank T-01 has capacity 50000 gallons, dimensions 30ft x 20ft x 15ft, stores Diesel.
      Tank T-02 has capacity 75000 gallons, dimensions 40ft x 25ft x 18ft, stores Gasoline.

Bot: [Calls fill_excel_conversational_tool]
     ✅ Filled 2 tanks in the Excel template. Would you like to provide more tank details?

User: That's all for now, continue processing.

Bot: [Continues pipeline with filled Excel]
     Processing complete! Generated compliance report at outputs/juncos_2025/final_compliance.xlsx
""")
    print("=" * 70)

def main():
    """Run all tests."""
    success = test_conversational_excel_filling()

    if success:
        print_usage_example()
        return 0
    else:
        print("\n⚠️  Tests did not pass. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())