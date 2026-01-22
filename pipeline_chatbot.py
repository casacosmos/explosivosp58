#!/usr/bin/env python3
"""
Pipeline Chatbot - Conversational Interface for Tank Processing Pipeline
Uses LangGraph to provide natural language interaction with the full pipeline.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime
import traceback

# LangGraph and LangChain imports
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

# Pipeline agent imports
from pipeline_agent import (
    run_pipeline_agent,
    PipelineState,
    create_pipeline_graph
)


# ============================================================================
# CHATBOT STATE DEFINITION
# ============================================================================

class ChatbotState(TypedDict):
    """
    Extended state combining conversation messages with pipeline execution state.
    """
    # Conversation
    messages: Annotated[List[BaseMessage], add_messages]

    # Pipeline context
    session_id: Optional[str]
    pipeline_active: bool
    user_intent: str  # Current user goal/intent

    # Pipeline state (subset for chatbot awareness)
    input_file: Optional[str]
    output_dir: str
    current_step: Optional[str]
    completed_steps: List[str]
    errors: List[str]
    warnings: List[str]
    tank_count: int

    # Results tracking
    artifacts: Dict[str, Any]  # Paths to generated files
    processing_stats: Dict[str, Any]


# ============================================================================
# CONVERSATIONAL TOOL WRAPPERS
# ============================================================================

@tool
def process_pipeline_tool(
    file_path: str,
    session_id: Optional[str] = None,
    output_dir: str = "outputs"
) -> Dict[str, Any]:
    """
    Start full pipeline processing for a tank configuration file.

    Use this when user wants to:
    - Process a KMZ/Excel/CSV file
    - Run the complete tank analysis pipeline
    - Generate compliance reports

    Args:
        file_path: Path to input file (KMZ, Excel, or CSV)
        session_id: Optional session ID for resuming/tracking
        output_dir: Directory for output files (default: outputs)

    Returns:
        Dictionary with success status, session_id, and initial results
    """
    try:
        # Validate file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "session_id": session_id
            }

        # Generate session ID if not provided
        if not session_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"chat_{timestamp}"

        # Create session-specific output directory
        session_output_dir = Path(output_dir) / session_id
        session_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n🚀 Starting pipeline for session: {session_id}")
        print(f"📁 Input file: {file_path}")
        print(f"📂 Output directory: {session_output_dir}")
        print(f"⏳ This may take 7-10 minutes for 24 tanks...\n")

        # Run pipeline with the actual run_pipeline_agent function
        result = run_pipeline_agent(
            input_file=str(file_path_obj.resolve()),
            output_dir=str(session_output_dir),
            session_id=session_id,
            config={"use_improved_parser": True},
            stream_progress=True  # Enable streaming for user feedback
        )

        # Save status file for later retrieval
        status_file = session_output_dir / "status.json"
        with open(status_file, 'w') as f:
            json.dump({
                "session_id": session_id,
                "current_step": result.get("current_step", "completed"),
                "completed_steps": result.get("completed_steps", []),
                "tank_count": result.get("tank_count", 0),
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
                "start_time": result.get("start_time"),
                "end_time": result.get("end_time")
            }, indent=2)

        print(f"\n✅ Pipeline completed successfully!")
        print(f"📊 Processed {result.get('tank_count', 0)} tanks")
        print(f"📁 Results saved to: {session_output_dir}\n")

        return {
            "success": True,
            "session_id": session_id,
            "message": f"Pipeline completed successfully! Processed {result.get('tank_count', 0)} tanks.\n\nResults saved to: {session_output_dir}\n\nKey artifacts:\n- Compliance Excel: {result.get('compliance_excel', 'N/A')}\n- PDF Report: {result.get('pdf_report', 'N/A')}\n- Updated Excel: {result.get('updated_excel', 'N/A')}",
            "tank_count": result.get("tank_count", 0),
            "completed_steps": result.get("completed_steps", []),
            "artifacts": {
                "compliance_excel": result.get("compliance_excel"),
                "pdf_report": result.get("pdf_report"),
                "updated_excel": result.get("updated_excel"),
                "tank_config_json": result.get("tank_config_json"),
                "hud_results_json": result.get("hud_results_json"),
                "distances_json": result.get("distances_json")
            },
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
            "output_dir": str(session_output_dir)
        }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"File not found: {str(e)}",
            "session_id": session_id
        }
    except Exception as e:
        error_msg = f"Pipeline execution failed: {str(e)}"
        print(f"\n❌ {error_msg}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": error_msg,
            "session_id": session_id,
            "traceback": traceback.format_exc()
        }


@tool
def check_status_tool(session_id: str) -> Dict[str, Any]:
    """
    Check the current status of a pipeline execution.

    Use this when user asks about:
    - Current processing status
    - What step is running
    - How many tanks processed
    - Any errors or warnings

    Args:
        session_id: Session identifier to check

    Returns:
        Dictionary with current pipeline state and progress
    """
    try:
        # Load state from status file
        status_file = Path(f"outputs/{session_id}/status.json")

        if status_file.exists():
            with open(status_file, 'r') as f:
                status = json.load(f)

            current_step = status.get("current_step", "unknown")
            completed_steps = status.get("completed_steps", [])
            total_steps = 9  # Total pipeline steps
            progress = len(completed_steps)

            # Format message
            if current_step == "completed":
                message = f"✅ Session {session_id} completed successfully!\n"
                message += f"📊 Processed {status.get('tank_count', 0)} tanks\n"
                message += f"✓ Completed all {progress}/{total_steps} steps"
            else:
                message = f"⏳ Session {session_id} is currently at step: {current_step}\n"
                message += f"📊 Processing {status.get('tank_count', 0)} tanks\n"
                message += f"✓ Completed {progress}/{total_steps} steps: {', '.join(completed_steps[-3:])}"

            if status.get("errors"):
                message += f"\n❌ Errors: {len(status['errors'])}"
            if status.get("warnings"):
                message += f"\n⚠️  Warnings: {len(status['warnings'])}"

            return {
                "success": True,
                "session_id": session_id,
                "current_step": current_step,
                "completed_steps": completed_steps,
                "progress_percent": (progress / total_steps) * 100,
                "tank_count": status.get("tank_count", 0),
                "errors": status.get("errors", []),
                "warnings": status.get("warnings", []),
                "start_time": status.get("start_time"),
                "end_time": status.get("end_time"),
                "message": message
            }
        else:
            # Check if session directory exists at all
            session_dir = Path(f"outputs/{session_id}")
            if not session_dir.exists():
                return {
                    "success": False,
                    "error": f"Session directory not found: {session_id}",
                    "message": f"Session '{session_id}' does not exist. Use list_sessions to see available sessions."
                }
            else:
                return {
                    "success": False,
                    "error": f"Status file not found for session: {session_id}",
                    "message": f"Session '{session_id}' exists but status.json not found. Pipeline may not have started yet."
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to check status: {str(e)}",
            "message": f"Error reading status for session {session_id}: {str(e)}"
        }


@tool
def get_results_tool(
    session_id: str,
    result_type: str = "summary"
) -> Dict[str, Any]:
    """
    Retrieve results from a completed pipeline execution.

    Use this when user asks about:
    - Final compliance results
    - Generated files and reports
    - Specific output artifacts
    - Summary of processing

    Args:
        session_id: Session identifier
        result_type: Type of result to retrieve:
            - "summary": Overview of all results
            - "compliance": Compliance Excel file info
            - "pdf": PDF report info
            - "excel": Updated Excel file info
            - "all": All artifact paths

    Returns:
        Dictionary with requested results and file paths
    """
    try:
        output_dir = Path(f"outputs/{session_id}")

        if not output_dir.exists():
            return {
                "success": False,
                "error": f"No results found for session: {session_id}",
                "message": f"Session directory not found: {session_id}. Use list_sessions to see available sessions."
            }

        # Scan for artifacts with more specific patterns
        artifacts = {
            "compliance_excel": None,
            "pdf_report": None,
            "updated_excel": None,
            "tank_config_json": None,
            "hud_results_json": None,
            "distances_json": None
        }

        # Search patterns for each artifact type
        artifact_patterns = {
            "compliance_excel": ["*compliance*.xlsx", "*final*.xlsx"],
            "pdf_report": ["*ASD*.pdf", "*.pdf"],
            "updated_excel": ["*with_hud*.xlsx", "*updated*.xlsx"],
            "tank_config_json": ["tank_config.json", "*tank*.json"],
            "hud_results_json": ["fast_results.json", "*hud*.json"],
            "distances_json": ["distances.json", "*distance*.json"]
        }

        # Search for each artifact type
        for artifact_key, patterns in artifact_patterns.items():
            for pattern in patterns:
                matches = list(output_dir.glob(f"**/{pattern}"))
                if matches:
                    artifacts[artifact_key] = str(matches[0])  # Take first match
                    break

        # Count how many artifacts were found
        found_count = sum(1 for v in artifacts.values() if v is not None)

        # Format response based on result_type
        if result_type == "summary":
            message = f"📊 Pipeline Results for Session: {session_id}\n"
            message += f"📁 Output Directory: {output_dir}\n"
            message += f"✓ Found {found_count}/6 artifacts\n\n"
            message += f"📄 Compliance Report: {Path(artifacts['compliance_excel']).name if artifacts['compliance_excel'] else '❌ Not generated'}\n"
            message += f"📋 PDF Report: {Path(artifacts['pdf_report']).name if artifacts['pdf_report'] else '❌ Not generated'}\n"
            message += f"📊 Updated Excel: {Path(artifacts['updated_excel']).name if artifacts['updated_excel'] else '❌ Not generated'}\n"
            message += f"🗂️  Tank Config JSON: {Path(artifacts['tank_config_json']).name if artifacts['tank_config_json'] else '❌ Not found'}\n"
            message += f"🔍 HUD Results JSON: {Path(artifacts['hud_results_json']).name if artifacts['hud_results_json'] else '❌ Not found'}\n"
            message += f"📏 Distances JSON: {Path(artifacts['distances_json']).name if artifacts['distances_json'] else '❌ Not found'}"

        elif result_type == "compliance":
            if artifacts['compliance_excel']:
                message = f"✅ Compliance Excel: {artifacts['compliance_excel']}\n"
                message += f"This file contains the final compliance assessment (YES/NO/REVIEW) for each tank."
            else:
                message = "❌ Compliance report not found. Pipeline may not have completed successfully."

        elif result_type == "pdf":
            if artifacts['pdf_report']:
                message = f"✅ PDF Report: {artifacts['pdf_report']}\n"
                message += f"This file contains HUD ASD calculation results with screenshots."
            else:
                message = "❌ PDF report not found. Check if HUD processing completed."

        elif result_type == "excel":
            if artifacts['updated_excel']:
                message = f"✅ Updated Excel: {artifacts['updated_excel']}\n"
                message += f"This file contains the original data merged with HUD ASD values."
            else:
                message = "❌ Updated Excel not found. Check if Excel update step completed."

        else:  # all
            message = "📁 All Artifacts:\n\n"
            for k, v in artifacts.items():
                status = "✅" if v else "❌"
                file_name = Path(v).name if v else "Not found"
                message += f"{status} {k}: {file_name}\n"
                if v:
                    message += f"   Path: {v}\n"

        return {
            "success": True,
            "session_id": session_id,
            "result_type": result_type,
            "artifacts": artifacts,
            "artifacts_found": found_count,
            "output_directory": str(output_dir),
            "message": message
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve results: {str(e)}",
            "message": f"Error retrieving results for {session_id}: {str(e)}"
        }


@tool
def list_sessions_tool() -> Dict[str, Any]:
    """
    List all available pipeline sessions.

    Use this when user asks about:
    - Available sessions
    - Previous pipeline runs
    - Session history

    Returns:
        Dictionary with list of sessions and their basic info
    """
    try:
        outputs_dir = Path("outputs")

        if not outputs_dir.exists():
            return {
                "success": True,
                "sessions": [],
                "message": "No sessions found"
            }

        sessions = []
        for session_dir in outputs_dir.iterdir():
            if session_dir.is_dir():
                # Get session info
                status_file = session_dir / "status.json"
                session_info = {
                    "session_id": session_dir.name,
                    "created": session_dir.stat().st_ctime,
                    "status": "unknown"
                }

                if status_file.exists():
                    with open(status_file, 'r') as f:
                        status = json.load(f)
                        session_info["status"] = status.get("current_step", "unknown")
                        session_info["tank_count"] = status.get("tank_count", 0)

                sessions.append(session_info)

        # Sort by creation time
        sessions.sort(key=lambda x: x.get("created", 0), reverse=True)

        message = f"Found {len(sessions)} session(s):\n"
        for s in sessions[:10]:  # Show max 10
            message += f"- {s['session_id']}: {s.get('tank_count', 0)} tanks, status: {s['status']}\n"

        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "message": message
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list sessions: {str(e)}"
        }


@tool
def fill_excel_conversational_tool(
    excel_path: str,
    tank_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Fill Excel template with tank data provided through conversation.

    This tool replaces manual Excel filling for KMZ workflow.
    User provides tank information via chat, and this tool populates the Excel.

    Use this when:
    - User has processed a KMZ file
    - User provides tank details in conversation
    - Need to fill Excel template automatically

    Args:
        excel_path: Path to Excel template file
        tank_data: List of dictionaries with tank information
            Each dict should contain:
            - tank_id: Tank identifier (e.g., "T-01")
            - capacity: Tank capacity in gallons (or with unit like "50000 gal")
            - length: Tank length (e.g., "30 ft" or "30")
            - width: Tank width (e.g., "20 ft" or "20")
            - height: Tank height (e.g., "15 ft" or "15")
            - product: Product stored (e.g., "Diesel", "Gasoline")
            - Additional optional fields as needed

    Returns:
        Dictionary with success status and filled Excel path
    """
    try:
        import pandas as pd
        from pathlib import Path

        excel_file = Path(excel_path)
        if not excel_file.exists():
            return {
                "success": False,
                "error": f"Excel template not found: {excel_path}",
                "message": "Cannot find the Excel template. Make sure KMZ parsing completed successfully."
            }

        # Read existing Excel template
        df = pd.read_excel(excel_path)

        # Track how many tanks we're filling
        filled_count = 0

        # Process each tank data entry
        for tank_info in tank_data:
            tank_id = tank_info.get("tank_id")
            if not tank_id:
                continue

            # Find the row for this tank in the Excel
            tank_row = df[df.iloc[:, 0].astype(str).str.contains(str(tank_id), case=False, na=False)]

            if not tank_row.empty:
                idx = tank_row.index[0]

                # Fill capacity
                if "capacity" in tank_info:
                    capacity = str(tank_info["capacity"])
                    # Extract numeric value if unit is included
                    import re
                    capacity_match = re.search(r'([\d,\.]+)', capacity)
                    if capacity_match:
                        df.at[idx, "Tank Capacity"] = str(capacity_match.group(1))

                # Fill dimensions
                measurements = []
                if "length" in tank_info:
                    measurements.append(str(tank_info["length"]))
                if "width" in tank_info:
                    measurements.append(str(tank_info["width"]))
                if "height" in tank_info:
                    measurements.append(str(tank_info["height"]))

                if measurements:
                    # Find dimension column
                    dim_cols = [col for col in df.columns if "dimension" in col.lower() or "measurement" in col.lower() or "size" in col.lower()]
                    if dim_cols:
                        df.at[idx, dim_cols[0]] = " x ".join(measurements)
                    else:
                        # Create new column if needed
                        df.at[idx, "Tank Measurements"] = " x ".join(measurements)

                # Fill product type
                if "product" in tank_info:
                    # Find a product column
                    product_cols = [col for col in df.columns if "product" in col.lower() or "material" in col.lower()]
                    if product_cols:
                        df.at[idx, product_cols[0]] = str(tank_info["product"])

                # Fill any other custom fields
                for key, value in tank_info.items():
                    if key not in ["tank_id", "capacity", "length", "width", "height", "product"]:
                        # Try to find matching column
                        matching_cols = [col for col in df.columns if key.lower() in col.lower()]
                        if matching_cols:
                            df.at[idx, matching_cols[0]] = value

                filled_count += 1

        # Save filled Excel
        df.to_excel(excel_path, index=False)

        return {
            "success": True,
            "excel_path": excel_path,
            "tanks_filled": filled_count,
            "total_tanks": len(tank_data),
            "message": f"✅ Successfully filled {filled_count}/{len(tank_data)} tanks in Excel template.\n\nThe Excel file is now ready for pipeline processing.\n\nFile: {excel_path}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fill Excel: {str(e)}",
            "message": f"Error filling Excel template: {str(e)}\n\nPlease check the tank data format and try again."
        }


@tool
def help_tool() -> Dict[str, Any]:
    """
    Get help information about available commands and pipeline capabilities.

    Use this when user asks:
    - How to use the chatbot
    - What can the pipeline do
    - Available commands
    - Help or instructions

    Returns:
        Dictionary with help information
    """
    help_text = """
🤖 Pipeline Chatbot Help

I can help you process tank configuration files and generate compliance reports!

**What I can do:**
1. **Process files**: "Process tanks.xlsx" or "Run pipeline on juncos.kmz"
2. **Check status**: "What's the status?" or "How's processing going?"
3. **Get results**: "Show me the compliance report" or "Where's the PDF?"
4. **List sessions**: "Show me previous sessions" or "What pipelines have run?"
5. **Fill Excel via chat**: For KMZ files, provide tank data through conversation instead of manual Excel editing

**Pipeline Capabilities:**
- Parse KMZ files for tank locations and boundaries
- Convert Excel/CSV to standardized format
- Calculate tank volumes automatically
- Run HUD ASD calculations (6-8 min for 24 tanks)
- Generate PDF reports with screenshots
- Calculate distances to boundaries
- Assess compliance (YES/NO/REVIEW)
- Produce final compliance Excel report

**File Formats Supported:**
- KMZ/KML: Geographic data with tank locations
- Excel/CSV: Tank configuration with dimensions
- Accepted columns: Tank ID, dimensions, capacity, product, coordinates

**Example Conversations:**
- "Hi, I need to process tanks_juncos.xlsx with session juncos_2025"
- "What's the current status of session juncos_2025?"
- "Show me the compliance results"
- "List all my previous sessions"
- "Tank T-01 has capacity 50000 gallons, dimensions 30ft x 20ft x 15ft, stores Diesel"

**Session IDs:**
Use session IDs to track and resume pipeline executions. If you don't provide one, I'll generate one automatically.

**Need more info?** Just ask! I'm here to help. 🚀
"""

    return {
        "success": True,
        "message": help_text
    }


# ============================================================================
# CHATBOT GRAPH CONSTRUCTION
# ============================================================================

def create_chatbot_graph(llm_model: str = "anthropic:claude-3-5-sonnet-latest") -> StateGraph:
    """
    Create the chatbot graph with LLM, tools, and routing logic.

    Args:
        llm_model: Model identifier for LangChain init_chat_model

    Returns:
        Compiled StateGraph ready for conversation
    """
    # Initialize LLM
    llm = init_chat_model(llm_model)

    # Bind tools to LLM
    tools = [
        process_pipeline_tool,
        check_status_tool,
        get_results_tool,
        list_sessions_tool,
        fill_excel_conversational_tool,
        help_tool
    ]
    llm_with_tools = llm.bind_tools(tools)

    # Define chatbot node
    def chatbot_node(state: ChatbotState) -> ChatbotState:
        """
        Main chatbot node that interprets user requests and decides on actions.
        """
        # Prepare system message with context
        system_message = SystemMessage(content="""You are a helpful assistant for the Tank Processing Pipeline system.

Your role is to help users:
- Process tank configuration files (KMZ, Excel, CSV)
- Track pipeline execution status
- Retrieve compliance reports and results
- Collect tank data conversationally for KMZ workflows
- Answer questions about the pipeline

Be conversational, helpful, and proactive. When users ask to process files, use the process_pipeline_tool.
When they ask about status or results, use the appropriate tools.

For KMZ workflows, when users provide tank information (like "Tank T-01 has capacity 50000 gallons, dimensions 30ft x 20ft x 15ft, stores Diesel"),
use the fill_excel_conversational_tool to populate the Excel template with the provided data.

Always provide clear, informative responses. If a user provides a file path, extract it and use it with the appropriate tool.
If they mention a session ID, use it for tracking and resuming operations.""")

        # Build message history with system context
        messages = [system_message] + state["messages"]

        # Invoke LLM with tools
        response = llm_with_tools.invoke(messages)

        # Update state
        return {
            "messages": [response]
        }

    # Create graph
    graph_builder = StateGraph(ChatbotState)

    # Add nodes
    graph_builder.add_node("chatbot", chatbot_node)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)

    # Add edges with conditional routing
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,  # If LLM calls tools, go to tools node; otherwise END
    )
    graph_builder.add_edge("tools", "chatbot")  # After tools, return to chatbot

    return graph_builder


# ============================================================================
# CLI INTERFACE
# ============================================================================

def run_chatbot_cli(
    session_id: Optional[str] = None,
    llm_model: str = "anthropic:claude-3-5-sonnet-latest",
    checkpointer_type: str = "memory"
):
    """
    Run interactive chatbot CLI.

    Args:
        session_id: Optional session ID for conversation persistence
        llm_model: LLM model to use
        checkpointer_type: "memory" or "sqlite"
    """
    print("=" * 70)
    print("🤖 Pipeline Chatbot - Tank Processing Assistant")
    print("=" * 70)
    print()
    print("Type 'help' for available commands, 'quit' to exit")
    print()

    # Generate session ID if not provided
    if not session_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"chat_{timestamp}"

    print(f"Session ID: {session_id}")
    print()

    # Create checkpointer
    if checkpointer_type == "memory":
        checkpointer = MemorySaver()
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string("pipeline_chatbot.db")

    # Build graph
    graph_builder = create_chatbot_graph(llm_model=llm_model)
    graph = graph_builder.compile(checkpointer=checkpointer)

    # Configuration for thread persistence
    config = {"configurable": {"thread_id": session_id}}

    # Initialize state
    initial_state: ChatbotState = {
        "messages": [],
        "session_id": session_id,
        "pipeline_active": False,
        "user_intent": "",
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

    # Main conversation loop
    first_run = True
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Check for exit commands
            if user_input.lower() in ["quit", "exit", "q", "bye"]:
                print("\nAssistant: Goodbye! 👋")
                break

            # Stream graph execution
            print("\nAssistant: ", end="", flush=True)

            if first_run:
                # First run: initialize with user message
                events = graph.stream(
                    {**initial_state, "messages": [HumanMessage(content=user_input)]},
                    config,
                    stream_mode="values"
                )
                first_run = False
            else:
                # Subsequent runs: append new message
                events = graph.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config,
                    stream_mode="values"
                )

            # Process events and display responses
            for event in events:
                if "messages" in event and event["messages"]:
                    last_message = event["messages"][-1]

                    # Only print AI messages (skip tool messages)
                    if isinstance(last_message, AIMessage):
                        # Check if this is a new message we haven't printed yet
                        if last_message.content:
                            print(last_message.content)

            print()  # New line after response

        except KeyboardInterrupt:
            print("\n\nAssistant: Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n\n⚠️  Error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            print()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Chatbot - Conversational interface for tank processing"
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID for conversation persistence"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic:claude-3-5-sonnet-latest",
        help="LLM model to use (default: anthropic:claude-3-5-sonnet-latest)"
    )
    parser.add_argument(
        "--checkpointer",
        type=str,
        choices=["memory", "sqlite"],
        default="memory",
        help="Checkpointer type (default: memory)"
    )

    args = parser.parse_args()

    # Run chatbot
    run_chatbot_cli(
        session_id=args.session,
        llm_model=args.model,
        checkpointer_type=args.checkpointer
    )


if __name__ == "__main__":
    main()
