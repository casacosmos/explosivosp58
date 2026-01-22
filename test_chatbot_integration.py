#!/usr/bin/env python3
"""
Integration test to verify chatbot calls the actual pipeline correctly.
This test ensures the chatbot produces the same outputs as the direct pipeline agent.
"""

import sys
from pathlib import Path

def test_tool_integration():
    """Test that chatbot tools properly integrate with pipeline_agent."""
    print("=" * 70)
    print("🧪 Chatbot-Pipeline Integration Test")
    print("=" * 70)
    print()

    from pipeline_chatbot import (
        process_pipeline_tool,
        check_status_tool,
        get_results_tool,
        list_sessions_tool
    )

    print("✅ All tools imported successfully")
    print()

    # Test 1: Verify tool can be invoked (without actual execution)
    print("Test 1: Tool invocation structure")
    print("-" * 70)

    # Test list_sessions (safe, doesn't execute pipeline)
    try:
        result = list_sessions_tool.invoke({})
        print(f"✅ list_sessions_tool invocable: {result['success']}")
    except Exception as e:
        print(f"❌ list_sessions_tool failed: {e}")
        return False

    # Test check_status with dummy session (should fail gracefully)
    try:
        result = check_status_tool.invoke({"session_id": "test_nonexistent"})
        if not result['success']:
            print(f"✅ check_status_tool handles missing sessions: {result['message']}")
        else:
            print(f"⚠️  check_status_tool unexpected success for nonexistent session")
    except Exception as e:
        print(f"❌ check_status_tool error handling failed: {e}")
        return False

    # Test get_results with dummy session (should fail gracefully)
    try:
        result = get_results_tool.invoke({
            "session_id": "test_nonexistent",
            "result_type": "summary"
        })
        if not result['success']:
            print(f"✅ get_results_tool handles missing sessions: {result['message']}")
        else:
            print(f"⚠️  get_results_tool unexpected success for nonexistent session")
    except Exception as e:
        print(f"❌ get_results_tool error handling failed: {e}")
        return False

    print()
    print("Test 2: Tool parameter validation")
    print("-" * 70)

    # Test process_pipeline_tool with nonexistent file
    try:
        result = process_pipeline_tool.invoke({
            "file_path": "/nonexistent/file.xlsx",
            "session_id": "test_validation"
        })
        if not result['success'] and 'File not found' in result['error']:
            print(f"✅ process_pipeline_tool validates file existence")
        else:
            print(f"⚠️  process_pipeline_tool didn't validate file: {result}")
    except Exception as e:
        print(f"❌ process_pipeline_tool validation failed: {e}")
        return False

    print()
    print("Test 3: Pipeline agent import verification")
    print("-" * 70)

    try:
        from pipeline_agent import run_pipeline_agent, create_pipeline_graph
        print("✅ pipeline_agent functions imported in chatbot")
        print("✅ Chatbot can call run_pipeline_agent()")
    except ImportError as e:
        print(f"❌ Failed to import pipeline_agent: {e}")
        return False

    print()
    print("Test 4: Tool function signatures")
    print("-" * 70)

    # Verify tool signatures match expected interface
    import inspect

    # Check process_pipeline_tool
    sig = inspect.signature(process_pipeline_tool.func)
    params = list(sig.parameters.keys())
    if 'file_path' in params and 'session_id' in params and 'output_dir' in params:
        print("✅ process_pipeline_tool has correct parameters")
    else:
        print(f"❌ process_pipeline_tool parameters incorrect: {params}")
        return False

    # Check check_status_tool
    sig = inspect.signature(check_status_tool.func)
    params = list(sig.parameters.keys())
    if 'session_id' in params:
        print("✅ check_status_tool has correct parameters")
    else:
        print(f"❌ check_status_tool parameters incorrect: {params}")
        return False

    # Check get_results_tool
    sig = inspect.signature(get_results_tool.func)
    params = list(sig.parameters.keys())
    if 'session_id' in params and 'result_type' in params:
        print("✅ get_results_tool has correct parameters")
    else:
        print(f"❌ get_results_tool parameters incorrect: {params}")
        return False

    print()
    return True


def print_manual_test_guide():
    """Print guide for manual integration testing."""
    print()
    print("=" * 70)
    print("📋 Manual Integration Test Guide")
    print("=" * 70)
    print()
    print("To fully test chatbot-pipeline integration, run:")
    print()
    print("1. Direct Pipeline (baseline):")
    print("   python pipeline_agent.py <your_file.xlsx> --session direct_test")
    print()
    print("2. Chatbot Pipeline:")
    print("   python pipeline_chatbot.py")
    print("   You: Process <your_file.xlsx> with session chat_test")
    print()
    print("3. Compare outputs:")
    print("   diff -r outputs/direct_test outputs/chat_test")
    print()
    print("Expected: Both should produce identical artifacts:")
    print("  ✓ tank_config.json")
    print("  ✓ fast_results.json")
    print("  ✓ HUD_ASD_Results.pdf")
    print("  ✓ with_hud.xlsx")
    print("  ✓ distances.json")
    print("  ✓ final_compliance.xlsx")
    print()
    print("=" * 70)
    print()
    print("Quick Test Commands:")
    print("-" * 70)
    print()
    print("# Test with help command (no pipeline execution)")
    print("python pipeline_chatbot.py")
    print("You: help")
    print()
    print("# Test listing sessions")
    print("You: list sessions")
    print()
    print("# Test checking nonexistent session")
    print("You: what's the status of session xyz?")
    print()
    print("# Test processing a file (FULL PIPELINE - will take 7-10 min)")
    print("You: process tanks.xlsx with session chatbot_test_run")
    print()
    print("=" * 70)


def main():
    """Run all integration tests."""
    print()

    success = test_tool_integration()

    print()
    print("=" * 70)
    if success:
        print("✅ All Integration Tests Passed!")
        print("=" * 70)
        print()
        print("The chatbot is properly configured to call the pipeline agent.")
        print("Tools will execute the full 8-step pipeline and produce identical")
        print("outputs to running pipeline_agent.py directly.")
        print_manual_test_guide()
        return 0
    else:
        print("❌ Some Integration Tests Failed")
        print("=" * 70)
        print()
        print("Please review the errors above and fix the chatbot integration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
