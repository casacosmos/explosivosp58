#!/usr/bin/env python3
"""
Test the simplified chatbot functionality.
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all imports work."""
    print("Testing imports...")
    try:
        from simple_chatbot import (
            process_file_tool,
            fill_tank_data_tool,
            create_template_tool,
            help_tool,
            create_simple_chatbot
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_tools():
    """Test individual tools."""
    print("\nTesting tools...")

    from simple_chatbot import help_tool, create_template_tool

    # Test help tool
    try:
        result = help_tool.invoke({})
        if result["success"]:
            print("✅ help_tool works")
        else:
            print("❌ help_tool failed")
            return False
    except Exception as e:
        print(f"❌ help_tool error: {e}")
        return False

    # Test create_template_tool
    try:
        test_template = "test_template.xlsx"
        result = create_template_tool.invoke({
            "tank_count": 5,
            "output_path": test_template
        })
        if result["success"]:
            print(f"✅ create_template_tool works")
            # Clean up
            Path(test_template).unlink(missing_ok=True)
        else:
            print(f"❌ create_template_tool failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ create_template_tool error: {e}")
        return False

    return True


def test_graph_creation():
    """Test that chatbot graph can be created."""
    print("\nTesting graph creation...")
    try:
        from simple_chatbot import create_simple_chatbot
        from langgraph.checkpoint.memory import MemorySaver

        graph_builder = create_simple_chatbot()
        checkpointer = MemorySaver()
        graph = graph_builder.compile(checkpointer=checkpointer)

        print("✅ Graph created successfully")
        return True
    except Exception as e:
        print(f"❌ Graph creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_integration():
    """Test that pipeline agent is properly integrated."""
    print("\nTesting pipeline integration...")
    try:
        from pipeline_agent import create_output_kmz_tool
        print("✅ create_output_kmz_tool imported")

        # Check that the tool is properly defined
        if hasattr(create_output_kmz_tool, 'invoke'):
            print("✅ create_output_kmz_tool is invocable")
        else:
            print("❌ create_output_kmz_tool missing invoke method")
            return False

        return True
    except Exception as e:
        print(f"❌ Pipeline integration error: {e}")
        return False


def print_workflow_summary():
    """Print summary of the workflow."""
    print("\n" + "=" * 70)
    print("📋 Simplified Chatbot Workflow Summary")
    print("=" * 70)
    print("""
**What changed:**
- ❌ Removed complex session management
- ❌ Removed session tracking tools
- ✅ Added simple process_file_tool that handles everything
- ✅ Added fill_tank_data_tool for conversational data entry
- ✅ Added create_template_tool for blank templates
- ✅ Added create_output_kmz step to pipeline

**Complete Pipeline Flow:**
1. User provides KMZ/Excel OR asks for template
2. If KMZ: Parse → Create Excel template → Fill via chat (optional)
3. Convert measurements → volumes → JSON
4. Use HUD tool (Playwright) → Retrieve data + screenshots
5. Update Excel with HUD results
6. Calculate distances to boundaries
7. Determine compliance (YES/NO/REVIEW)
8. Create output KMZ with tank locations labeled by capacities
9. Generate final reports

**Output Files:**
- tank_config.json (structured tank data)
- fast_results.json (HUD query results)
- HUD_ASD_Results.pdf (screenshots)
- with_hud.xlsx (Excel with HUD data)
- distances.json (boundary distances)
- final_compliance.xlsx (compliance report)
- tanks_output.kmz (Google Earth file with labeled tanks) ← NEW!

**Example Usage:**
Bot: Type 'help' for instructions
You: Process tanks.kmz
Bot: [Runs complete pipeline, outputs KMZ with labeled locations]

You: Create template for 10 tanks
Bot: [Creates blank Excel template]

You: Tank T-01 has 50000 gallons, 30x20x15 ft, stores Diesel
Bot: [Fills Excel with provided data]
""")
    print("=" * 70)


def main():
    """Run all tests."""
    print("=" * 70)
    print("🧪 Simple Chatbot Test Suite")
    print("=" * 70)
    print()

    tests = [
        ("Imports", test_imports),
        ("Tools", test_tools),
        ("Graph Creation", test_graph_creation),
        ("Pipeline Integration", test_pipeline_integration)
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"⚠️  {name} test had issues")
        except Exception as e:
            print(f"❌ {name} test raised exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 70)

    if passed == total:
        print("✅ All tests passed!")
        print_workflow_summary()
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())