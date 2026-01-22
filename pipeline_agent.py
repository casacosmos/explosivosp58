#!/usr/bin/env python3
"""
Unified LangGraph Pipeline Agent
Orchestrates all 8 tank processing steps using LangGraph tools and state management.
"""

import os
import sys
import json
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Annotated, Literal
from datetime import datetime
from enum import Enum
import traceback

# LangGraph imports
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict




# ============================================================================
# STATE DEFINITION
# ============================================================================

class PipelineState(TypedDict):
    """State for the complete pipeline execution"""
    # Input configuration
    input_file: str
    input_type: str  # "kmz", "excel", "csv"
    output_dir: str
    session_id: str
    config: Dict[str, Any]

    # Artifacts (paths to intermediate files)
    kmz_parsed: Optional[Dict[str, Any]]  # {"excel": path, "polygon": path}
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
    messages: Annotated[List[BaseMessage], add_messages]

    # Metrics
    tank_count: int
    processing_stats: Dict[str, Any]
    start_time: Optional[float]
    end_time: Optional[float]


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@tool
def parse_kmz_tool(kmz_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Parse KMZ/KML file to extract tank locations and boundary polygon.

    Args:
        kmz_path: Path to KMZ or KML file
        output_dir: Directory for output files

    Returns:
        Dictionary with excel template path, polygon path, and metadata
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "python", "kmz_parser_agent.py",
            kmz_path,
            "-o", str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"KMZ parsing failed: {result.stderr}",
                "excel": None,
                "polygon": None
            }

        # Find generated files
        excel_files = list(output_path.glob("tank_locations_*.xlsx"))
        polygon_files = list(output_path.glob("polygon_*.txt"))
        
        excel_path = str(excel_files[0]) if excel_files else None
        
        # Analyze content for richness
        data_status = "unknown"
        if excel_path:
            import pandas as pd
            try:
                df = pd.read_excel(excel_path)
                # Check if capacity or measurements are filled
                has_capacity = df['Tank Capacity'].notna().any() if 'Tank Capacity' in df.columns else False
                has_measurements = df['Tank Measurements'].notna().any() if 'Tank Measurements' in df.columns else False
                
                if not has_capacity and not has_measurements:
                    data_status = "names_only"
                else:
                    data_status = "complete"
            except Exception:
                pass

        return {
            "success": True,
            "excel": excel_path,
            "polygon": str(polygon_files[0]) if polygon_files else None,
            "data_status": data_status,
            "message": f"KMZ parsed successfully (Status: {data_status})"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"KMZ parsing exception: {str(e)}",
            "excel": None,
            "polygon": None
        }














@tool
def update_excel_tool(
    excel_path: str,
    hud_results_json: str,
    output_path: str
) -> Dict[str, Any]:
    """
    Update Excel file with HUD ASD calculation results.

    Args:
        excel_path: Path to original Excel file
        hud_results_json: Path to HUD results JSON
        output_path: Path for updated Excel file

    Returns:
        Dictionary with updated Excel path
    """
    try:
        cmd = [
            "python", "update_excel_with_results.py",
            excel_path,
            hud_results_json,
            "-o", output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Excel update failed: {result.stderr}",
                "excel_path": None
            }

        return {
            "success": True,
            "excel_path": output_path,
            "message": "Excel updated with HUD results"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Excel update exception: {str(e)}",
            "excel_path": None
        }


@tool
def calculate_distances_tool(
    excel_path: str,
    polygon_file: str,
    output_excel: str
) -> Dict[str, Any]:
    """
    Calculate distances from tanks (in Excel) to polygon boundary.
    
    IMPORTANT: Uses NAD83 / Puerto Rico & Virgin Islands (EPSG:32161) for high accuracy.

    Args:
        excel_path: Path to Excel file with tank coordinates
        polygon_file: Path to polygon coordinates file
        output_excel: Path for output Excel with distances

    Returns:
        Dictionary with results path
    """
    try:
        cmd = [
            "python", "calculate_distances.py",
            excel_path,
            polygon_file,
            "-o", output_excel
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Distance calculation failed: {result.stderr}",
                "updated_excel": None
            }

        return {
            "success": True,
            "updated_excel": output_excel,
            "message": "Distances calculated successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Distance calculation exception: {str(e)}",
            "updated_excel": None
        }





@tool
def create_output_kmz_tool(
    compliance_excel: str,
    output_kmz: str
) -> Dict[str, Any]:
    """
    Create output KMZ file with tank locations labeled by capacities.

    Args:
        compliance_excel: Path to final compliance Excel file
        output_kmz: Path for output KMZ file

    Returns:
        Dictionary with success status and output path
    """
    try:
        cmd = [
            "python", "create_output_kmz.py",
            compliance_excel,
            "-o", output_kmz
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"KMZ creation failed: {result.stderr}",
                "output_kmz": None
            }

        return {
            "success": True,
            "output_kmz": output_kmz,
            "message": f"Created output KMZ: {Path(output_kmz).name}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Compliance check exception: {str(e)}",
            "compliance_excel": None
        }


@tool
def create_buffer_kmz_tool(
    input_file: str,
    radius: float,
    unit: str = "miles",
    output_dir: str = "outputs"
) -> Dict[str, Any]:
    """
    Create a buffer zone around a site polygon.

    Args:
        input_file: Path to KMZ or Session JSON file containing the site polygon
        radius: Buffer radius (e.g., 1, 0.5, 3000)
        unit: Unit of measurement (miles, feet, meters, km)
        output_dir: Directory for output files

    Returns:
        Dictionary with success status and output path
    """
    try:
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Construct command
        cmd = [
            "python", "create_universal_buffer_kmz.py",
            input_file,
            "-r", str(radius),
            "-u", unit,
            "-d", str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Buffer creation failed: {result.stderr}",
                "output_kmz": None
            }

        # Parse output to find the created file
        # The script prints "KMZ created: path/to/file.kmz"
        for line in result.stdout.splitlines():
            if line.startswith("KMZ created:"):
                kmz_path = line.split(":", 1)[1].strip()
                return {
                    "success": True,
                    "output_kmz": kmz_path,
                    "message": f"Created buffer KMZ: {Path(kmz_path).name}"
                }

        return {
            "success": False,
            "error": "Buffer script completed but output path not found",
            "output_kmz": None
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Buffer creation exception: {str(e)}",
            "output_kmz": None
        }





@tool
def human_approval_tool(
    message: str,
    data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Request human approval or input for a decision point.

    Args:
        message: Message to display to human
        data: Optional data context

    Returns:
        Dictionary with approval status
    """
    # In production, this would integrate with the API/WebSocket
    # For now, just log and auto-approve
    print(f"\n{'='*60}")
    print(f"HUMAN APPROVAL REQUESTED")
    print(f"Message: {message}")
    if data:
        print(f"Data: {json.dumps(data, indent=2)}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "approved": True,
        "message": "Auto-approved (human approval tool)"
    }


@tool
def perform_ocr_tool(image_path: str) -> Dict[str, Any]:
    """
    Perform OCR on an image (e.g., field data sheet) to extract table data.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary with extracted text and structured data if possible
    """
    try:
        # Try importing pytesseract
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return {
                "success": False,
                "error": "OCR libraries not installed. Please install pytesseract and Pillow.",
                "data": None
            }

        text = pytesseract.image_to_string(Image.open(image_path))
        
        # Very basic parsing heuristic (can be improved)
        lines = text.split('\n')
        data = [line.split() for line in lines if line.strip()]

        return {
            "success": True,
            "text": text,
            "data": data,
            "message": "OCR performed successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"OCR exception: {str(e)}",
            "data": None
        }

@tool
def merge_data_tool(
    source_data: List[List[str]],
    target_file: str,
    output_file: str = None
) -> Dict[str, Any]:
    """
    Update an Excel/CSV file with data extracted from OCR or another source.

    Args:
        source_data: List of rows (lists of strings)
        target_file: Path to the existing Excel/CSV file
        output_file: Path for the updated file

    Returns:
        Dictionary with success status
    """
    try:
        import pandas as pd
        
        df = pd.read_excel(target_file) if target_file.endswith(('.xlsx', '.xls')) else pd.read_csv(target_file)
        
        # Logic to merge would go here. For now, we'll append or try to match names.
        # This is a placeholder for complex merge logic.
        
        if not output_file:
            output_file = target_file
            
        # For demonstration: just logging that we would merge
        print(f"Would merge {len(source_data)} rows into {target_file}")
        
        return {
            "success": True,
            "output_file": output_file,
            "message": f"Data merged into {Path(output_file).name} (Simulation)"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Merge exception: {str(e)}"
        }

# ============================================================================
# NODE FUNCTIONS
# ============================================================================

def detect_input_node(state: PipelineState) -> PipelineState:
    """Detect input file type and initialize state."""
    ext = Path(state["input_file"]).suffix.lower()

    if ext in [".kmz", ".kml"]:
        state["input_type"] = "kmz"
    elif ext == ".csv":
        state["input_type"] = "csv"
    elif ext in [".xlsx", ".xls"]:
        state["input_type"] = "excel"
    elif ext in [".png", ".jpg", ".jpeg", ".pdf"]:
        state["input_type"] = "image"
    else:
        state["input_type"] = "unknown"

    state["current_step"] = "detect_input"
    state["messages"].append(
        AIMessage(content=f"Detected input type: {state['input_type']}")
    )

    return state


def parse_kmz_node(state: PipelineState) -> PipelineState:
    """Parse KMZ file using tool."""
    state["current_step"] = "parse_kmz"
    state["messages"].append(AIMessage(content="Parsing KMZ file..."))

    result = parse_kmz_tool.invoke({
        "kmz_path": state["input_file"],
        "output_dir": state["output_dir"]
    })

    if result["success"]:
        state["kmz_parsed"] = result
        state["excel_file"] = result["excel"]
        state["completed_steps"].append("kmz_parse")
        state["messages"].append(
            AIMessage(content=f"✓ KMZ parsed: {result['message']}")
        )
    else:
        state["errors"].append(result["error"])
        state["messages"].append(
            AIMessage(content=f"✗ KMZ parsing failed: {result['error']}")
        )

    return state


def human_fill_excel_node(state: PipelineState) -> PipelineState:
    """Prompt human to fill Excel template."""
    state["current_step"] = "human_fill_excel"

    excel_path = state["excel_file"]
    state["messages"].append(
        HumanMessage(content=f"Please fill the Excel template at: {excel_path}")
    )

    # Request human approval before proceeding
    approval = human_approval_tool.invoke({
        "message": "Excel template ready for filling. Proceed when complete.",
        "data": {"excel_path": excel_path}
    })

    if approval["approved"]:
        state["completed_steps"].append("human_fill_excel")

    return state














def update_excel_node(state: PipelineState) -> PipelineState:
    """Update Excel with HUD results using tool."""
    state["current_step"] = "update_excel"

    # Skip if HUD processing failed
    if not state.get("hud_results_json"):
        state["warnings"].append("Skipping Excel update (no HUD results)")
        return state

    state["messages"].append(AIMessage(content="Updating Excel with HUD results..."))

    excel_path = state["excel_file"] or state["input_file"]
    output_path = str(Path(state["output_dir"]) / "with_hud.xlsx")

    result = update_excel_tool.invoke({
        "excel_path": excel_path,
        "hud_results_json": state["hud_results_json"],
        "output_path": output_path
    })

    if result["success"]:
        state["updated_excel"] = result["excel_path"]
        state["completed_steps"].append("update_excel")
        state["messages"].append(AIMessage(content="✓ Excel updated with HUD results"))
    else:
        state["warnings"].append(result["error"])
        state["messages"].append(
            AIMessage(content=f"⚠ Excel update failed: {result['error']}")
        )

    return state


def calculate_distances_node(state: PipelineState) -> PipelineState:
    """Calculate distances to polygon boundary using tool."""
    state["current_step"] = "calculate_distances"

    # Check if polygon available
    polygon_file = None
    if state.get("kmz_parsed"):
        polygon_file = state["kmz_parsed"].get("polygon")

    if not polygon_file:
        state["warnings"].append("No polygon file available - skipping distance calculations")
        state["messages"].append(
            AIMessage(content="⚠ Skipping distance calculations (no polygon)")
        )
        return state

    state["messages"].append(AIMessage(content="Calculating distances to boundary..."))

    # Use updated excel if available, otherwise original
    input_excel = state.get("updated_excel") or state.get("excel_file")
    output_excel = str(Path(state["output_dir"]) / "tanks_with_distances.xlsx")

    result = calculate_distances_tool.invoke({
        "excel_path": input_excel,
        "polygon_file": polygon_file,
        "output_excel": output_excel
    })

    if result["success"]:
        state["updated_excel"] = result["updated_excel"]
        state["completed_steps"].append("calculate_distances")
        state["messages"].append(AIMessage(content="✓ Distances calculated"))
    else:
        state["warnings"].append(result["error"])
        state["messages"].append(
            AIMessage(content=f"⚠ Distance calculation failed: {result['error']}")
        )

    return state





def create_output_kmz_node(state: PipelineState) -> PipelineState:
    """Create output KMZ with labeled tank locations."""
    state["current_step"] = "create_output_kmz"
    state["messages"].append(AIMessage(content="Creating output KMZ..."))

    # Use compliance excel to create KMZ
    compliance_excel = state.get("compliance_excel")
    if not compliance_excel:
        state["warnings"].append("No compliance Excel found, skipping KMZ creation")
        return state

    output_kmz = str(Path(state["output_dir"]) / "tanks_output.kmz")

    result = create_output_kmz_tool.invoke({
        "compliance_excel": compliance_excel,
        "output_kmz": output_kmz
    })

    if result["success"]:
        state["output_kmz"] = result["output_kmz"]
        state["completed_steps"].append("create_output_kmz")
        state["messages"].append(AIMessage(content=f"✓ Output KMZ created: {Path(output_kmz).name}"))
    else:
        state["errors"].append(result["error"])
        state["messages"].append(
            AIMessage(content=f"✗ KMZ creation failed: {result['error']}")
        )

    return state


def summarize_results_node(state: PipelineState) -> PipelineState:
    """Summarize pipeline execution results."""
    state["current_step"] = "summarize"
    state["end_time"] = datetime.now().timestamp()

    duration = state["end_time"] - state["start_time"]

    summary = f"""
Pipeline Execution Summary
{'='*60}
Session ID: {state['session_id']}
Duration: {duration:.2f} seconds
Tank Count: {state.get('tank_count', 0)}

Completed Steps: {len(state['completed_steps'])}
{chr(10).join([f'  ✓ {step}' for step in state['completed_steps']])}

Generated Files:
"""

    if state.get("compliance_excel"):
        summary += f"  - Compliance Report: {state['compliance_excel']}\n"
    if state.get("pdf_report"):
        summary += f"  - PDF Report: {state['pdf_report']}\n"
    if state.get("updated_excel"):
        summary += f"  - Updated Excel: {state['updated_excel']}\n"
    if state.get("output_kmz"):
        summary += f"  - Output KMZ: {state['output_kmz']}\n"

    if state.get("errors"):
        summary += f"\nErrors: {len(state['errors'])}\n"
        for err in state['errors']:
            summary += f"  ✗ {err}\n"

    if state.get("warnings"):
        summary += f"\nWarnings: {len(state['warnings'])}\n"
        for warn in state['warnings']:
            summary += f"  ⚠ {warn}\n"

    summary += f"\n{'='*60}"

    state["messages"].append(AIMessage(content=summary))
    state["processing_stats"]["summary"] = summary

    return state





# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_pipeline_graph() -> StateGraph:
    """Build the complete pipeline StateGraph."""

    workflow = StateGraph(PipelineState)

    # Add all nodes
    workflow.add_node("detect_input", detect_input_node)
    workflow.add_node("parse_kmz", parse_kmz_node)
    workflow.add_node("human_fill_excel", human_fill_excel_node)
    workflow.add_node("update_excel", update_excel_node)
    workflow.add_node("calculate_distances", calculate_distances_node)
    workflow.add_node("create_output_kmz", create_output_kmz_node)
    workflow.add_node("summarize", summarize_results_node)

    # Add edges - Start
    workflow.add_edge(START, "detect_input")

    # Conditional routing after detection
    # For simplicity in this simplified agent:
    # KMZ -> parse_kmz -> human_fill_excel -> update_excel
    # Excel -> update_excel
    
    workflow.add_conditional_edges(
        "detect_input",
        lambda state: "parse_kmz" if state["input_type"] == "kmz" else "update_excel"
    )

    # KMZ path
    workflow.add_edge("parse_kmz", "human_fill_excel")
    workflow.add_edge("human_fill_excel", "update_excel")

    # Pipeline continuation
    workflow.add_edge("update_excel", "calculate_distances")
    
    # After distances, create KMZ
    workflow.add_edge("calculate_distances", "create_output_kmz")
    
    # Finish
    workflow.add_edge("create_output_kmz", "summarize")
    workflow.add_edge("summarize", END)

    return workflow


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_pipeline_agent(
    input_file: str,
    output_dir: str = "outputs",
    session_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    stream_progress: bool = False
) -> Dict[str, Any]:
    """
    Run the complete pipeline as a LangGraph agent.

    Args:
        input_file: Path to input file (KMZ/Excel/CSV)
        output_dir: Output directory for artifacts
        session_id: Optional session ID for persistence
        config: Optional configuration dictionary
        stream_progress: Whether to stream progress updates

    Returns:
        Final state dictionary with all results
    """

    # Validate input file exists
    if not Path(input_file).exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate session ID if not provided
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create graph with checkpointer for persistence
    checkpointer = MemorySaver()
    workflow = create_pipeline_graph()
    agent = workflow.compile(checkpointer=checkpointer)

    # Initialize state
    initial_state: PipelineState = {
        "input_file": str(Path(input_file).resolve()),
        "input_type": "",
        "output_dir": str(output_path.resolve()),
        "session_id": session_id,
        "config": config or {},

        # Artifacts
        "kmz_parsed": None,
        "excel_file": None,
        "tank_config_json": None,
        "validation_passed": False,
        "hud_results_json": None,
        "pdf_report": None,
        "updated_excel": None,
        "distances_json": None,
        "compliance_excel": None,

        # Processing state
        "current_step": "",
        "completed_steps": [],
        "errors": [],
        "warnings": [],
        "messages": [],

        # Metrics
        "tank_count": 0,
        "processing_stats": {},
        "start_time": datetime.now().timestamp(),
        "end_time": None
    }

    # Run the agent with streaming
    config_dict = {"configurable": {"thread_id": session_id}}

    if stream_progress:
        print(f"\n{'='*70}")
        print(f"  TANK PROCESSING PIPELINE - AGENT MODE")
        print(f"{'='*70}")
        print(f"Input: {input_file}")
        print(f"Output: {output_dir}")
        print(f"Session: {session_id}\n")

        for event in agent.stream(initial_state, config_dict):
            # Print node updates
            for node_name, node_state in event.items():
                if node_name != "__end__":
                    current = node_state.get("current_step", node_name)
                    print(f"→ {current}")

                    # Print any new messages
                    messages = node_state.get("messages", [])
                    if messages and len(messages) > 0:
                        last_msg = messages[-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  {last_msg.content}")
    else:
        # Run without streaming
        result = agent.invoke(initial_state, config_dict)

    # Get final state
    final_state = agent.get_state(config_dict)

    return dict(final_state.values)


# ============================================================================
# CHATBOT INTERFACE
# ============================================================================

def run_chatbot():
    """Run the agent in interactive chatbot mode."""
    from langchain.chat_models import init_chat_model
    from langgraph.prebuilt import ToolNode, tools_condition

    print("""
╔════════════════════════════════════════════════════════════════╗
║             Spatial & Data Pipeline Agent - Chat Mode         ║
╠════════════════════════════════════════════════════════════════╣
║  I specialize in spatial analysis, KMZ processing, and        ║
║  data ingestion (OCR/Merging).                                ║
║                                                                ║
║  For compliance checks & calculations, please use the         ║
║  Compliance Agent.                                            ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Initialize LLM
    llm = init_chat_model(model_name="gpt-4o")

    # Bind tools to LLM
    tools = [
        parse_kmz_tool,
        update_excel_tool,
        calculate_distances_tool,
        create_output_kmz_tool,
        create_buffer_kmz_tool,
        perform_ocr_tool,
        merge_data_tool
    ]

    llm_with_tools = llm.bind_tools(tools)

    # Create tool node
    tool_node = ToolNode(tools)

    # Build graph for chat
    chat_graph = StateGraph(PipelineState)

    # Add nodes
    chat_graph.add_node("agent", lambda state: {"messages": [llm_with_tools.invoke(state["messages"])[-1]]})
    chat_graph.add_node("tools", tool_node)

    # Add edges
    chat_graph.add_edge(START, "agent")
    chat_graph.add_conditional_edges("agent", tools_condition)
    chat_graph.add_edge("tools", "agent")

    # Compile with memory
    memory = MemorySaver()
    chat_app = chat_graph.compile(checkpointer=memory)

    # Initialize state
    state = {
        "messages": [
            AIMessage(content="""
I am the Tank Compliance Agent, an intelligent assistant for processing tank location data. 

**My Core Capabilities:**

1.  **Smart KMZ Processing**:
    *   I will parse your KMZ file to extract site boundaries and tank locations.
    *   **Crucial Step**: I analyze the extracted data. 
        *   If I see **only names** (no measurements/capacities), I will explicitly offer to generate a CSV table for you to fill out.
        *   If I see existing data, I will proceed with analysis.
    *   *Note*: I always use the **EPSG:32161 (Puerto Rico & Virgin Islands)** coordinate system for high-accuracy distance calculations.

2.  **Field Data Integration (Image/OCR)**:
    *   Upload an image of a field data sheet or spreadsheet (PNG, JPG, PDF).
    *   I will perform OCR to extract the text and structured data.
    *   I will then offer to **merge** this new data into your existing Excel report or update your KMZ file directly.

3.  **Data Management**:
    *   If you provide a CSV, I will ask how you want to handle it:
        *   **Update**: Append new rows or update existing entries?
        *   **Merge**: Combine with data from another source?
        *   **Calculate**: Run volume or distance calculations?

**How to start:**
*   "Process `file.kmz`"
*   "Analyze this image `data.jpg`"
*   "Help"
""")
        ],
        "output_dir": "outputs",
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "input_file": "",
        "input_type": "",
        "config": {"use_improved_parser": True},
        "completed_steps": [],
        "errors": [],
        "warnings": [],
        "tank_count": 0,
        "processing_stats": {},
        "start_time": datetime.now().timestamp()
    }

    # Chat loop
    while True:
        try:
            user_input = input("\n📝 You: ").strip()

            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\n👋 Goodbye! Thank you for using the Tank Compliance Agent.")
                break

            if user_input.lower() == "help":
                print("""
Available commands:
  • process <file>  - Process a KMZ or Excel file
  • create template - Create an Excel template
  • status         - Show current processing status
  • help           - Show this help message
  • exit           - Exit the chat
                """)
                continue

            # Add user message to state
            state["messages"].append(HumanMessage(content=user_input))

            # Process through graph
            config = {"configurable": {"thread_id": state["session_id"]}}
            result = chat_app.invoke(state, config)

            # Get response
            last_message = result["messages"][-1]
            if hasattr(last_message, "content"):
                print(f"\n🤖 Agent: {last_message.content}")

            # Update state
            state = result

        except KeyboardInterrupt:
            print("\n\n👋 Chat interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Tank Processing Pipeline Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s tanks.xlsx
  %(prog)s facility.kmz -o reports/
  %(prog)s tanks.csv --session my_session_001
        """
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input file (KMZ/KML/Excel/CSV) - not required in chat mode"
    )

    parser.add_argument(
        "-o", "--output",
        default="outputs",
        help="Output directory (default: outputs)"
    )

    parser.add_argument(
        "--session",
        help="Session ID for persistence"
    )

    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable progress streaming"
    )

    parser.add_argument(
        "--legacy-parser",
        action="store_true",
        help="Use legacy parser instead of improved"
    )

    parser.add_argument(
        "--chat",
        action="store_true",
        help="Run in interactive chatbot mode"
    )

    args = parser.parse_args()

    # Run in chat mode if requested
    if args.chat:
        run_chatbot()
        return

    # Otherwise run standard pipeline mode
    if not args.input_file:
        parser.error("Input file is required in pipeline mode (use --chat for interactive mode)")

    config = {
        "use_improved_parser": not args.legacy_parser
    }

    try:
        result = run_pipeline_agent(
            input_file=args.input_file,
            output_dir=args.output,
            session_id=args.session,
            config=config,
            stream_progress=not args.no_stream
        )

        # Print final summary
        if result.get("processing_stats", {}).get("summary"):
            print("\n" + result["processing_stats"]["summary"])

        sys.exit(0 if not result.get("errors") else 1)

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()