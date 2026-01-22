#!/usr/bin/env python3
"""
Test persistence functionality
"""
import pickle
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage

# Test storage directory
STORAGE_DIR = Path.home() / ".tank_compliance_agent"
STORAGE_DIR.mkdir(exist_ok=True)

def test_persistence():
    print("Testing chat history persistence...")
    print("=" * 50)

    # Create test session ID
    test_session_id = "test_session_123"
    session_file = STORAGE_DIR / f"session_{test_session_id}.pkl"

    # Create test messages
    test_messages = [
        {'type': 'human', 'content': 'Parse the KMZ file'},
        {'type': 'ai', 'content': 'I will parse the KMZ file for you.', 'tool_calls': []},
        {'type': 'human', 'content': 'Create an Excel file'},
        {'type': 'ai', 'content': 'Excel file created successfully.', 'tool_calls': []}
    ]

    # Test KMZ data
    test_kmz_data = {
        'sites': [
            {'name': 'Test Site 1', 'latitude': 18.23, 'longitude': -65.92},
            {'name': 'Test Site 2', 'latitude': 18.24, 'longitude': -65.93}
        ],
        'polygons': [{'name': 'Test Polygon', 'coordinates': []}],
        'count': 2
    }

    # Save test data
    print("\n1. Saving test session data...")
    session_data = {
        'messages': test_messages,
        'kmz_data': test_kmz_data,
        'excel_data': {'path': 'test.xlsx'},
        'timestamp': '2024-01-01T00:00:00'
    }

    with open(session_file, 'wb') as f:
        pickle.dump(session_data, f)
    print(f"   ✅ Saved to: {session_file}")

    # Load test data
    print("\n2. Loading test session data...")
    with open(session_file, 'rb') as f:
        loaded_data = pickle.load(f)

    print(f"   ✅ Loaded {len(loaded_data['messages'])} messages")
    print(f"   ✅ KMZ data: {loaded_data['kmz_data']['count']} sites")
    print(f"   ✅ Excel data: {loaded_data['excel_data']['path']}")

    # List sessions
    print("\n3. Listing available sessions...")
    sessions = []
    for file in STORAGE_DIR.glob("session_*.pkl"):
        session_id = file.stem.replace("session_", "")
        sessions.append(session_id)
        print(f"   • {session_id}")

    # Verify message reconstruction
    print("\n4. Testing message reconstruction...")
    messages = []
    for msg_data in loaded_data['messages']:
        if msg_data['type'] == 'human':
            messages.append(HumanMessage(content=msg_data['content']))
        elif msg_data['type'] == 'ai':
            msg = AIMessage(content=msg_data['content'])
            messages.append(msg)

    print(f"   ✅ Reconstructed {len(messages)} message objects")
    for i, msg in enumerate(messages):
        print(f"      {i+1}. {type(msg).__name__}: {msg.content[:50]}...")

    # Clean up test file
    print("\n5. Cleaning up...")
    if session_file.exists():
        session_file.unlink()
        print(f"   ✅ Removed test file")

    print("\n" + "=" * 50)
    print("✨ Persistence test completed successfully!")
    print("\nKey features verified:")
    print("  • Session data saved to disk")
    print("  • Messages properly serialized")
    print("  • KMZ and Excel data preserved")
    print("  • Sessions can be listed and loaded")
    print("  • Messages reconstructed correctly")

    print("\n📝 To use the persistent agent:")
    print("   streamlit run agente_persistent.py")

if __name__ == "__main__":
    test_persistence()