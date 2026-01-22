# Tank Processing Pipeline - LangGraph Agent Configuration Guide

**Based on Official LangGraph Documentation**

This guide ensures your agents are properly configured according to LangGraph best practices.

---

## Table of Contents

1. [Agent Architecture Overview](#agent-architecture-overview)
2. [State Management](#state-management)
3. [Tool Configuration](#tool-configuration)
4. [Graph Construction](#graph-construction)
5. [Memory & Persistence](#memory--persistence)
6. [Human-in-the-Loop](#human-in-the-loop)
7. [Streaming & Progress](#streaming--progress)
8. [Error Handling](#error-handling)
9. [Testing & Validation](#testing--validation)
10. [Deployment Options](#deployment-options)

---

## Agent Architecture Overview

### Current Implementation

Our pipeline uses **two types of agents**:

1. **Pipeline Agent** (`pipeline_agent.py`) - Main orchestration
2. **Simple Chatbot** (`simple_chatbot.py`) - Conversational interface
3. **Specialized Parsers** (`kmz_parser_agent.py`, `enhanced_excel_parser.py`) - File processing

### LangGraph Architecture Pattern

According to [LangGraph Agent Development](https://langchain-ai.github.io/langgraph/agents/overview/), our agents follow the recommended structure:

```
┌─────────────────────────────────────────────────────────┐
│                    AGENT STRUCTURE                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                 │
│  │   LLM Core   │ ──> │    Tools     │                 │
│  └──────────────┘     └──────────────┘                 │
│         │                     │                         │
│         ▼                     ▼                         │
│  ┌──────────────────────────────────┐                  │
│  │      State Management            │                  │
│  │  (Memory + Checkpointing)        │                  │
│  └──────────────────────────────────┘                  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## State Management

### ✅ CORRECT: TypedDict State (Following LangGraph Best Practices)

Our `PipelineState` follows the [recommended StateGraph pattern](https://langchain-ai.github.io/langgraph/concepts/low_level/):

```python
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages

class PipelineState(TypedDict):
    """State for complete pipeline execution"""
    # Messages for LLM communication
    messages: Annotated[List[BaseMessage], add_messages]

    # Input configuration
    input_file: str
    input_type: str  # "kmz", "excel", "csv"
    output_dir: str
    session_id: str
    config: Dict[str, Any]

    # Artifacts (file paths)
    kmz_parsed: Optional[Dict[str, Any]]
    excel_file: Optional[str]
    tank_config_json: Optional[str]
    validation_passed: bool
    hud_results_json: Optional[str]
    pdf_report: Optional[str]
    updated_excel: Optional[str]
    distances_json: Optional[str]
    compliance_excel: Optional[str]
    output_kmz: Optional[str]

    # Processing state
    current_step: str
    completed_steps: List[str]
    errors: List[str]
    warnings: List[str]

    # Metrics
    tank_count: int
    processing_stats: Dict[str, Any]
    start_time: Optional[float]
    end_time: Optional[float]
```

**Key Features:**
- ✅ Uses `TypedDict` for type safety
- ✅ Uses `add_messages` reducer for message accumulation
- ✅ Separates input, output, and processing state
- ✅ Tracks artifacts by file paths
- ✅ Includes error/warning lists

### Chatbot State

The `SimpleChatbotState` follows [chatbot memory patterns](https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/):

```python
class SimpleChatbotState(TypedDict):
    """Simple state for conversational interface"""
    messages: Annotated[List[BaseMessage], add_messages]
    current_file: Optional[str]
    output_dir: str
```

**Why this works:**
- ✅ Minimal state for conversational flow
- ✅ Uses `add_messages` for conversation history
- ✅ Tracks current file being processed

---

## Tool Configuration

### Tool Definition Pattern

Following [LangGraph tool integration](https://langchain-ai.github.io/langgraph/agents/tools/), our tools use the `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def parse_kmz_tool(kmz_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Parse KMZ/KML file to extract tank locations and boundary polygon.

    Args:
        kmz_path: Path to KMZ or KML file
        output_dir: Directory for output files

    Returns:
        Dictionary with parsed data and Excel template path
    """
    try:
        # Implementation using subprocess
        cmd = ["python", "kmz_parser_agent.py", kmz_path, "-o", output_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"KMZ parsing failed: {result.stderr}"
            }

        # Find generated Excel template
        excel_files = list(Path(output_dir).glob("tank_locations_*.xlsx"))

        return {
            "success": True,
            "excel": str(excel_files[0]) if excel_files else None,
            "message": "KMZ parsed successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"KMZ parsing exception: {str(e)}"
        }
```

**Best Practices Applied:**
- ✅ Clear docstring with Args and Returns
- ✅ Type hints for all parameters
- ✅ Consistent return structure (success/error)
- ✅ Exception handling
- ✅ Subprocess timeout for safety

### Tool Binding

Following [model configuration guide](https://langchain-ai.github.io/langgraph/agents/models/):

```python
from langchain.chat_models import init_chat_model

# Initialize LLM
llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

# Bind tools
tools = [
    process_file_tool,
    fill_tank_data_tool,
    create_template_tool,
    help_tool
]

llm_with_tools = llm.bind_tools(tools)
```

**Why `init_chat_model`:**
- ✅ Unified interface for all providers
- ✅ Automatic tool calling support detection
- ✅ Consistent error handling
- ✅ Easy provider switching

---

## Graph Construction

### StateGraph Pattern

Following [LangGraph Graph API](https://langchain-ai.github.io/langgraph/how-tos/graph-api/):

```python
from langgraph.graph import StateGraph, START, END

def create_pipeline_graph() -> StateGraph:
    """Build the complete pipeline StateGraph."""
    workflow = StateGraph(PipelineState)

    # Add nodes
    workflow.add_node("detect_input", detect_input_node)
    workflow.add_node("parse_kmz", parse_kmz_node)
    workflow.add_node("excel_to_json", excel_to_json_node)
    workflow.add_node("validate_json", validate_json_node)
    workflow.add_node("process_hud", process_hud_node)
    workflow.add_node("generate_pdf", generate_pdf_node)
    workflow.add_node("update_excel", update_excel_node)
    workflow.add_node("calculate_distances", calculate_distances_node)
    workflow.add_node("check_compliance", check_compliance_node)
    workflow.add_node("create_output_kmz", create_output_kmz_node)
    workflow.add_node("summarize", summarize_results_node)

    # Add edges
    workflow.add_edge(START, "detect_input")

    # Conditional routing
    workflow.add_conditional_edges(
        "detect_input",
        route_after_detection,
        {
            "parse_kmz": "parse_kmz",
            "excel_to_json": "excel_to_json"
        }
    )

    # Sequential flow
    workflow.add_edge("parse_kmz", "excel_to_json")
    workflow.add_edge("excel_to_json", "validate_json")
    workflow.add_edge("validate_json", "process_hud")
    workflow.add_edge("process_hud", "generate_pdf")
    workflow.add_edge("generate_pdf", "update_excel")
    workflow.add_edge("update_excel", "calculate_distances")
    workflow.add_edge("calculate_distances", "check_compliance")
    workflow.add_edge("check_compliance", "create_output_kmz")
    workflow.add_edge("create_output_kmz", "summarize")
    workflow.add_edge("summarize", END)

    return workflow
```

**Best Practices Applied:**
- ✅ Clear node names describing actions
- ✅ Conditional routing for input type detection
- ✅ Sequential edges for linear workflow
- ✅ START and END markers
- ✅ Proper error handling in route functions

### Chatbot Graph

Following [building a basic chatbot](https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/):

```python
from langgraph.prebuilt import ToolNode, tools_condition

def create_simple_chatbot() -> StateGraph:
    """Create simple chatbot graph."""
    llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

    tools = [
        process_file_tool,
        fill_tank_data_tool,
        create_template_tool,
        help_tool
    ]

    llm_with_tools = llm.bind_tools(tools)

    def chatbot_node(state: SimpleChatbotState) -> SimpleChatbotState:
        """Main chatbot logic."""
        system_message = SystemMessage(content="You are a helpful assistant...")
        messages = [system_message] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Build graph
    graph_builder = StateGraph(SimpleChatbotState)
    graph_builder.add_node("chatbot", chatbot_node)

    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")

    return graph_builder
```

**Key Components:**
- ✅ Uses prebuilt `ToolNode` for tool execution
- ✅ Uses prebuilt `tools_condition` for routing
- ✅ System message for agent behavior
- ✅ Simple loop: chatbot → tools → chatbot

---

## Memory & Persistence

### Checkpointing

Following [persistence and checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/):

```python
from langgraph.checkpoint.memory import MemorySaver

# Development: In-memory checkpointer
checkpointer = MemorySaver()

# Compile graph with checkpointer
graph = workflow.compile(checkpointer=checkpointer)

# Run with thread-based memory
config = {"configurable": {"thread_id": "user_session_123"}}
for event in graph.stream(initial_state, config):
    # Process events
    pass
```

**For Production:**

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Production: SQLite checkpointer
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = workflow.compile(checkpointer=checkpointer)
```

**Benefits:**
- ✅ Conversation history preservation
- ✅ State recovery after errors
- ✅ Time travel capability
- ✅ Human-in-the-loop support

### Memory Management

Following [memory in LangGraph](https://langchain-ai.github.io/langgraph/concepts/memory/):

**Short-term Memory:**
```python
# Handled automatically by add_messages reducer
messages: Annotated[List[BaseMessage], add_messages]
```

**Long-term Memory (if needed):**
```python
from langgraph.store.memory import InMemoryStore

# Create memory store
store = InMemoryStore()

# Use in graph
graph = workflow.compile(
    checkpointer=checkpointer,
    store=store
)
```

---

## Human-in-the-Loop

### Interrupt Pattern

Following [human-in-the-loop guide](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/):

```python
from langgraph.types import interrupt

def human_fill_excel_node(state: PipelineState) -> PipelineState:
    """Prompt human to fill Excel template."""
    state["current_step"] = "human_fill_excel"

    excel_path = state["excel_file"]

    # Request human input
    approval = interrupt({
        "message": "Excel template ready for filling. Proceed when complete.",
        "excel_path": excel_path
    })

    # Continue after approval
    if approval.get("approved"):
        state["completed_steps"].append("human_fill_excel")
    else:
        state["errors"].append("Human approval denied")

    return state
```

**Usage:**
```python
# Run until interrupt
for event in graph.stream(state, config):
    print(event)

# Resume after human input
graph.update_state(
    config,
    {"excel_filled": True},
    as_node="human_fill_excel"
)

# Continue execution
for event in graph.stream(None, config):
    print(event)
```

---

## Streaming & Progress

### Stream Modes

Following [streaming in LangGraph](https://langchain-ai.github.io/langgraph/concepts/streaming/):

```python
# Stream node updates
for event in graph.stream(state, config, stream_mode="updates"):
    print(f"Node: {event}")

# Stream full state values
for event in graph.stream(state, config, stream_mode="values"):
    print(f"State: {event}")

# Stream LLM tokens
for event in graph.stream(state, config, stream_mode="messages"):
    if hasattr(event, 'content'):
        print(event.content, end="", flush=True)
```

**Current Implementation:**

```python
def run_pipeline_agent(
    input_file: str,
    stream_progress: bool = False
):
    """Run pipeline with optional streaming."""
    for event in agent.stream(initial_state, config):
        if stream_progress:
            # Show progress updates
            if "messages" in event:
                last_msg = event["messages"][-1]
                print(f"✓ {last_msg.content}")
```

---

## Error Handling

### Retry Policies

Following [error handling best practices](https://langchain-ai.github.io/langgraph/troubleshooting/errors/index/):

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def process_hud_tool(config_json: str, output_dir: str) -> Dict[str, Any]:
    """Process HUD with retry logic."""
    try:
        # HUD processing
        result = subprocess.run(
            ["python", "fast_hud_processor.py", config_json, "-o", output_dir],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            raise Exception(f"HUD processing failed: {result.stderr}")

        return {"success": True, "output": output_dir}

    except Exception as e:
        # Log error
        print(f"Error in HUD processing: {e}")
        raise
```

### Recursion Limits

Following [recursion limit handling](https://langchain-ai.github.io/langgraph/troubleshooting/errors/GRAPH_RECURSION_LIMIT/):

```python
# Compile with custom recursion limit
graph = workflow.compile(
    checkpointer=checkpointer,
    recursion_limit=100  # Default is 25
)
```

---

## Testing & Validation

### Unit Testing Tools

```python
def test_parse_kmz_tool():
    """Test KMZ parsing tool."""
    result = parse_kmz_tool.invoke({
        "kmz_path": "test_tanks.kmz",
        "output_dir": "test_output"
    })

    assert result["success"] == True
    assert "excel" in result
    assert Path(result["excel"]).exists()
```

### Integration Testing Graph

```python
def test_pipeline_graph():
    """Test complete pipeline graph."""
    graph = create_pipeline_graph()
    checkpointer = MemorySaver()
    agent = graph.compile(checkpointer=checkpointer)

    initial_state = {
        "input_file": "test.xlsx",
        "output_dir": "test_output",
        "session_id": "test_123",
        # ... other state fields
    }

    config = {"configurable": {"thread_id": "test"}}

    result = None
    for event in agent.stream(initial_state, config):
        result = event

    assert result["status"] == "completed"
    assert len(result["errors"]) == 0
```

---

## Deployment Options

### Local Development

Following [local server quickstart](https://langchain-ai.github.io/langgraph/tutorials/langgraph-platform/local-server/):

```bash
# Install LangGraph CLI
pip install langgraph-cli

# Start local server
langgraph dev

# Test with LangGraph Studio
open http://localhost:8123
```

### Production Deployment

Following [deployment options](https://langchain-ai.github.io/langgraph/concepts/deployment_options/):

**Option 1: Cloud SaaS**
- Managed by LangChain
- Auto-scaling
- Built-in monitoring

**Option 2: Self-Hosted Container**
```bash
# Build Docker image
docker build -t tank-pipeline .

# Run container
docker run -p 8000:8000 tank-pipeline
```

**Option 3: Kubernetes**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tank-pipeline
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: pipeline
        image: tank-pipeline:latest
        ports:
        - containerPort: 8000
```

---

## Configuration Summary

### ✅ What We're Doing Right

1. **State Management**
   - Using TypedDict for type safety
   - Using add_messages reducer
   - Proper state separation

2. **Tool Configuration**
   - Using @tool decorator
   - Consistent return structures
   - Error handling in tools

3. **Graph Construction**
   - Clear node definitions
   - Conditional routing
   - START/END markers

4. **Memory**
   - Using MemorySaver for checkpointing
   - Thread-based conversation tracking

5. **Streaming**
   - Optional progress streaming
   - Multiple stream modes supported

### 📝 Recommendations

1. **Add Retry Logic**
   - Implement tenacity for HUD processing
   - Add exponential backoff

2. **Enhanced Error Handling**
   - Add custom error types
   - Better error recovery

3. **Production Checkpointing**
   - Switch to SQLite for persistence
   - Add checkpoint cleanup

4. **Monitoring**
   - Add LangSmith tracing
   - Log execution metrics

5. **Testing**
   - Add comprehensive unit tests
   - Add integration test suite

---

## Quick Reference

### Running the Pipeline

```python
from pipeline_agent import run_pipeline_agent

result = run_pipeline_agent(
    input_file="tanks.xlsx",
    output_dir="outputs",
    session_id="my_session",
    stream_progress=True
)
```

### Running the Chatbot

```python
from simple_chatbot import run_chatbot

# Interactive mode
run_chatbot()

# Programmatic mode
graph = create_simple_chatbot()
checkpointer = MemorySaver()
agent = graph.compile(checkpointer=checkpointer)

result = agent.invoke({
    "messages": [HumanMessage(content="Process tanks.xlsx")]
})
```

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Agent Development Guide](https://langchain-ai.github.io/langgraph/agents/overview/)
- [State Management](https://langchain-ai.github.io/langgraph/concepts/low_level/)
- [Tool Calling](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
- [Memory & Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [Streaming](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [Deployment](https://langchain-ai.github.io/langgraph/concepts/deployment_options/)

---

**Last Updated:** 2025-01-30
**LangGraph Version:** Latest
**Agent Configuration:** ✅ Validated Against Official Documentation