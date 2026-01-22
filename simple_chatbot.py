#!/usr/bin/env python3
"""
Simple Pipeline Chatbot - Conversational interface for tank processing
No complex session management - just execute the pipeline steps conversationally
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime

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
from pipeline_agent import run_pipeline_agent


# ============================================================================
# SIMPLE CHATBOT STATE
# ============================================================================

class SimpleChatbotState(TypedDict):
    """Simple state - just messages and current file being processed."""
    messages: Annotated[List[BaseMessage], add_messages]
    current_file: Optional[str]
    output_dir: str


# ============================================================================
# SIMPLE TOOLS
# ============================================================================

@tool
def process_file_tool(file_path: str) -> Dict[str, Any]:
    """
    Process a KMZ or Excel file through the complete pipeline.

    This will:
    1. Parse the file (KMZ → Excel template, or validate Excel)
    2. Convert measurements to volumes and create JSON
    3. Use HUD tool with Playwright to retrieve data + screenshots
    4. Update Excel with HUD results
    5. Determine compliance
    6. Create output KMZ with tank locations labeled by capacities

    Args:
        file_path: Path to KMZ or Excel file

    Returns:
        Processing results with paths to generated files
    """
    try:
        # Validate file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        # Create output directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("outputs") / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run the complete pipeline
        result = run_pipeline_agent(
            input_file=str(file_path_obj.resolve()),
            output_dir=str(output_dir),
            session_id=timestamp,
            config={"use_improved_parser": True},
            stream_progress=True
        )

        if result.get("status") == "completed":
            return {
                "success": True,
                "message": "Pipeline completed successfully!",
                "output_dir": str(output_dir),
                "artifacts": {
                    "json": str(output_dir / "tank_config.json"),
                    "hud_results": str(output_dir / "fast_results.json"),
                    "hud_pdf": str(output_dir / "HUD_ASD_Results.pdf"),
                    "excel": str(output_dir / "with_hud.xlsx"),
                    "compliance": str(output_dir / "final_compliance.xlsx"),
                    "output_kmz": str(output_dir / "tanks_with_labels.kmz")
                },
                "tank_count": result.get("tank_count", 0)
            }
        else:
            return {
                "success": False,
                "error": f"Pipeline failed: {result.get('error', 'Unknown error')}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing file: {str(e)}"
        }


@tool
def fill_tank_data_tool(
    excel_path: str,
    tank_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Fill Excel template with tank data provided conversationally.

    Use this when user provides tank information like:
    "Tank T-01 has capacity 50000 gallons, dimensions 30ft x 20ft x 15ft, stores Diesel"

    Args:
        excel_path: Path to Excel template (from KMZ parsing)
        tank_data: List of tank info dicts with keys: tank_id, capacity, length, width, height, product

    Returns:
        Success status and count of filled tanks
    """
    try:
        import pandas as pd
        import re

        # Read Excel
        df = pd.read_excel(excel_path)
        filled_count = 0

        for tank_info in tank_data:
            tank_id = tank_info.get("tank_id")

            # Find row for this tank
            tank_row = df[df.iloc[:, 0].astype(str).str.contains(str(tank_id), case=False, na=False)]

            if not tank_row.empty:
                idx = tank_row.index[0]

                # Fill capacity
                if "capacity" in tank_info:
                    capacity_match = re.search(r'([\d,\.]+)', str(tank_info["capacity"]))
                    if capacity_match:
                        df.at[idx, "Tank Capacity"] = str(capacity_match.group(1))

                # Fill dimensions
                measurements = []
                for dim in ["length", "width", "height"]:
                    if dim in tank_info:
                        measurements.append(str(tank_info[dim]))

                if measurements:
                    dim_cols = [col for col in df.columns if "dimension" in col.lower() or "measurement" in col.lower()]
                    if dim_cols:
                        df.at[idx, dim_cols[0]] = " x ".join(measurements)

                # Fill product
                if "product" in tank_info:
                    product_cols = [col for col in df.columns if "product" in col.lower() or "material" in col.lower()]
                    if product_cols:
                        df.at[idx, product_cols[0]] = str(tank_info["product"])

                filled_count += 1

        # Save
        df.to_excel(excel_path, index=False)

        return {
            "success": True,
            "tanks_filled": filled_count,
            "excel_path": excel_path,
            "message": f"Filled {filled_count} tanks in Excel template"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error filling Excel: {str(e)}"
        }


@tool
def create_template_tool(tank_count: int, output_path: str = "tank_template.xlsx") -> Dict[str, Any]:
    """
    Create a blank Excel template for tank data entry.

    Use this when user asks to create a template without providing a KMZ file.

    Args:
        tank_count: Number of tank rows to create
        output_path: Where to save the template

    Returns:
        Path to created template
    """
    try:
        import pandas as pd

        # Create template structure
        data = {
            "Tank ID": [f"T-{i+1:02d}" for i in range(tank_count)],
            "Tank Capacity": [""] * tank_count,
            "Tank Dimensions": [""] * tank_count,
            "Product Stored": [""] * tank_count,
            "Longitude": [""] * tank_count,
            "Latitude": [""] * tank_count
        }

        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False)

        return {
            "success": True,
            "template_path": output_path,
            "tank_count": tank_count,
            "message": f"Created template with {tank_count} tank rows at {output_path}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating template: {str(e)}"
        }


@tool
def help_tool() -> Dict[str, Any]:
    """Get help about what the chatbot can do."""
    help_text = """
🤖 Tank Processing Pipeline Chatbot

**What I can do:**
1. Process KMZ files - extracts tank locations and creates Excel template
2. Process Excel files - validates and runs compliance analysis
3. Create blank templates - for manual data entry
4. Fill data conversationally - you tell me tank info, I fill the Excel

**Complete Pipeline Steps:**
1. Parse KMZ/Excel → Create/validate structure
2. Convert measurements → Calculate volumes → Generate JSON
3. Use JSON with HUD tool (Playwright) → Retrieve HUD data + screenshots
4. Update Excel with HUD results
5. Determine compliance (YES/NO/REVIEW)
6. Create output KMZ with tanks labeled by capacities

**Example Usage:**
- "Process tanks.kmz"
- "Create a template for 24 tanks"
- "Tank T-01 has 50000 gallons capacity, 30ft x 20ft x 15ft, stores Diesel"
- "Process tanks.xlsx"

Just tell me what you need! 🚀
"""
    return {"success": True, "message": help_text}


# ============================================================================
# CHATBOT GRAPH
# ============================================================================

def create_simple_chatbot() -> StateGraph:
    """Create the simple chatbot graph."""

    # Initialize LLM
    llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

    # Define tools
    tools = [
        process_file_tool,
        fill_tank_data_tool,
        create_template_tool,
        help_tool
    ]

    llm_with_tools = llm.bind_tools(tools)

    # Define chatbot node
    def chatbot_node(state: SimpleChatbotState) -> SimpleChatbotState:
        """Main chatbot logic."""
        system_message = SystemMessage(content="""You are a helpful assistant for tank processing and compliance analysis.

Your job is to help users:
1. Process KMZ or Excel files containing tank data
2. Fill Excel templates conversationally when users provide tank information
3. Create blank templates when needed
4. Guide users through the pipeline workflow

The pipeline automatically:
- Converts measurements to volumes
- Creates structured JSON
- Uses HUD tool with Playwright to retrieve data and take screenshots
- Updates Excel with HUD results
- Determines compliance
- Creates output KMZ with tank locations labeled by capacities

When users provide tank data like "Tank T-01 has 50000 gallons, 30x20x15 ft, stores Diesel",
extract the structured information and use fill_tank_data_tool.

When users say "process [file]", use process_file_tool.
When users ask for a template, use create_template_tool.

Be conversational and helpful!""")

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


# ============================================================================
# MAIN INTERFACE
# ============================================================================

def run_chatbot():
    """Run the interactive chatbot."""
    print("=" * 70)
    print("🤖 Tank Processing Pipeline Chatbot")
    print("=" * 70)
    print()
    print("Type 'help' for instructions, 'quit' to exit")
    print()

    # Create graph
    graph_builder = create_simple_chatbot()
    checkpointer = MemorySaver()
    graph = graph_builder.compile(checkpointer=checkpointer)

    # Conversation config
    config = {"configurable": {"thread_id": "main_conversation"}}

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\nGoodbye! 👋")
                break

            # Create message
            state = {
                "messages": [HumanMessage(content=user_input)],
                "current_file": None,
                "output_dir": "outputs"
            }

            # Stream response
            print("\nBot: ", end="", flush=True)

            for event in graph.stream(state, config, stream_mode="values"):
                if "messages" in event:
                    last_message = event["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        # Print only new content
                        if hasattr(last_message, 'content') and last_message.content:
                            print(last_message.content)

            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_chatbot()
