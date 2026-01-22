#!/usr/bin/env python3
"""
Compliance Agent
Specialized agent for calculating tank volumes, running HUD compliance checks, 
validating data, and generating reports.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime

# LangGraph imports
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import ToolNode, tools_condition

# Local imports
from volume_calculator import VolumeCalculator

# ============================================================================ 
# STATE DEFINITION
# ============================================================================ 

class ComplianceState(TypedDict):
    """State for the compliance agent execution"""
    messages: Annotated[List[BaseMessage], add_messages]
    input_file: Optional[str]
    output_dir: str
    session_id: str
    config: Dict[str, Any]
    tank_config_json: Optional[str]
    hud_results_json: Optional[str]
    pdf_report: Optional[str]
    compliance_excel: Optional[str]

# ============================================================================ 
# TOOL DEFINITIONS
# ============================================================================ 

@tool
def excel_to_json_tool(
    excel_path: str,
    output_json: str,
    use_improved: bool = True
) -> Dict[str, Any]:
    """
    Convert Excel/CSV to tank configuration JSON.

    Args:
        excel_path: Path to Excel or CSV file
        output_json: Output path for JSON file
        use_improved: Use improved parser with VolumeCalculator

    Returns:
        Dictionary with JSON path, tank count, and volume sources
    """
    try:
        script = "excel_to_json_improved.py" if use_improved else "excel_to_json_langgraph.py"

        cmd = [
            "python", script,
            excel_path,
            "-o", output_json
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Excel to JSON conversion failed: {result.stderr}",
                "json_path": None,
                "tank_count": 0
            }

        # Parse the generated JSON to get stats
        if Path(output_json).exists():
            with open(output_json, 'r') as f:
                data = json.load(f)
                tank_count = len(data.get('tanks', []))

                # Analyze volume sources
                volume_sources = {}
                for tank in data.get('tanks', []):
                    src = tank.get('volume_source', 'unknown')
                    volume_sources[src] = volume_sources.get(src, 0) + 1
        else:
            return {
                "success": False,
                "error": "JSON file not created",
                "json_path": None,
                "tank_count": 0
            }

        return {
            "success": True,
            "json_path": output_json,
            "tank_count": tank_count,
            "volume_sources": volume_sources,
            "message": f"Converted {tank_count} tanks to JSON"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Excel to JSON exception: {str(e)}",
            "json_path": None,
            "tank_count": 0
        }


@tool
def validate_json_tool(json_path: str) -> Dict[str, Any]:
    """
    Validate tank configuration JSON structure.

    Args:
        json_path: Path to JSON file to validate

    Returns:
        Dictionary with validation result
    """
    try:
        cmd = ["python", "validate_tank_json.py", json_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        return {
            "success": result.returncode == 0,
            "message": "Validation passed" if result.returncode == 0 else "Validation failed",
            "details": result.stdout if result.returncode == 0 else result.stderr
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Validation exception: {str(e)}"
        }


@tool
def process_hud_tool(config_json: str, output_dir: str) -> Dict[str, Any]:
    """
    Run HUD ASD calculations for all tanks using Playwright automation.

    Args:
        config_json: Path to tank configuration JSON
        output_dir: Directory for output files

    Returns:
        Dictionary with results path and processing stats
    """
    try:
        cmd = [
            "python", "fast_hud_processor.py",
            "--config", config_json
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2 hour timeout

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"HUD processing failed: {result.stderr}",
                "results": None
            }

        # Look for fast_results.json
        results_file = Path("fast_results.json")
        if results_file.exists():
            # Move to output directory
            output_file = Path(output_dir) / "fast_results.json"
            import shutil
            shutil.move(str(results_file), str(output_file))

            with open(output_file, 'r') as f:
                results = json.load(f)
                processed_count = len(results)
        else:
            return {
                "success": False,
                "error": "HUD results file not created",
                "results": None
            }

        return {
            "success": True,
            "results": str(output_file),
            "processed_count": processed_count,
            "screenshots_dir": ".playwright-mcp",
            "message": f"Processed {processed_count} tanks"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"HUD processing exception: {str(e)}",
            "results": None
        }


@tool
def generate_pdf_tool(output_dir: str, pdf_name: str = "HUD_ASD_Results.pdf") -> Dict[str, Any]:
    """
    Generate PDF report from HUD calculation screenshots.

    Args:
        output_dir: Directory for output PDF
        pdf_name: Name of output PDF file

    Returns:
        Dictionary with PDF path
    """
    try:
        output_pdf = Path(output_dir) / pdf_name

        cmd = [
            "python", "generate_pdf.py",
            "-d", ".playwright-mcp",
            "-o", str(output_pdf),
            "--summary"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"PDF generation failed: {result.stderr}",
                "pdf_path": None
            }

        return {
            "success": True,
            "pdf_path": str(output_pdf),
            "message": f"PDF generated: {output_pdf.name}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF generation exception: {str(e)}",
            "pdf_path": None
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
def calculate_volume_tool(
    length: float,
    width: float,
    height: float,
    unit: str = "ft"
) -> Dict[str, Any]:
    """
    Calculate tank volume from dimensions using VolumeCalculator.

    Args:
        length: Tank length
        width: Tank width
        height: Tank height
        unit: Unit of measurement

    Returns:
        Dictionary with volume in gallons
    """
    try:
        calc = VolumeCalculator(debug=False)
        volume = calc.compute_from_tuple(length, width, height, unit)

        if volume is None:
            return {
                "success": False,
                "error": "Invalid dimensions or volume calculation failed",
                "volume_gallons": None
            }

        return {
            "success": True,
            "volume_gallons": volume,
            "message": f"Calculated volume: {volume:.2f} gallons"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Volume calculation exception: {str(e)}",
            "volume_gallons": None
        }


@tool
def check_compliance_tool(
    excel_path: str,
    output_path: str,
    distances_json: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check compliance by comparing actual distances to required ASD values.

    Args:
        excel_path: Path to Excel with HUD results
        output_path: Path for compliance report Excel
        distances_json: Optional path to distances JSON

    Returns:
        Dictionary with compliance statistics
    """
    try:
        cmd = [
            "python", "compliance_checker.py",
            excel_path
        ]

        if distances_json:
            cmd.extend(["--distances", distances_json])
        else:
            cmd.append("--no-distances")

        cmd.extend(["-o", output_path])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Compliance check failed: {result.stderr}",
                "compliance_excel": None
            }

        return {
            "success": True,
            "compliance_excel": output_path,
            "message": "Compliance report generated"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Compliance check exception: {str(e)}",
            "compliance_excel": None
        }

# ============================================================================ 
# CHATBOT INTERFACE
# ============================================================================ 

def run_compliance_chatbot():
    """Run the compliance agent in interactive chatbot mode."""
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║             Compliance & Calculation Agent                    ║
╠════════════════════════════════════════════════════════════════╣
║  I specialize in tank volume calculations, HUD compliance,    ║
║  and generating regulatory reports.                           ║
║                                                                ║
║  Capabilities:                                                ║
║    • Calculate tank volumes                                   ║
║    • Run HUD ASD checks                                       ║
║    • Generate Compliance PDF/Excel                            ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Initialize LLM
    llm = init_chat_model(model_name="gpt-4o")

    # Bind tools to LLM
    tools = [
        calculate_volume_tool,
        check_compliance_tool,
        generate_pdf_tool,
        update_excel_tool,
        process_hud_tool,
        validate_json_tool,
        excel_to_json_tool
    ]

    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    # Build graph
    graph = StateGraph(ComplianceState)
    graph.add_node("agent", lambda state: {"messages": [llm_with_tools.invoke(state["messages"])[-1]]})
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    # Compile
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)

    # State
    state = {
        "messages": [
            AIMessage(content="I am the Compliance Agent. I can help with volume calculations, HUD ASD checks, and compliance reporting. Upload an Excel file or ask me to calculate a volume.")
        ],
        "output_dir": "outputs",
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "config": {}
    }

    # Loop
    while True:
        try:
            user_input = input("\n🛡️ Compliance Agent: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break
            
            state["messages"].append(HumanMessage(content=user_input))
            config = {"configurable": {"thread_id": state["session_id"]}}
            result = app.invoke(state, config)
            
            last_msg = result["messages"][-1]
            if hasattr(last_msg, "content"):
                print(f"\n🤖: {last_msg.content}")
            
            state = result
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_compliance_chatbot()
