# Pipeline Chatbot Documentation

**Conversational Interface for Tank Processing Pipeline using LangGraph**

---

## Overview

The Pipeline Chatbot provides a natural language interface to the complete tank processing pipeline. Instead of remembering command-line arguments and file paths, users can simply chat with the bot to process files, check status, and retrieve results.

## Features

✅ **Natural Language Processing** - Talk to the pipeline like you would to a colleague
✅ **Context Awareness** - Chatbot remembers previous interactions within a session
✅ **Full Pipeline Access** - All 8 pipeline steps available through conversation
✅ **Session Management** - Track and resume multiple pipeline executions
✅ **Intelligent Tool Selection** - LLM automatically chooses the right tools based on your request
✅ **Persistent Memory** - Conversations and pipeline state saved via checkpointing
✅ **Same Outputs** - Generates identical artifacts as the direct pipeline agent

---

## Quick Start

### Installation

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

Required packages include:
- `langgraph` - Graph orchestration
- `langchain` - LLM integration
- `langchain-anthropic` or `langchain-openai` - LLM providers
- All existing pipeline dependencies

### Basic Usage

Start the interactive chatbot:

```bash
python pipeline_chatbot.py
```

With custom session ID:

```bash
python pipeline_chatbot.py --session juncos_2025
```

With different LLM model:

```bash
python pipeline_chatbot.py --model openai:gpt-4
```

With SQLite checkpointing (persistent across restarts):

```bash
python pipeline_chatbot.py --checkpointer sqlite
```

---

## Example Conversations

### 1. Basic Help

```
You: help
Assistant: [Displays comprehensive help information about available commands and pipeline capabilities]
```

### 2. Process a File

```
You: Hi, I need to process tanks_juncos.xlsx
Assistant: I'll help you process that file. Let me start the pipeline for tanks_juncos.xlsx.
[Calls process_pipeline_tool]
Assistant: Pipeline completed successfully! Processed 24 tanks.
The compliance report is available at: outputs/chat_20250130_143025/final_compliance.xlsx
```

### 3. Check Status

```
You: What's the current status of session juncos_2025?
Assistant: [Calls check_status_tool]
Assistant: Session juncos_2025 is currently at step: process_hud
Completed steps: detect_input, excel_to_json, validate_json
Processing 24 tanks, no errors so far.
```

### 4. Get Results

```
You: Show me the compliance report
Assistant: [Calls get_results_tool]
Assistant: Pipeline results for juncos_2025:
- Compliance Report: outputs/juncos_2025/final_compliance.xlsx
- PDF Report: outputs/juncos_2025/HUD_ASD_Results.pdf
- Updated Excel: outputs/juncos_2025/with_hud.xlsx
```

### 5. List Sessions

```
You: Show me all my previous sessions
Assistant: [Calls list_sessions_tool]
Assistant: Found 3 session(s):
- juncos_2025: 24 tanks, status: completed
- chat_20250130_140512: 18 tanks, status: process_hud
- test_session: 0 tanks, status: detect_input
```

### 6. Multi-turn Conversation

```
You: Hi, I have a KMZ file with tank locations
Assistant: Great! I can help you process that KMZ file. The pipeline will extract tank locations,
create an Excel template, and then process all the tanks through the full compliance workflow.
What's the path to your KMZ file?

You: It's at tanks_juncos.kmz
Assistant: [Calls process_pipeline_tool with tanks_juncos.kmz]
Assistant: Processing started! The KMZ file is being parsed to extract locations...

You: How's it going?
Assistant: [Calls check_status_tool]
Assistant: Currently processing HUD calculations (step 4 of 8).
Extracted 24 tanks from the KMZ file. This step takes about 6-8 minutes for 24 tanks.

You: Let me know when it's done
Assistant: I'll keep you updated! [continues processing in background]
```

---

## Architecture

### State Management

The chatbot uses `ChatbotState` which extends pipeline state with conversation context:

```python
class ChatbotState(TypedDict):
    # Conversation
    messages: Annotated[List[BaseMessage], add_messages]

    # Pipeline context
    session_id: Optional[str]
    pipeline_active: bool
    user_intent: str

    # Pipeline state
    input_file: Optional[str]
    output_dir: str
    current_step: Optional[str]
    completed_steps: List[str]
    errors: List[str]
    warnings: List[str]
    tank_count: int
    artifacts: Dict[str, Any]
    processing_stats: Dict[str, Any]
```

### Available Tools

The chatbot has access to 5 conversational tools:

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `process_pipeline_tool` | Start full pipeline execution | User wants to process a file |
| `check_status_tool` | Get current pipeline status | User asks about progress |
| `get_results_tool` | Retrieve output artifacts | User wants compliance reports |
| `list_sessions_tool` | List all pipeline sessions | User asks about previous runs |
| `help_tool` | Display help information | User needs guidance |

### Graph Structure

```
┌─────────────────────────────────────────────────────────────┐
│                       Pipeline Chatbot                       │
└─────────────────────────────────────────────────────────────┘

                    START
                      │
                      ▼
            ┌─────────────────┐
            │  chatbot_node   │
            │  (LLM + tools)  │
            └─────────┬───────┘
                      │
          ┌───────────┴──────────┐
          │                      │
    ┌─────▼──────┐          ┌───▼────┐
    │ tools_node │          │  END   │
    │  (execute) │          └────────┘
    └─────┬──────┘
          │
          └──────────► chatbot_node (loop)

Key Features:
• LLM decides which tools to invoke based on user input
• Tools execute pipeline operations or retrieve information
• Results flow back to chatbot for natural language response
• Checkpointer saves state after each interaction
```

### Checkpointing

Two checkpointer options:

**Memory (Development):**
```bash
python pipeline_chatbot.py --checkpointer memory
```
- Fast, in-memory storage
- Lost on process restart
- Good for testing

**SQLite (Production):**
```bash
python pipeline_chatbot.py --checkpointer sqlite
```
- Persistent storage in `pipeline_chatbot.db`
- Survives restarts
- Supports multiple concurrent sessions
- Recommended for production use

---

## Tool Details

### `process_pipeline_tool`

**Purpose:** Execute the full 8-step tank processing pipeline

**Parameters:**
- `file_path` (required): Path to input file (KMZ, Excel, or CSV)
- `session_id` (optional): Session identifier for tracking
- `output_dir` (optional): Output directory (default: "outputs")

**Returns:**
```python
{
    "success": True,
    "session_id": "juncos_2025",
    "message": "Pipeline completed successfully",
    "tank_count": 24,
    "completed_steps": [...],
    "artifacts": {
        "compliance_excel": "outputs/.../final_compliance.xlsx",
        "pdf_report": "outputs/.../HUD_ASD_Results.pdf",
        "updated_excel": "outputs/.../with_hud.xlsx"
    },
    "errors": [],
    "warnings": []
}
```

**Example prompts:**
- "Process tanks.xlsx"
- "Run pipeline on juncos.kmz with session id juncos_2025"
- "I need to analyze this Excel file: /path/to/tanks.xlsx"

---

### `check_status_tool`

**Purpose:** Get current status of a pipeline execution

**Parameters:**
- `session_id` (required): Session to check

**Returns:**
```python
{
    "success": True,
    "session_id": "juncos_2025",
    "current_step": "process_hud",
    "completed_steps": ["detect_input", "excel_to_json", "validate_json"],
    "tank_count": 24,
    "errors": [],
    "warnings": [],
    "message": "Session juncos_2025 is at step: process_hud"
}
```

**Example prompts:**
- "What's the status?"
- "How's processing going for session juncos_2025?"
- "Check status of my pipeline"

---

### `get_results_tool`

**Purpose:** Retrieve pipeline outputs and artifacts

**Parameters:**
- `session_id` (required): Session to query
- `result_type` (optional): "summary", "compliance", "pdf", "excel", "all"

**Returns:**
```python
{
    "success": True,
    "session_id": "juncos_2025",
    "result_type": "summary",
    "artifacts": {
        "compliance_excel": "path/to/final_compliance.xlsx",
        "pdf_report": "path/to/HUD_ASD_Results.pdf",
        "updated_excel": "path/to/with_hud.xlsx",
        "tank_config_json": "path/to/tank_config.json",
        "hud_results_json": "path/to/fast_results.json"
    },
    "message": "Pipeline results for juncos_2025:\n- Compliance Report: ...\n- PDF Report: ...\n- Updated Excel: ..."
}
```

**Example prompts:**
- "Show me the results"
- "Where's the compliance report?"
- "Get the PDF for session juncos_2025"

---

### `list_sessions_tool`

**Purpose:** List all available pipeline sessions

**Parameters:** None

**Returns:**
```python
{
    "success": True,
    "sessions": [
        {
            "session_id": "juncos_2025",
            "created": 1706553600.0,
            "status": "completed",
            "tank_count": 24
        },
        ...
    ],
    "count": 3,
    "message": "Found 3 session(s):\n- juncos_2025: 24 tanks, status: completed\n..."
}
```

**Example prompts:**
- "List all sessions"
- "Show me previous pipeline runs"
- "What sessions are available?"

---

### `help_tool`

**Purpose:** Display comprehensive help information

**Parameters:** None

**Returns:** Help text covering:
- Available commands
- Pipeline capabilities
- File format support
- Example conversations
- Session ID usage

**Example prompts:**
- "help"
- "How do I use this?"
- "What can you do?"

---

## Integration with Existing Pipeline

The chatbot wraps `pipeline_agent.py` and maintains full compatibility:

### Direct Pipeline Agent
```bash
python pipeline_agent.py tanks.xlsx --session juncos_2025
```

### Via Chatbot
```bash
python pipeline_chatbot.py
You: Process tanks.xlsx with session juncos_2025
```

**Both produce identical outputs:**
- Same 8-step pipeline execution
- Same artifact files (Excel, PDF, JSON)
- Same compliance assessments
- Same error handling and recovery

---

## Session Management

### Session ID Format

**Auto-generated:**
```
chat_20250130_143025
```

**User-specified:**
```
juncos_2025
site_alpha_v2
production_run_01
```

### Session Persistence

Sessions are tracked via:
1. **Conversation state** - Checkpointer stores message history
2. **Pipeline state** - Status file in `outputs/{session_id}/status.json`
3. **Artifacts** - Output files in `outputs/{session_id}/`

### Resume a Session

```bash
# Start chatbot with existing session ID
python pipeline_chatbot.py --session juncos_2025

You: What's the status?
Assistant: [Loads previous state and continues from where it left off]
```

---

## Advanced Usage

### Custom LLM Model

```bash
# Use OpenAI GPT-4
python pipeline_chatbot.py --model openai:gpt-4

# Use Anthropic Claude Sonnet
python pipeline_chatbot.py --model anthropic:claude-3-5-sonnet-latest

# Use Azure OpenAI
python pipeline_chatbot.py --model azure_openai:gpt-4
```

### Programmatic Usage

```python
from pipeline_chatbot import create_chatbot_graph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

# Create graph
graph_builder = create_chatbot_graph(llm_model="anthropic:claude-3-5-sonnet-latest")
checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)

# Configuration
config = {"configurable": {"thread_id": "my_session"}}

# Send message
initial_state = {
    "messages": [HumanMessage(content="Process tanks.xlsx")],
    "session_id": "my_session",
    "pipeline_active": False,
    "user_intent": "process",
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

# Stream responses
for event in graph.stream(initial_state, config, stream_mode="values"):
    if "messages" in event:
        print(event["messages"][-1].content)
```

### API Integration (Future)

The chatbot can be integrated into FastAPI:

```python
# api/chatbot_routes.py (example)
from fastapi import APIRouter
from pipeline_chatbot import create_chatbot_graph

router = APIRouter()

@router.post("/chatbot/message")
async def send_message(session_id: str, message: str):
    # Stream chatbot response
    ...

@router.websocket("/ws/chatbot/{session_id}")
async def chatbot_websocket(websocket: WebSocket, session_id: str):
    # Real-time chat via WebSocket
    ...
```

---

## Testing

Run the test suite:

```bash
python test_pipeline_chatbot.py
```

**Tests included:**
1. ✅ Import validation
2. ✅ Tool invocation tests
3. ✅ Graph creation and compilation
4. ✅ State structure validation
5. ✅ Conversation simulation

**Expected output:**
```
======================================================================
🧪 Pipeline Chatbot Test Suite
======================================================================
Testing imports...
✅ All imports successful

Testing tool invocations...
✅ help_tool works
✅ list_sessions_tool works (found 3 sessions)

Testing graph creation...
✅ Graph created and compiled successfully

Testing state structure...
✅ State structure is valid

Testing conversation simulation...
  Running test conversation with 'help' command...
  (This will invoke the LLM - may take a few seconds)
✅ Conversation simulation completed (4 events)

======================================================================
Test Results: 5/5 passed
======================================================================
✅ All tests passed!
```

---

## Troubleshooting

### Common Issues

**Issue:** "Import Error: No module named 'langchain'"
**Solution:**
```bash
pip install -U langchain langchain-anthropic langgraph
```

**Issue:** "API key not found"
**Solution:**
```bash
export ANTHROPIC_API_KEY="your-key-here"
# or
export OPENAI_API_KEY="your-key-here"
```

**Issue:** "Session not found"
**Solution:** Check that the session ID exists:
```bash
ls -la outputs/
# Look for directory matching your session_id
```

**Issue:** "Tool execution failed"
**Solution:** Verify file paths are absolute or relative to current directory:
```
You: Process /absolute/path/to/tanks.xlsx
# or
You: Process ./relative/path/tanks.xlsx
```

### Debug Mode

For detailed execution traces, use LangSmith:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY="your-langsmith-key"
export LANGCHAIN_PROJECT="pipeline-chatbot"

python pipeline_chatbot.py
```

View traces at: https://smith.langchain.com/

---

## Comparison: Chatbot vs Direct Agent

| Feature | Direct Agent | Chatbot |
|---------|-------------|---------|
| **Interface** | CLI arguments | Natural language |
| **Context** | Single execution | Multi-turn conversation |
| **Learning curve** | Medium (need to know args) | Low (conversational) |
| **Flexibility** | Fixed commands | Flexible phrasing |
| **Session tracking** | Manual session IDs | Automatic tracking |
| **Error explanation** | Technical messages | Natural language help |
| **Multi-tasking** | One task at a time | Check status during run |
| **Pipeline output** | Identical | Identical |

---

## Benefits

### 1. Natural Language Interface
No need to remember complex CLI arguments:
```bash
# Before (Direct Agent)
python pipeline_agent.py tanks.xlsx --session juncos --output-dir ./out --config config.json

# After (Chatbot)
You: Process tanks.xlsx with session juncos
```

### 2. Context Awareness
Chatbot remembers previous interactions:
```
You: Process tanks.xlsx
Assistant: [starts processing]
You: What's the status?
Assistant: [knows which session you mean]
You: Show me the results
Assistant: [retrieves results for same session]
```

### 3. Intelligent Tool Selection
LLM automatically chooses the right tools:
```
You: I need compliance reports → get_results_tool
You: How's processing? → check_status_tool
You: Process this file → process_pipeline_tool
```

### 4. Error Guidance
LLM can explain errors in plain language:
```
You: Why did validation fail?
Assistant: The validation failed because tank T-05 is missing the height dimension.
You can either add this dimension to the Excel file or the pipeline will calculate
volume from the capacity value instead.
```

### 5. Same Reliable Output
All pipeline capabilities remain unchanged:
- 8-step processing workflow
- HUD ASD calculations
- Compliance assessment
- PDF and Excel reports

---

## Future Enhancements

Potential additions to the chatbot:

1. **Streaming Progress** - Real-time updates during long operations
2. **File Upload** - Accept file uploads directly through chat
3. **Batch Processing** - "Process all files in directory X"
4. **Custom Workflows** - "Skip PDF generation" or "Run only HUD"
5. **Notifications** - "Email me when processing completes"
6. **Multi-language** - Support for Spanish language interactions
7. **Voice Interface** - Speech-to-text for hands-free operation
8. **Web UI** - Browser-based chat interface

---

## Contributing

To extend the chatbot with new tools:

```python
@tool
def custom_tool(param: str) -> Dict[str, Any]:
    """
    Custom tool description for LLM.

    Args:
        param: Parameter description

    Returns:
        Result dictionary
    """
    # Implementation
    return {"success": True, "result": "..."}

# Add to tools list in create_chatbot_graph()
tools = [
    process_pipeline_tool,
    check_status_tool,
    get_results_tool,
    list_sessions_tool,
    help_tool,
    custom_tool  # Add here
]
```

---

## Support

For issues or questions:
- Review test output: `python test_pipeline_chatbot.py`
- Check LangSmith traces for detailed execution logs
- Verify environment variables are set correctly
- Ensure all dependencies are installed

---

**Version:** 1.0.0
**Created:** 2025-01-30
**Compatible with:** pipeline_agent.py v1.0+