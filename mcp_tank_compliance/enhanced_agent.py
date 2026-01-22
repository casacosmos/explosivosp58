#!/usr/bin/env python3
"""
Enhanced LangGraph Agent for Tank Compliance with Excel handling
"""

import asyncio
import os
import json
import pandas as pd
from pathlib import Path
from typing import Annotated, Dict, List, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import streamlit as st
from server import TankComplianceTools

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
        return "Error: No KMZ data found. Please parse a KMZ file first."

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

    return f"Excel file created successfully at: {output_path}\nTotal sites: {len(df)}"

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
        summary = f"Excel file loaded: {excel_path}\n"
        summary += f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
        summary += f"Columns: {', '.join(df.columns.tolist())}\n\n"

        # Show first few rows
        summary += "First 5 rows:\n"
        summary += df.head().to_string()

        return summary
    except Exception as e:
        return f"Error reading Excel file: {str(e)}"

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
        return "Error: No Excel file loaded. Please read an Excel file first."

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
        return f"Successfully modified {column} for {row_identifier} to '{new_value}'"
    except Exception as e:
        return f"Error modifying Excel: {str(e)}"

@tool
async def save_excel_changes(output_path: Optional[str] = None) -> str:
    """
    Save changes made to the Excel file

    Args:
        output_path: Path to save (if None, overwrites original)
    """
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "Error: No Excel file loaded"

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

        return f"Excel file saved successfully to: {save_path}"
    except Exception as e:
        return f"Error saving Excel file: {str(e)}"

@tool
async def add_excel_row(site_name: str, latitude: float, longitude: float, **kwargs) -> str:
    """
    Add a new row to the Excel file

    Args:
        site_name: Name of the site
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        **kwargs: Additional column values
    """
    if 'current_excel' not in st.session_state:
        # Create new DataFrame
        df = pd.DataFrame()
        st.session_state.current_excel = {'data': df, 'path': 'new_file.xlsx'}
    else:
        df = st.session_state.current_excel['data']

    new_row = {
        'Site Name': site_name,
        'Latitude': latitude,
        'Longitude': longitude,
        'Tank Capacity': kwargs.get('tank_capacity', ''),
        'Tank Measurements': kwargs.get('tank_measurements', ''),
        'Underground (Y/N)': kwargs.get('underground', ''),
        'Has Dike (Y/N)': kwargs.get('has_dike', ''),
        'ASDPPU (ft)': kwargs.get('asdppu', ''),
        'ASDBPU (ft)': kwargs.get('asdbpu', ''),
        'Distance to Boundary (ft)': kwargs.get('distance', ''),
        'Compliance Status': kwargs.get('compliance', ''),
        'Notes': kwargs.get('notes', '')
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state.current_excel['data'] = df

    return f"Added new row for site: {site_name}"

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
    summary += "  - Use 'calculate_distances_for_sites' to calculate distances\n"

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
        return "Error: No KMZ data found. Please parse a KMZ file first."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    if not sites:
        return "Error: No sites found"
    if not polygons:
        return "Error: No polygons found"

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
        return "Error: No suitable polygon found"

    # Calculate distances
    polygon_coords = selected_polygon['coordinates']
    distance_results = await tools_instance.batch_calculate_distances(sites, polygon_coords)

    # Format results
    summary = f"Calculated distances using polygon: {selected_polygon['name']}\n\n"

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

# Keep other original tools
@tool
async def parse_tank_measurements(measurement_str: str) -> str:
    """Parse tank measurements (e.g., '39\"x46\"x229\"') and calculate volume in gallons"""
    result = await tools_instance.parse_tank_measurements(measurement_str)
    return str(result)

@tool
async def assess_compliance(distance_feet: float, asd_values: Dict[str, float], has_dike: bool = False) -> str:
    """Assess compliance based on distance and ASD requirements"""
    result = await tools_instance.assess_compliance(distance_feet, asd_values, has_dike)
    return str(result)

# Collect all tools
tank_tools = [
    parse_kmz_file,
    create_excel_from_kmz,
    read_excel_file,
    modify_excel_cell,
    save_excel_changes,
    add_excel_row,
    calculate_distances_for_sites,
    parse_tank_measurements,
    assess_compliance,
]

# State definition
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], "The messages in the conversation"]

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tank_tools)

# Prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant specialized in tank compliance assessment.

IMPORTANT WORKFLOW RULES:
1. When asked to parse a KMZ file, ONLY parse it. Do NOT automatically calculate distances.
2. After parsing a KMZ, wait for the user to request Excel creation or distance calculation.
3. Always confirm what the user wants before proceeding to the next step.

Available tools and their purposes:

FILE PARSING:
- parse_kmz_file: Parse KMZ/KML files to extract sites and polygons (does NOT calculate distances)

EXCEL OPERATIONS:
- create_excel_from_kmz: Create an Excel file from parsed KMZ data
- read_excel_file: Read and display Excel file contents
- modify_excel_cell: Modify specific cells in the Excel file
- save_excel_changes: Save changes made to Excel file
- add_excel_row: Add new rows to Excel file

CALCULATIONS:
- calculate_distances_for_sites: Calculate distances from sites to polygon boundaries
- parse_tank_measurements: Parse tank dimensions and calculate volume
- assess_compliance: Assess compliance based on distances and ASD values

Always be explicit about what action you're taking and wait for user confirmation before moving to the next step."""),
    MessagesPlaceholder(variable_name="messages"),
])

# Agent chain
agent_chain = prompt | llm_with_tools

async def call_model(state: AgentState):
    messages = state["messages"]

    # Convert ToolMessages for compatibility
    llm_messages = []
    for m in messages:
        if isinstance(m, ToolMessage):
            llm_messages.append(HumanMessage(content=f"Tool Result: {m.content}"))
        else:
            llm_messages.append(m)

    response = await agent_chain.ainvoke({"messages": llm_messages})
    return {"messages": [response]}

# Tool node
tool_node = ToolNode(tank_tools)

# Conditional edge
async def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END

# Build graph
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# Compile with checkpointer
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Message formatting
def format_message_for_display(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return message.content
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                args_str = ', '.join(f'{k}={v}' for k, v in tc['args'].items())
                tool_calls.append(f"**{tc['name']}**({args_str})")
            return f"🔧 Using tools: {', '.join(tool_calls)}"
        return message.content
    elif isinstance(message, ToolMessage):
        content = message.content
        if len(content) > 500:
            return f"📊 {content[:500]}..."
        return f"📊 {content}"
    return str(message.content)

# Streamlit Interface
def run_chat_interface():
    st.set_page_config(
        page_title="Tank Compliance Agent",
        page_icon="🏭",
        layout="wide"
    )

    st.title("🏭 Tank Compliance Assessment Agent")
    st.markdown("Enhanced agent with Excel file handling and controlled workflow")

    # Sidebar
    with st.sidebar:
        st.header("📁 Session Data")

        # Show stored KMZ data
        if 'kmz_data' in st.session_state and st.session_state.kmz_data:
            st.success("✅ KMZ data loaded")
            kmz = st.session_state.kmz_data
            st.write(f"Sites: {len(kmz.get('sites', []))}")
            st.write(f"Polygons: {len(kmz.get('polygons', []))}")
        else:
            st.info("No KMZ data loaded")

        # Show current Excel
        if 'current_excel' in st.session_state:
            st.success("✅ Excel file loaded")
            st.write(f"Path: {st.session_state.current_excel.get('path', 'N/A')}")
            if 'data' in st.session_state.current_excel:
                df = st.session_state.current_excel['data']
                st.write(f"Rows: {len(df)}")
        else:
            st.info("No Excel file loaded")

        st.divider()

        if st.button("🔄 Reset Session"):
            for key in ['display_messages', 'kmz_data', 'current_excel', 'thread_id']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        # Tool guide
        st.header("📚 Tool Guide")

        with st.expander("1️⃣ Parse KMZ"):
            st.code('parse_kmz_file("/path/to/file.kmz")')

        with st.expander("2️⃣ Create Excel"):
            st.code('create_excel_from_kmz("output.xlsx", include_distances=True)')

        with st.expander("3️⃣ Modify Excel"):
            st.code('read_excel_file("file.xlsx")')
            st.code('modify_excel_cell("Site Name", "Tank Capacity", "5000")')
            st.code('save_excel_changes()')

    # Initialize session
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"session_{asyncio.get_event_loop().time()}"

    if "display_messages" not in st.session_state:
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        try:
            previous_state = app.get_state(config)
            if previous_state and hasattr(previous_state, 'values'):
                st.session_state.display_messages = previous_state.values.get("messages", [])
            else:
                st.session_state.display_messages = []
        except:
            st.session_state.display_messages = []

    # Display messages
    for message in st.session_state.display_messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user", avatar="👤"):
                st.markdown(format_message_for_display(message))
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(format_message_for_display(message))

    # Chat input
    if user_input := st.chat_input("Enter your command:"):
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        user_message = HumanMessage(content=user_input)
        config = {"configurable": {"thread_id": st.session_state.thread_id}}

        # Process
        with st.spinner("Processing..."):
            all_new_messages = []

            async def process_stream():
                async for chunk in app.astream({"messages": [user_message]}, config=config, stream_mode="values"):
                    if "messages" in chunk and len(chunk["messages"]) > 0:
                        last_msg = chunk["messages"][-1]
                        if not all_new_messages or last_msg != all_new_messages[-1]:
                            all_new_messages.append(last_msg)

            asyncio.run(process_stream())

            # Update messages
            st.session_state.display_messages.append(user_message)
            for msg in all_new_messages:
                if msg != user_message and msg not in st.session_state.display_messages:
                    st.session_state.display_messages.append(msg)

        st.rerun()

    # Example queries
    with st.expander("💡 Example Workflow"):
        st.markdown("""
        1. **Parse KMZ file:**
           ```
           Parse the KMZ file at /path/to/file.kmz
           ```

        2. **Create Excel from KMZ:**
           ```
           Create an Excel file from the KMZ data with distances
           ```

        3. **Read and modify Excel:**
           ```
           Read the Excel file tank_data.xlsx
           Modify the Tank Capacity for "Site Name" to "5000"
           Save the changes
           ```
        """)

if __name__ == "__main__":
    run_chat_interface()