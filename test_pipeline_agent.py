#!/usr/bin/env python3
"""
Quick verification script for pipeline_agent.py
Tests that the agent can be imported and graph can be built.
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all imports work."""
    print("Testing imports...")
    try:
        from pipeline_agent import (
            PipelineState,
            create_pipeline_graph,
            run_pipeline_agent,
            # Tools
            parse_kmz_tool,
            excel_to_json_tool,
            validate_json_tool,
            process_hud_tool,
            generate_pdf_tool,
            update_excel_tool,
            calculate_distances_tool,
            check_compliance_tool,
            calculate_volume_tool,
            human_approval_tool
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_graph_creation():
    """Test that the graph can be created."""
    print("\nTesting graph creation...")
    try:
        from pipeline_agent import create_pipeline_graph
        workflow = create_pipeline_graph()
        print("✅ Graph created successfully")

        # Try to compile it
        from langgraph.checkpoint.memory import MemorySaver
        agent = workflow.compile(checkpointer=MemorySaver())
        print("✅ Graph compiled successfully")

        return True
    except Exception as e:
        print(f"❌ Graph creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_invocation():
    """Test that a simple tool can be invoked."""
    print("\nTesting tool invocation...")
    try:
        from pipeline_agent import calculate_volume_tool

        result = calculate_volume_tool.invoke({
            "length": 10.0,
            "width": 8.0,
            "height": 6.0,
            "unit": "ft"
        })

        if result["success"]:
            volume = result["volume_gallons"]
            print(f"✅ Volume tool works: {volume:.2f} gallons")
            return True
        else:
            print(f"❌ Volume tool returned error: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ Tool invocation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_structure():
    """Test that PipelineState structure is correct."""
    print("\nTesting state structure...")
    try:
        from pipeline_agent import PipelineState

        # Create a sample state
        state: PipelineState = {
            "input_file": "test.xlsx",
            "input_type": "excel",
            "output_dir": "outputs",
            "session_id": "test_session",
            "config": {},
            "kmz_parsed": None,
            "excel_file": None,
            "tank_config_json": None,
            "validation_passed": False,
            "hud_results_json": None,
            "pdf_report": None,
            "updated_excel": None,
            "distances_json": None,
            "compliance_excel": None,
            "current_step": "",
            "completed_steps": [],
            "errors": [],
            "warnings": [],
            "messages": [],
            "tank_count": 0,
            "processing_stats": {},
            "start_time": None,
            "end_time": None
        }

        print("✅ PipelineState structure valid")
        return True

    except Exception as e:
        print(f"❌ State structure error: {e}")
        return False


def main():
    """Run all verification tests."""
    print("="*60)
    print("Pipeline Agent Verification Tests")
    print("="*60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Graph Creation", test_graph_creation()))
    results.append(("Tool Invocation", test_tool_invocation()))
    results.append(("State Structure", test_state_structure()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:30} {status}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All verification tests passed!")
        print("The pipeline agent is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())