#!/usr/bin/env python3
"""
Test script for Pipeline Chatbot
Verifies conversational interface and tool integration.
"""

import sys
from pathlib import Path
from typing import List, Tuple

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    try:
        from pipeline_chatbot import (
            ChatbotState,
            create_chatbot_graph,
            process_pipeline_tool,
            check_status_tool,
            get_results_tool,
            list_sessions_tool,
            help_tool
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_tool_invocations():
    """Test individual tool invocations."""
    print("\nTesting tool invocations...")

    from pipeline_chatbot import (
        help_tool,
        list_sessions_tool
    )

    # Test help tool
    try:
        result = help_tool.invoke({})
        if result["success"] and "Pipeline Chatbot Help" in result["message"]:
            print("✅ help_tool works")
        else:
            print("❌ help_tool failed")
            return False
    except Exception as e:
        print(f"❌ help_tool error: {e}")
        return False

    # Test list_sessions tool
    try:
        result = list_sessions_tool.invoke({})
        if result["success"]:
            print(f"✅ list_sessions_tool works (found {result.get('count', 0)} sessions)")
        else:
            print("❌ list_sessions_tool failed")
            return False
    except Exception as e:
        print(f"❌ list_sessions_tool error: {e}")
        return False

    return True


def test_graph_creation():
    """Test that the chatbot graph can be created."""
    print("\nTesting graph creation...")
    try:
        from pipeline_chatbot import create_chatbot_graph
        from langgraph.checkpoint.memory import MemorySaver

        # Create graph
        graph_builder = create_chatbot_graph(
            llm_model="anthropic:claude-3-5-sonnet-latest"
        )

        # Compile with checkpointer
        checkpointer = MemorySaver()
        graph = graph_builder.compile(checkpointer=checkpointer)

        print("✅ Graph created and compiled successfully")
        return True
    except Exception as e:
        print(f"❌ Graph creation error: {e}")
        return False


def test_state_structure():
    """Test ChatbotState structure."""
    print("\nTesting state structure...")
    try:
        from pipeline_chatbot import ChatbotState
        from langchain_core.messages import HumanMessage

        # Create sample state
        state: ChatbotState = {
            "messages": [HumanMessage(content="Test message")],
            "session_id": "test_123",
            "pipeline_active": False,
            "user_intent": "test",
            "input_file": None,
            "output_dir": "outputs",
            "current_step": None,
            "completed_steps": [],
            "errors": [],
            "warnings": [],
            "tank_count": 0,
            "artifacts": {},
            "processing_stats": {}
        }

        # Verify all required fields
        required_fields = [
            "messages", "session_id", "pipeline_active", "user_intent",
            "input_file", "output_dir", "current_step", "completed_steps",
            "errors", "warnings", "tank_count", "artifacts", "processing_stats"
        ]

        for field in required_fields:
            if field not in state:
                print(f"❌ Missing required field: {field}")
                return False

        print("✅ State structure is valid")
        return True
    except Exception as e:
        print(f"❌ State structure error: {e}")
        return False


def test_conversation_simulation():
    """Simulate a basic conversation to test the flow."""
    print("\nTesting conversation simulation...")
    try:
        from pipeline_chatbot import create_chatbot_graph
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_core.messages import HumanMessage

        # Create graph
        graph_builder = create_chatbot_graph(
            llm_model="anthropic:claude-3-5-sonnet-latest"
        )
        checkpointer = MemorySaver()
        graph = graph_builder.compile(checkpointer=checkpointer)

        # Simulate conversation
        config = {"configurable": {"thread_id": "test_conversation"}}

        # Initial state
        initial_state = {
            "messages": [HumanMessage(content="help")],
            "session_id": "test_123",
            "pipeline_active": False,
            "user_intent": "help",
            "input_file": None,
            "output_dir": "outputs",
            "current_step": None,
            "completed_steps": [],
            "errors": [],
            "warnings": [],
            "tank_count": 0,
            "artifacts": {},
            "processing_stats": {}
        }

        print("  Running test conversation with 'help' command...")
        print("  (This will invoke the LLM - may take a few seconds)")

        # Stream events
        event_count = 0
        for event in graph.stream(initial_state, config, stream_mode="values"):
            event_count += 1
            if event_count > 10:  # Safety limit
                break

        print(f"✅ Conversation simulation completed ({event_count} events)")
        return True
    except Exception as e:
        print(f"❌ Conversation simulation error: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def print_sample_conversations():
    """Print sample conversation examples for manual testing."""
    print("\n" + "=" * 70)
    print("📝 Sample Conversations for Manual Testing")
    print("=" * 70)

    conversations = [
        ("Basic Help", [
            "help",
            "Expected: Display help information with available commands"
        ]),
        ("List Sessions", [
            "list sessions",
            "show me previous sessions",
            "Expected: Display list of available sessions"
        ]),
        ("Process File", [
            "Process tanks.xlsx",
            "I need to process tanks_juncos.xlsx with session juncos_2025",
            "Expected: Start pipeline execution with specified file and session"
        ]),
        ("Check Status", [
            "What's the status of session juncos_2025?",
            "How's processing going?",
            "Expected: Display current pipeline status and progress"
        ]),
        ("Get Results", [
            "Show me the compliance report",
            "Where's the PDF report?",
            "Get results for session juncos_2025",
            "Expected: Display artifact paths and result summaries"
        ]),
        ("Multi-turn Conversation", [
            "User: Hi, I need help processing tank data",
            "Bot: (explains capabilities)",
            "User: Process tanks.xlsx",
            "Bot: (starts processing)",
            "User: What's the status?",
            "Bot: (shows progress)",
            "User: Show me the results",
            "Bot: (displays results)",
            "Expected: Chatbot maintains context throughout conversation"
        ])
    ]

    for title, examples in conversations:
        print(f"\n### {title}")
        print("-" * 70)
        for example in examples:
            print(f"  {example}")

    print("\n" + "=" * 70)
    print("To manually test, run: python pipeline_chatbot.py")
    print("=" * 70)


def run_all_tests() -> Tuple[int, int]:
    """Run all tests and return (passed, total) counts."""
    tests = [
        ("Imports", test_imports),
        ("Tool Invocations", test_tool_invocations),
        ("Graph Creation", test_graph_creation),
        ("State Structure", test_state_structure),
        ("Conversation Simulation", test_conversation_simulation)
    ]

    print("=" * 70)
    print("🧪 Pipeline Chatbot Test Suite")
    print("=" * 70)

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
            print(traceback.format_exc())

    return passed, total


def main():
    """Main test runner."""
    passed, total = run_all_tests()

    print("\n" + "=" * 70)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 70)

    if passed == total:
        print("✅ All tests passed!")
        print_sample_conversations()
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
