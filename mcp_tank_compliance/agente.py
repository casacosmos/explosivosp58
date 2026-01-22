#!/usr/bin/env python3
"""
Refactored LangGraph ReAct Agent for Tank Compliance Tools with Chat Interface and Persistence

This script ensures proper chat history continuity by:
- Loading the full thread state from the checkpointer at the start of each run to display current history.
- Using a session-specific thread_id via st.session_state (fixed to a unique value per browser session).
- Appending only the new user message to the input_state for invocations, allowing the checkpointer to merge with existing history.
- Updating st.session_state.messages after each interaction by re-loading from checkpointer to reflect the full state.
- This maintains ReAct behavior with persistence across turns within the same session.
"""

import asyncio
import os
import hashlib
import pandas as pd
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import streamlit as st
from server import TankComplianceTools  # Import from the provided server.py

# Initialize the tools class
tools_instance = TankComplianceTools()

# Store parsed KMZ data in session state for later use
def store_kmz_data(data: Dict):
    """Store KMZ data in session state"""
    if 'kmz_data' not in st.session_state:
        st.session_state.kmz_data = {}
    st.session_state.kmz_data = data

def get_kmz_data() -> Dict:
    """Get stored KMZ data"""
    return st.session_state.get('kmz_data', {})

# Excel handling tools
@tool
async def create_excel_from_kmz(output_path: str = "tank_compliance.xlsx", include_distances: bool = False) -> str:
    """
    Create an Excel file from the previously parsed KMZ data.
    Use this AFTER parsing a KMZ file.

    Args:
        output_path: Path for the Excel file
        include_distances: Whether to calculate distances (requires polygon data)
    """
    kmz_data = get_kmz_data()
    if not kmz_data:
        return "Error: No KMZ data found. Please parse a KMZ file first using parse_kmz_file."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    if not sites:
        return "Error: No sites found in KMZ data"

    # Create DataFrame
    excel_data = []
    for site in sites:
        row = {
            'Site Name': site['name'],
            'Latitude': site['latitude'],
            'Longitude': site['longitude'],
            'Tank Capacity': '',
            'Tank Measurements': '',
            'Underground (Y/N)': '',
            'Has Dike (Y/N)': '',
            'ASDPPU (ft)': '',
            'ASDBPU (ft)': '',
            'Distance to Boundary (ft)': '',
            'Compliance Status': '',
            'Notes': ''
        }
        excel_data.append(row)

    # Calculate distances if requested and polygon available
    if include_distances and polygons:
        main_polygon = None
        for polygon in polygons:
            if 'Buffer' not in polygon['name']:
                main_polygon = polygon
                break

        if main_polygon:
            # Calculate distances
            polygon_coords = main_polygon['coordinates']
            distance_results = await tools_instance.batch_calculate_distances(sites, polygon_coords)

            # Add distances to Excel data
            distance_map = {}
            if isinstance(distance_results, list):
                for result in distance_results:
                    if 'name' in result and 'distance_feet' in result:
                        distance_map[result['name']] = result['distance_feet']

            for row in excel_data:
                if row['Site Name'] in distance_map:
                    row['Distance to Boundary (ft)'] = distance_map[row['Site Name']]

    # Create Excel file
    df = pd.DataFrame(excel_data)
    df = df.sort_values('Site Name')

    # Ensure output path is absolute
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.getcwd(), output_path)

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    # Write Excel with formatting
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tank Compliance', index=False)

        # Format the Excel file
        workbook = writer.book
        worksheet = writer.sheets['Tank Compliance']

        # Set column widths
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)

    return f"✅ Excel file created successfully at: {output_path}\nTotal sites: {len(df)}"

@tool
async def read_excel_file(excel_path: str, sheet_name: Optional[str] = None) -> str:
    """
    Read an Excel file and display its contents

    Args:
        excel_path: Path to the Excel file
        sheet_name: Specific sheet to read (default: first sheet)
    """
    try:
        if sheet_name:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(excel_path)

        # Store in session for modification
        if 'current_excel' not in st.session_state:
            st.session_state.current_excel = {}
        st.session_state.current_excel['path'] = excel_path
        st.session_state.current_excel['data'] = df

        # Create summary
        summary = f"📊 Excel file loaded: {excel_path}\n"
        summary += f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
        summary += f"Columns: {', '.join(df.columns.tolist())}\n\n"

        # Show first few rows
        summary += "First 5 rows:\n"
        summary += df.head().to_string()

        return summary
    except Exception as e:
        return f"❌ Error reading Excel file: {str(e)}"

@tool
async def modify_excel_cell(row_identifier: str, column: str, new_value: str) -> str:
    """
    Modify a specific cell in the currently loaded Excel file

    Args:
        row_identifier: Site name or row index (0-based)
        column: Column name
        new_value: New value for the cell
    """
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "❌ Error: No Excel file loaded. Please read an Excel file first using read_excel_file."

    df = st.session_state.current_excel['data']

    try:
        # Try to find by site name first
        if 'Site Name' in df.columns:
            mask = df['Site Name'] == row_identifier
            if mask.any():
                df.loc[mask, column] = new_value
            else:
                # Try as index
                row_idx = int(row_identifier)
                df.at[row_idx, column] = new_value
        else:
            # Use as index
            row_idx = int(row_identifier)
            df.at[row_idx, column] = new_value

        st.session_state.current_excel['data'] = df
        return f"✅ Successfully modified {column} for {row_identifier} to '{new_value}'"
    except Exception as e:
        return f"❌ Error modifying Excel: {str(e)}"

@tool
async def save_excel_changes(output_path: Optional[str] = None) -> str:
    """
    Save changes made to the Excel file

    Args:
        output_path: Path to save (if None, overwrites original)
    """
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "❌ Error: No Excel file loaded"

    df = st.session_state.current_excel['data']
    save_path = output_path or st.session_state.current_excel['path']

    try:
        with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tank Compliance', index=False)

            # Format
            workbook = writer.book
            worksheet = writer.sheets['Tank Compliance']

            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)

        return f"✅ Excel file saved successfully to: {save_path}"
    except Exception as e:
        return f"❌ Error saving Excel file: {str(e)}"

# Original tools with modifications
@tool
async def parse_kmz_file(kmz_path: str) -> str:
    """
    Parse KMZ/KML file to extract site locations and polygon boundaries.
    This only parses the file, it does NOT automatically calculate distances.
    Use 'create_excel_from_kmz' after this to create an Excel file.
    """
    result = await tools_instance.parse_kmz_file(kmz_path)

    # Store the parsed data
    store_kmz_data(result)

    # Return summary without triggering distance calculation
    summary = f"✅ Successfully parsed KMZ file: {kmz_path}\n\n"
    summary += f"Found {result['count']} sites:\n"
    for site in result['sites'][:5]:  # Show first 5 sites
        summary += f"  • {site['name']}\n"
    if result['count'] > 5:
        summary += f"  ... and {result['count'] - 5} more sites\n"

    summary += f"\nFound {len(result.get('polygons', []))} polygon(s):\n"
    for polygon in result.get('polygons', []):
        summary += f"  • {polygon['name']}\n"

    summary += "\n💡 Next steps:\n"
    summary += "  - Use 'create_excel_from_kmz' to create an Excel file\n"
    summary += "  - Use 'calculate_distances_for_sites' if you need distances\n"

    return summary

@tool
async def calculate_distances_for_sites(polygon_name: Optional[str] = None) -> str:
    """
    Calculate distances from parsed sites to polygon boundary.
    This should be used AFTER parsing a KMZ file.

    Args:
        polygon_name: Name of polygon to use (if None, uses first non-buffer polygon)
    """
    kmz_data = get_kmz_data()
    if not kmz_data:
        return "❌ Error: No KMZ data found. Please parse a KMZ file first using parse_kmz_file."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    if not sites:
        return "❌ Error: No sites found"
    if not polygons:
        return "❌ Error: No polygons found"

    # Find the polygon to use
    selected_polygon = None
    if polygon_name:
        for p in polygons:
            if polygon_name.lower() in p['name'].lower():
                selected_polygon = p
                break
    else:
        # Use first non-buffer polygon
        for p in polygons:
            if 'Buffer' not in p['name']:
                selected_polygon = p
                break

    if not selected_polygon and polygons:
        selected_polygon = polygons[0]

    if not selected_polygon:
        return "❌ Error: No suitable polygon found"

    # Calculate distances
    polygon_coords = selected_polygon['coordinates']
    distance_results = await tools_instance.batch_calculate_distances(sites, polygon_coords)

    # Format results
    summary = f"📏 Calculated distances using polygon: {selected_polygon['name']}\n\n"

    if isinstance(distance_results, list):
        # Show statistics
        distances = [r['distance_feet'] for r in distance_results if 'distance_feet' in r]
        if distances:
            summary += f"Distance Statistics:\n"
            summary += f"  • Minimum: {min(distances):.1f} ft\n"
            summary += f"  • Maximum: {max(distances):.1f} ft\n"
            summary += f"  • Average: {sum(distances)/len(distances):.1f} ft\n\n"

        # Show first few results
        summary += "Site distances:\n"
        for result in distance_results[:5]:
            summary += f"  • {result['name']}: {result.get('distance_feet', 'N/A'):.1f} ft\n"
        if len(distance_results) > 5:
            summary += f"  ... and {len(distance_results) - 5} more sites\n"

    return summary

@tool
async def parse_tank_measurements(measurement_str: str) -> str:
    """Parse tank measurements (e.g., '39\"x46\"x229\"') and calculate volume in gallons"""
    result = await tools_instance.parse_tank_measurements(measurement_str)
    return str(result)

@tool
async def parse_multi_tank_capacities(capacity_str: str) -> str:
    """Parse capacity string with multiple tanks and identify largest for compliance"""
    result = await tools_instance.parse_multi_tank_capacities(capacity_str)
    return str(result)

@tool
async def extract_asd_values(asd_string: str) -> str:
    """Extract ASDPPU and ASDBPU values from ASD calculation string"""
    result = await tools_instance.extract_asd_values(asd_string)
    return str(result)

@tool
async def assess_compliance(distance_feet: float, asd_values: Dict[str, float], has_dike: bool = False) -> str:
    """Assess compliance based on distance and ASD requirements"""
    result = await tools_instance.assess_compliance(distance_feet, asd_values, has_dike)
    return str(result)

@tool
async def process_excel_compliance(excel_path: str, polygon_coords: List[List[float]]) -> str:
    """Process entire Excel file for comprehensive compliance assessment"""
    result = await tools_instance.process_excel_compliance(excel_path, polygon_coords)
    return str(result)

@tool
async def create_kmz_file(sites: List[Dict[str, Any]], polygons: List[Dict[str, Any]], output_path: str = "output.kmz") -> str:
    """Create KMZ file with sites, polygons, and compliance visualization"""
    result = await tools_instance.create_kmz_file(sites, polygons, output_path)
    return str(result)

@tool
async def update_excel_with_results(excel_path: str, results: List[Dict[str, Any]], output_path: str = None) -> str:
    """Update Excel file with calculated distances and compliance results"""
    if output_path is None:
        output_path = excel_path
    result = await tools_instance.update_excel_with_results(excel_path, results, output_path)
    return str(result)

# Define all tools
tank_tools = [
    parse_kmz_file,
    create_excel_from_kmz,
    read_excel_file,
    modify_excel_cell,
    save_excel_changes,
    calculate_distances_for_sites,
    parse_tank_measurements,
    parse_multi_tank_capacities,
    extract_asd_values,
    assess_compliance,
    process_excel_compliance,
    create_kmz_file,
    update_excel_with_results,
]

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# System prompt as a string for the 'prompt' parameter
system_content = """You are a helpful assistant specialized in tank compliance assessment.

IMPORTANT WORKFLOW RULES:
1. When asked to parse a KMZ file, ONLY parse it. Do NOT automatically calculate distances.
2. After parsing a KMZ, wait for the user to request Excel creation or distance calculation.
3. Always confirm what the user wants before proceeding to the next step.

Available tools and their purposes:

FILE PARSING:
- parse_kmz_file: Parse KMZ/KML files to extract sites and polygons (does NOT calculate distances)

EXCEL OPERATIONS:
- create_excel_from_kmz: Create an Excel file from parsed KMZ data (can optionally include distances)
- read_excel_file: Read and display Excel file contents
- modify_excel_cell: Modify specific cells in the Excel file
- save_excel_changes: Save changes made to Excel file

CALCULATIONS:
- calculate_distances_for_sites: Calculate distances from sites to polygon boundaries
- parse_tank_measurements: Parse tank dimensions and calculate volume
- parse_multi_tank_capacities: Parse multiple tank capacities
- extract_asd_values: Extract ASD values from strings
- assess_compliance: Assess compliance based on distances and ASD values

FILE GENERATION:
- create_kmz_file: Create KMZ with visualization
- update_excel_with_results: Update Excel with results
- process_excel_compliance: Process entire Excel for compliance

Always be explicit about what action you're taking and provide clear status updates."""

# Create the prebuilt ReAct agent
checkpointer = MemorySaver()
app = create_react_agent(
    llm,
    tank_tools,
    prompt=system_content,
    checkpointer=checkpointer
)

# Helper function to get display content from BaseMessage
def get_display_content(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return message.content
    elif isinstance(message, AIMessage):
        # Format tool calls nicely
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_info = []
            for tc in message.tool_calls:
                args = ', '.join(f"{k}={v}" for k, v in tc.get('args', {}).items())
                tool_info.append(f"**{tc.get('name', 'unknown')}**({args})")

            if message.content:
                return f"{message.content}\n\n🔧 Using tools: {', '.join(tool_info)}"
            else:
                return f"🔧 Using tools: {', '.join(tool_info)}"
        return message.content if message.content else ""
    elif isinstance(message, ToolMessage):
        # Format tool results
        content = message.content
        if len(content) > 1000:
            return f"📊 Tool result:\n{content[:1000]}..."
        return f"📊 Tool result:\n{content}"
    return str(message.content) if hasattr(message, 'content') else str(message)

# Streamlit Chat Interface
def run_chat_interface():
    st.set_page_config(
        page_title="Tank Compliance Assessment Agent",
        page_icon="🏭",
        layout="wide"
    )

    st.title("🏭 Tank Compliance Assessment Agent")
    st.markdown("Interact with the agent to perform compliance assessments using the available tools.")

    # Sidebar for session info and tools
    with st.sidebar:
        st.header("📊 Session Information")

        # Show KMZ data if loaded
        if 'kmz_data' in st.session_state and st.session_state.kmz_data:
            st.success("✅ KMZ Data Loaded")
            kmz = st.session_state.kmz_data
            st.write(f"• Sites: {len(kmz.get('sites', []))}")
            st.write(f"• Polygons: {len(kmz.get('polygons', []))}")
        else:
            st.info("No KMZ data loaded yet")

        # Show Excel data if loaded
        if 'current_excel' in st.session_state and 'data' in st.session_state.current_excel:
            st.success("✅ Excel File Loaded")
            st.write(f"• Path: {st.session_state.current_excel.get('path', 'N/A')}")
            df = st.session_state.current_excel['data']
            st.write(f"• Rows: {len(df)}")
        else:
            st.info("No Excel file loaded yet")

        st.divider()

        # Reset button
        if st.button("🔄 Reset Session", type="secondary"):
            for key in ['messages', 'kmz_data', 'current_excel', 'thread_id']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        # Tool documentation
        st.header("📚 Available Tools")

        with st.expander("📍 File Parsing"):
            st.markdown("""
            - **parse_kmz_file**: Parse KMZ/KML files
            - **read_excel_file**: Read Excel files
            """)

        with st.expander("📊 Excel Operations"):
            st.markdown("""
            - **create_excel_from_kmz**: Create Excel from KMZ
            - **modify_excel_cell**: Edit Excel cells
            - **save_excel_changes**: Save changes
            """)

        with st.expander("📏 Calculations"):
            st.markdown("""
            - **calculate_distances_for_sites**: Calculate distances
            - **parse_tank_measurements**: Parse tank dimensions
            - **assess_compliance**: Check compliance
            """)

        # Example queries
        with st.expander("💡 Example Queries"):
            st.markdown("""
            1. Parse the KMZ file at /path/to/file.kmz
            2. Create an Excel file from the KMZ data
            3. Calculate distances to polygon boundaries
            4. Read the Excel file tank_data.xlsx
            5. Modify Tank Capacity for "Site Name" to "5000"
            """)

    # Initialize session-specific thread_id (unique per browser session)
    if "thread_id" not in st.session_state:
        # Use a hash for uniqueness if multiple tabs/sessions
        session_hash = hashlib.md5(str(id(st.session_state)).encode()).hexdigest()[:8]
        st.session_state.thread_id = f"tank_compliance_session_{session_hash}"

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # Always load current messages from checkpointer for display
    if "messages" not in st.session_state:
        try:
            current_state = app.get_state(config)
            st.session_state.messages = current_state.values.get("messages", []) if current_state and hasattr(current_state, 'values') else []
        except:
            st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user", avatar="👤"):
                st.markdown(get_display_content(message))
        elif isinstance(message, (AIMessage, ToolMessage)):
            with st.chat_message("assistant", avatar="🤖"):
                content = get_display_content(message)
                if content:  # Only display if there's content
                    st.markdown(content)

    # Chat input
    if user_input := st.chat_input("Enter your query about tank compliance:"):
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Generate assistant response
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            full_response = ""

            # Stream the ReAct agent asynchronously
            async def stream_agent():
                nonlocal full_response
                input_state = {"messages": [HumanMessage(content=user_input)]}

                try:
                    async for chunk in app.astream(input_state, config=config):
                        for key, value in chunk.items():
                            if 'messages' in value:
                                for new_msg in value['messages']:
                                    display_content = get_display_content(new_msg)
                                    if display_content:  # Only add if there's content
                                        full_response = display_content
                                        placeholder.markdown(full_response)
                        await asyncio.sleep(0.01)
                except Exception as e:
                    full_response = f"❌ Error: {str(e)}"
                    placeholder.markdown(full_response)

            asyncio.run(stream_agent())

        # Re-load updated messages from checkpointer after response
        try:
            current_state = app.get_state(config)
            if current_state and hasattr(current_state, 'values'):
                st.session_state.messages = current_state.values.get("messages", [])
        except:
            pass

        # Force rerun to update the UI with new messages
        st.rerun()

if __name__ == "__main__":
    # Run Streamlit
    run_chat_interface()
    # To run: streamlit run agente.py