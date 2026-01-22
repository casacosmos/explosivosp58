# LangGraph Pipeline Agent

## Overview

The **Pipeline Agent** (`pipeline_agent.py`) is a unified LangGraph-based orchestrator that manages all 8 steps of the tank processing pipeline through a stateful workflow with tools, persistence, and streaming capabilities.

## Architecture

### Agent-Based Design
- **StateGraph** workflow with 11 nodes
- **10 specialized tools** wrapping existing pipeline scripts
- **Checkpointing** for persistence and recovery
- **Streaming** for real-time progress updates
- **Conditional routing** based on input type and step results

### State Management
```python
PipelineState:
  - Input: file path, type, output directory, session ID
  - Artifacts: paths to all intermediate files
  - Progress: current step, completed steps, errors, warnings
  - Metrics: tank count, processing statistics, timing
```

## Features

### ✅ Advantages Over `main.py`

| Feature | `main.py` (Old) | `pipeline_agent.py` (New) |
|---------|-----------------|---------------------------|
| **Persistence** | No | Yes (checkpointing) |
| **Resume on Failure** | No | Yes (from last checkpoint) |
| **Streaming Progress** | No | Yes (real-time updates) |
| **Time Travel Debugging** | No | Yes (LangGraph Studio) |
| **Human-in-the-Loop** | Limited | Yes (approval gates) |
| **Observability** | Logs only | LangSmith tracing |
| **Tool Reuse** | No | Yes (tools can be used independently) |
| **Error Recovery** | Stop on error | Continue with warnings |

## Usage

### 1. Basic Execution

```bash
# Excel/CSV input
python pipeline_agent.py tanks.xlsx

# KMZ input
python pipeline_agent.py facility.kmz

# With custom output directory
python pipeline_agent.py tanks.xlsx -o reports/batch_001/

# With session ID for persistence
python pipeline_agent.py tanks.xlsx --session jun

cos_2025_01
```

### 2. Configuration Options

```bash
# Use legacy parser (not recommended)
python pipeline_agent.py tanks.xlsx --legacy-parser

# Disable streaming (quiet mode)
python pipeline_agent.py tanks.xlsx --no-stream

# Show help
python pipeline_agent.py --help
```

### 3. Programmatic Usage

```python
from pipeline_agent import run_pipeline_agent

result = run_pipeline_agent(
    input_file="tanks.xlsx",
    output_dir="outputs",
    session_id="custom_session",
    config={
        "use_improved_parser": True
    },
    stream_progress=True
)

# Access results
print(f"Tanks processed: {result['tank_count']}")
print(f"Compliance report: {result['compliance_excel']}")
print(f"Errors: {result['errors']}")
```

## Pipeline Flow

```
START
  ↓
[Detect Input Type] ─→ KMZ/Excel/CSV
  ↓
[Parse KMZ] (if KMZ) ─→ [Human: Fill Excel] ─→ [Excel to JSON]
  OR
[Excel to JSON] (if Excel/CSV directly)
  ↓
[Validate JSON] ─→ Check structure
  ↓
[Process HUD] ─→ Calculate ASD values (longest step)
  ↓
[Generate PDF] ─→ Create screenshot report
  ↓
[Update Excel] ─→ Merge HUD results
  ↓
[Calculate Distances] (if polygon available)
  ↓
[Check Compliance] ─→ Final compliance report
  ↓
[Summarize] ─→ Generate execution summary
  ↓
END
```

## Tools

### 1. `parse_kmz_tool`
Wraps `kmz_parser_agent.py` to extract tank locations and boundary polygons.

### 2. `excel_to_json_tool`
Wraps `excel_to_json_improved.py` for accurate volume calculations.

### 3. `validate_json_tool`
Wraps `validate_tank_json.py` for structure validation.

### 4. `process_hud_tool`
Wraps `fast_hud_processor.py` for Playwright-based HUD automation.

### 5. `generate_pdf_tool`
Wraps `generate_pdf.py` to create screenshot reports.

### 6. `update_excel_tool`
Wraps `update_excel_with_results.py` to merge HUD data.

### 7. `calculate_distances_tool`
Wraps `calculate_distances.py` for geospatial calculations.

### 8. `check_compliance_tool`
Wraps `compliance_checker.py` for final compliance assessment.

### 9. `calculate_volume_tool`
Direct wrapper around `VolumeCalculator` for volume calculations.

### 10. `human_approval_tool`
Requests human approval at critical decision points.

## Advanced Features

### Checkpointing & Resume

```python
from langgraph.checkpoint.memory import MemorySaver

# State is automatically saved at each step
# If execution fails, resume from last checkpoint:

result = run_pipeline_agent(
    input_file="tanks.xlsx",
    session_id="interrupted_session_123",
    # Will resume from where it left off
)
```

### Streaming Progress

```python
from pipeline_agent import create_pipeline_graph
from langgraph.checkpoint.memory import MemorySaver

workflow = create_pipeline_graph()
agent = workflow.compile(checkpointer=MemorySaver())

# Stream events
for event in agent.stream(initial_state, config):
    for node_name, node_state in event.items():
        print(f"Node: {node_name}")
        print(f"Step: {node_state.get('current_step')}")
        print(f"Messages: {node_state.get('messages')}")
```

### LangSmith Tracing

```bash
# Set environment variables for LangSmith tracing
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_api_key
export LANGCHAIN_PROJECT=tank_pipeline

# Run agent - all executions will be traced
python pipeline_agent.py tanks.xlsx
```

### LangGraph Studio

```bash
# Start LangGraph Studio for visual debugging
langgraph dev

# Open in browser and visualize:
# - Graph structure
# - Execution flow
# - State at each node
# - Time travel debugging
```

## Output Files

The agent generates the following artifacts:

```
outputs/
├── tank_config.json              # Structured tank data
├── fast_results.json             # HUD calculation results
├── HUD_ASD_Results.pdf           # PDF report with screenshots
├── with_hud.xlsx                 # Excel with ASD values
├── distances.json                # Distance calculations
└── final_compliance.xlsx         # Final compliance report
```

## Error Handling

### Graceful Degradation
The agent continues execution even if optional steps fail:

- **HUD Processing Failed**: Continues without ASD values
- **PDF Generation Failed**: Continues without PDF
- **Distance Calculation Failed**: Skips distances
- **Polygon Not Available**: Skips distance step entirely

### Error Reporting
```python
result = run_pipeline_agent(input_file="tanks.xlsx")

# Check for errors
if result['errors']:
    print("Errors encountered:")
    for error in result['errors']:
        print(f"  - {error}")

# Check for warnings
if result['warnings']:
    print("Warnings:")
    for warning in result['warnings']:
        print(f"  - {warning}")
```

## Comparison with Original Pipeline

### Files & Responsibilities

| Component | Original | Agent |
|-----------|----------|-------|
| **Orchestration** | `main.py` (subprocess calls) | `pipeline_agent.py` (LangGraph) |
| **State Management** | Class attributes | PipelineState (TypedDict) |
| **Error Handling** | Try-catch per step | Tool-level + node-level |
| **Progress Tracking** | Console logs | Streaming events |
| **Persistence** | None | Checkpointing |
| **Debugging** | Print statements | LangSmith + LangGraph Studio |

### When to Use Each

**Use `pipeline_agent.py` when:**
- ✅ Need resumability after failures
- ✅ Want real-time progress updates
- ✅ Need observability and tracing
- ✅ Building API with streaming
- ✅ Want human-in-the-loop capabilities

**Use `main.py` when:**
- ✅ Simple one-off executions
- ✅ Don't need persistence
- ✅ Prefer simple subprocess model
- ✅ Minimal dependencies desired

## Requirements

### Python Dependencies
```bash
pip install langgraph langchain langchain-openai langchain-core
pip install pandas openpyxl pydantic typing-extensions
pip install playwright
playwright install chromium
```

### Environment Variables
```bash
export OPENAI_API_KEY=sk-...           # Required for Excel→JSON
export LANGCHAIN_TRACING_V2=true       # Optional: LangSmith tracing
export LANGCHAIN_API_KEY=...           # Optional: LangSmith API key
export LANGCHAIN_PROJECT=tank_pipeline # Optional: LangSmith project
```

## Integration with API

### Add Agent Endpoint

```python
# In api/main.py

from pipeline_agent import run_pipeline_agent

@app.post("/pipeline/agent/run")
async def run_agent_endpoint(
    file: UploadFile = File(...),
    session: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None
):
    """Run pipeline using LangGraph agent."""

    # Save uploaded file
    file_path = save_upload(file, session)

    # Run agent in background
    def run_bg():
        result = run_pipeline_agent(
            input_file=file_path,
            output_dir=f"output/{session}",
            session_id=session,
            stream_progress=False
        )
        # Store result

    background_tasks.add_task(run_bg)

    return {"job_id": session, "status": "started"}
```

### WebSocket Streaming

```python
@app.websocket("/ws/pipeline/agent/{session_id}")
async def agent_stream(websocket: WebSocket, session_id: str):
    """Stream agent execution progress."""
    await websocket.accept()

    workflow = create_pipeline_graph()
    agent = workflow.compile(checkpointer=MemorySaver())

    # Stream events to WebSocket
    for event in agent.stream(initial_state, config):
        await websocket.send_json(event)
```

## Troubleshooting

### Issue: "Tool not found" error
**Solution**: Ensure all pipeline scripts are in the same directory as `pipeline_agent.py`

### Issue: Execution hangs at HUD processing
**Solution**: Check that Chromium is installed with `playwright install chromium`

### Issue: Cannot resume session
**Solution**: Using MemorySaver (in-memory) - for persistent storage, use PostgresSaver or SqliteSaver

### Issue: Import errors for LangGraph
**Solution**: Install with `pip install langgraph langchain-openai`

## Performance Metrics

Typical execution times (24 tanks):

| Step | Time | Notes |
|------|------|-------|
| KMZ Parse | 10-30 sec | One-time |
| Excel→JSON | 30-60 sec | LLM calls |
| Validate | <1 sec | Fast |
| HUD Process | 6-8 min | **Bottleneck** |
| Generate PDF | 5-10 sec | Fast |
| Update Excel | 2-5 sec | Fast |
| Calculate Distances | 5-10 sec | Fast |
| Check Compliance | 2-5 sec | Fast |
| **Total** | **7-10 min** | Dominated by HUD |

## Future Enhancements

1. **Parallel HUD Processing** - Multiple browser instances
2. **Persistent Checkpointer** - PostgreSQL/SQLite for true persistence
3. **Human Approval UI** - Frontend integration for approval gates
4. **Retry Logic** - Automatic retries for failed steps
5. **Subgraphs** - Modular step definitions
6. **Multi-Agent** - Separate agents for different pipeline stages

## Support

For issues or questions:
1. Check this README
2. Review `main.py` for comparison
3. Enable LangSmith tracing for debugging
4. Use LangGraph Studio for visual inspection

---

**Created**: 2025-09-29
**Version**: 1.0.0
**Author**: Pipeline Agent Generator