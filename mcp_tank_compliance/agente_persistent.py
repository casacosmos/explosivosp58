#!/usr/bin/env python3
"""
Tank Compliance Agent with Persistent Chat History

This version properly persists chat history across Streamlit restarts using:
- File-based storage for messages
- Pickle for serialization
- Session recovery on startup
"""

import asyncio
import os
import hashlib
import pandas as pd
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import streamlit as st
from server import TankComplianceTools

# Create a persistent storage directory
STORAGE_DIR = Path.home() / ".tank_compliance_agent"
STORAGE_DIR.mkdir(exist_ok=True)

# Initialize the tools class
tools_instance = TankComplianceTools()

# Session persistence functions
def get_session_file(session_id: str) -> Path:
    """Get the file path for a session's data"""
    return STORAGE_DIR / f"session_{session_id}.pkl"

def save_session_data(session_id: str, messages: List, kmz_data: Dict = None, excel_data: Dict = None):
    """Save session data to disk"""
    session_file = get_session_file(session_id)

    # Convert messages to serializable format
    serializable_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            serializable_messages.append({
                'type': 'human',
                'content': msg.content
            })
        elif isinstance(msg, AIMessage):
            serializable_messages.append({
                'type': 'ai',
                'content': msg.content,
                'tool_calls': getattr(msg, 'tool_calls', [])
            })
        elif isinstance(msg, ToolMessage):
            serializable_messages.append({
                'type': 'tool',
                'content': msg.content,
                'tool_name': getattr(msg, 'name', 'unknown')
            })

    session_data = {
        'messages': serializable_messages,
        'kmz_data': kmz_data,
        'excel_data': excel_data,
        'timestamp': datetime.now().isoformat()
    }

    with open(session_file, 'wb') as f:
        pickle.dump(session_data, f)

def load_session_data(session_id: str) -> Dict:
    """Load session data from disk"""
    session_file = get_session_file(session_id)

    if not session_file.exists():
        return {'messages': [], 'kmz_data': None, 'excel_data': None}

    try:
        with open(session_file, 'rb') as f:
            session_data = pickle.load(f)

        # Reconstruct message objects
        messages = []
        for msg_data in session_data.get('messages', []):
            if msg_data['type'] == 'human':
                messages.append(HumanMessage(content=msg_data['content']))
            elif msg_data['type'] == 'ai':
                msg = AIMessage(content=msg_data['content'])
                if 'tool_calls' in msg_data:
                    msg.tool_calls = msg_data['tool_calls']
                messages.append(msg)
            elif msg_data['type'] == 'tool':
                messages.append(ToolMessage(
                    content=msg_data['content'],
                    tool_call_id="restored",  # Required field for ToolMessage
                    name=msg_data.get('tool_name', 'unknown')
                ))

        return {
            'messages': messages,
            'kmz_data': session_data.get('kmz_data'),
            'excel_data': session_data.get('excel_data')
        }
    except Exception as e:
        st.warning(f"Could not load previous session: {e}")
        return {'messages': [], 'kmz_data': None, 'excel_data': None}

def list_sessions() -> List[str]:
    """List all available sessions"""
    sessions = []
    for file in STORAGE_DIR.glob("session_*.pkl"):
        session_id = file.stem.replace("session_", "")
        sessions.append(session_id)
    return sessions

# Store parsed KMZ data
def store_kmz_data(data: Dict):
    """Store KMZ data in session state and persist it"""
    st.session_state.kmz_data = data
    if 'session_id' in st.session_state:
        current_data = load_session_data(st.session_state.session_id)
        save_session_data(
            st.session_state.session_id,
            current_data['messages'],
            kmz_data=data,
            excel_data=current_data.get('excel_data')
        )

def get_kmz_data() -> Dict:
    """Get stored KMZ data"""
    return st.session_state.get('kmz_data', {})

# Excel handling tools
@tool
async def create_excel_from_kmz(output_path: str = "tank_compliance.xlsx", include_distances: bool = False) -> str:
    """
    Create an Excel file from the previously parsed KMZ data.
    Use this AFTER parsing a KMZ file.
    """
    kmz_data = get_kmz_data()
    if not kmz_data:
        return "Error: No KMZ data found. Please parse a KMZ file first using parse_kmz_file."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    if not sites:
        return "Error: No sites found in KMZ data"

    # Create DataFrame with the specified format
    excel_data = []
    for site in sites:
        row = {
            'Site Name or Business Name ': site['name'],
            'Person Contacted': '',
            'Tank Capacity': '',
            'Tank Measurements': '',
            'Dike Measurements': '',
            'Acceptable Separation Distance Calculated': '',
            'Approximate Distance to Site (approximately)': '',
            'Compliance': '',
            'Additional information ': '',
            'Latitude (NAD83)': site['latitude'],
            'Longitude (NAD83)': site['longitude'],
            'Calculated Distance to Polygon (ft)': '',
            'Tank Type': '',
            'Has Dike': ''
        }
        excel_data.append(row)

    # Calculate distances if requested
    if include_distances and polygons:
        main_polygon = None
        for polygon in polygons:
            if 'Buffer' not in polygon['name']:
                main_polygon = polygon
                break

        if main_polygon:
            polygon_coords = main_polygon['coordinates']
            distance_results = await tools_instance.batch_calculate_distances(sites, polygon_coords)

            distance_map = {}
            if isinstance(distance_results, list):
                for result in distance_results:
                    if 'name' in result and 'distance_feet' in result:
                        distance_map[result['name']] = result['distance_feet']

            for row in excel_data:
                site_name = row['Site Name or Business Name ']
                if site_name in distance_map:
                    row['Calculated Distance to Polygon (ft)'] = distance_map[site_name]

    # Create Excel file
    df = pd.DataFrame(excel_data)
    df = df.sort_values('Site Name or Business Name ')

    if not os.path.isabs(output_path):
        output_path = os.path.join(os.getcwd(), output_path)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tank Compliance', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Tank Compliance']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)

    # Store the Excel in session state
    st.session_state.current_excel = {'path': output_path, 'data': df}

    return f"✅ Excel file created successfully at: {output_path}\nTotal sites: {len(df)}"

@tool
async def read_excel_file(excel_path: str, sheet_name: Optional[str] = None) -> str:
    """Read an Excel file and display its contents"""
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(excel_path)

        st.session_state.current_excel = {'path': excel_path, 'data': df}

        # Persist Excel data
        if 'session_id' in st.session_state:
            current_data = load_session_data(st.session_state.session_id)
            save_session_data(
                st.session_state.session_id,
                current_data['messages'],
                kmz_data=current_data.get('kmz_data'),
                excel_data={'path': excel_path}
            )

        summary = f"📊 Excel file loaded: {excel_path}\n"
        summary += f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
        summary += f"Columns: {', '.join(df.columns.tolist())}\n\n"
        summary += "First 5 rows:\n"
        summary += df.head().to_string()
        return summary
    except Exception as e:
        return f"❌ Error reading Excel file: {str(e)}"

@tool
async def modify_excel_cell(row_identifier: str, column: str, new_value: str) -> str:
    """Modify a specific cell in the currently loaded Excel file"""
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "❌ Error: No Excel file loaded. Please read an Excel file first using read_excel_file."

    df = st.session_state.current_excel['data']
    try:
        # Check for the new column name format
        site_column = 'Site Name or Business Name ' if 'Site Name or Business Name ' in df.columns else 'Site Name'

        if site_column in df.columns:
            mask = df[site_column] == row_identifier
            if mask.any():
                df.loc[mask, column] = new_value
            else:
                # Try as index if not found by name
                try:
                    row_idx = int(row_identifier)
                    df.at[row_idx, column] = new_value
                except (ValueError, IndexError):
                    return f"❌ Error: Site '{row_identifier}' not found and not a valid row index"
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
    """Save changes made to the Excel file"""
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "❌ Error: No Excel file loaded"

    df = st.session_state.current_excel['data']
    save_path = output_path or st.session_state.current_excel['path']

    try:
        with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tank Compliance', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Tank Compliance']
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)
        return f"✅ Excel file saved successfully to: {save_path}"
    except Exception as e:
        return f"❌ Error saving Excel file: {str(e)}"

@tool
async def parse_kmz_file(kmz_path: str) -> str:
    """Parse KMZ/KML file to extract site locations and polygon boundaries"""
    result = await tools_instance.parse_kmz_file(kmz_path)
    store_kmz_data(result)

    summary = f"✅ Successfully parsed KMZ file: {kmz_path}\n\n"
    summary += f"Found {result['count']} sites:\n"
    for site in result['sites'][:5]:
        summary += f"  • {site['name']}\n"
    if result['count'] > 5:
        summary += f"  ... and {result['count'] - 5} more sites\n"

    summary += f"\nFound {len(result.get('polygons', []))} polygon(s):\n"
    for polygon in result.get('polygons', []):
        summary += f"  • {polygon['name']}\n"

    summary += "\n💡 Next steps:\n"
    summary += "  - Use 'display_kmz_info' to see all site details\n"
    summary += "  - Use 'create_excel_from_kmz' to create an Excel file\n"
    summary += "  - Use 'calculate_distances_for_sites' if you need distances\n"
    return summary

@tool
async def calculate_distances_for_sites(polygon_name: Optional[str] = None) -> str:
    """Calculate distances from parsed sites to polygon boundary"""
    kmz_data = get_kmz_data()
    if not kmz_data:
        return "❌ Error: No KMZ data found. Please parse a KMZ file first."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    if not sites or not polygons:
        return "❌ Error: Missing sites or polygons"

    selected_polygon = None
    if polygon_name:
        for p in polygons:
            if polygon_name.lower() in p['name'].lower():
                selected_polygon = p
                break
    else:
        for p in polygons:
            if 'Buffer' not in p['name']:
                selected_polygon = p
                break

    if not selected_polygon and polygons:
        selected_polygon = polygons[0]

    if not selected_polygon:
        return "❌ Error: No suitable polygon found"

    polygon_coords = selected_polygon['coordinates']
    distance_results = await tools_instance.batch_calculate_distances(sites, polygon_coords)

    summary = f"📏 Calculated distances using polygon: {selected_polygon['name']}\n\n"
    if isinstance(distance_results, list):
        distances = [r['distance_feet'] for r in distance_results if 'distance_feet' in r]
        if distances:
            summary += f"Distance Statistics:\n"
            summary += f"  • Minimum: {min(distances):.1f} ft\n"
            summary += f"  • Maximum: {max(distances):.1f} ft\n"
            summary += f"  • Average: {sum(distances)/len(distances):.1f} ft\n\n"

        summary += "Site distances:\n"
        for result in distance_results[:5]:
            summary += f"  • {result['name']}: {result.get('distance_feet', 'N/A'):.1f} ft\n"
        if len(distance_results) > 5:
            summary += f"  ... and {len(distance_results) - 5} more sites\n"
    return summary

# NEW TOOL: Display stored KMZ information
@tool
async def display_kmz_info() -> str:
    """
    Display the currently loaded KMZ file information including all sites and polygons.
    Use this when the user asks to list or show the parsed KMZ data.
    """
    kmz_data = get_kmz_data()
    if not kmz_data:
        return "❌ No KMZ data loaded. Please parse a KMZ file first using parse_kmz_file."

    sites = kmz_data.get('sites', [])
    polygons = kmz_data.get('polygons', [])

    output = "📍 **KMZ File Information**\n\n"

    # Sites information
    output += f"**Total Sites: {len(sites)}**\n\n"
    for i, site in enumerate(sites, 1):
        output += f"{i}. **{site['name']}**\n"
        output += f"   - Latitude: {site['latitude']:.8f}\n"
        output += f"   - Longitude: {site['longitude']:.8f}\n\n"

    # Polygons information
    output += f"\n**Total Polygons: {len(polygons)}**\n\n"
    for i, polygon in enumerate(polygons, 1):
        output += f"{i}. **{polygon['name']}**\n"
        output += f"   - Vertices: {len(polygon.get('coordinates', []))}\n"
        if polygon.get('coordinates'):
            # Show first few coordinates
            coords = polygon['coordinates'][:3]
            for j, coord in enumerate(coords, 1):
                output += f"   - Point {j}: ({coord[0]:.6f}, {coord[1]:.6f})\n"
            if len(polygon['coordinates']) > 3:
                output += f"   - ... and {len(polygon['coordinates']) - 3} more points\n"
        output += "\n"

    return output

# NEW TOOL: Display current Excel information
@tool
async def display_excel_info() -> str:
    """
    Display information about the currently loaded Excel file.
    Use this when the user asks to show or list Excel data.
    """
    if 'current_excel' not in st.session_state or 'data' not in st.session_state.current_excel:
        return "❌ No Excel file loaded. Please use read_excel_file to load an Excel file."

    df = st.session_state.current_excel['data']
    path = st.session_state.current_excel.get('path', 'Unknown')

    output = f"📊 **Excel File Information**\n\n"
    output += f"**File Path:** {path}\n"
    output += f"**Dimensions:** {df.shape[0]} rows × {df.shape[1]} columns\n\n"

    output += "**Columns:**\n"
    for col in df.columns:
        non_empty = df[col].notna().sum()
        output += f"- {col} ({non_empty}/{len(df)} filled)\n"

    output += f"\n**Data Preview (first 10 rows):**\n"
    output += "```\n"
    output += df.head(10).to_string()
    output += "\n```"

    # Summary statistics for numeric columns
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
    if len(numeric_cols) > 0:
        output += "\n**Numeric Column Statistics:**\n"
        for col in numeric_cols:
            if df[col].notna().any():
                output += f"\n{col}:\n"
                output += f"  - Min: {df[col].min():.2f}\n"
                output += f"  - Max: {df[col].max():.2f}\n"
                output += f"  - Mean: {df[col].mean():.2f}\n"

    return output

# Additional tools
@tool
async def parse_tank_measurements(measurement_str: str) -> str:
    """Parse tank measurements and calculate volume"""
    result = await tools_instance.parse_tank_measurements(measurement_str)
    return str(result)

@tool
async def assess_compliance(distance_feet: float, asd_values: Dict[str, float], has_dike: bool = False) -> str:
    """Assess compliance based on distance and ASD requirements"""
    result = await tools_instance.assess_compliance(distance_feet, asd_values, has_dike)
    return str(result)

# All tools
tank_tools = [
    parse_kmz_file,
    display_kmz_info,  # NEW: Display parsed KMZ data
    display_excel_info,  # NEW: Display loaded Excel data
    create_excel_from_kmz,
    read_excel_file,
    modify_excel_cell,
    save_excel_changes,
    calculate_distances_for_sites,
    parse_tank_measurements,
    assess_compliance,
]

# Initialize LLM and agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)

system_content = """You are a helpful assistant specialized in tank compliance assessment.

IMPORTANT RULES:
1. When a user asks to "list", "show", or "display" information about parsed KMZ data, use the 'display_kmz_info' tool.
2. When a user asks about Excel data details, use the 'display_excel_info' tool.
3. Do NOT automatically calculate distances after parsing a KMZ file.
4. Always check if data is already loaded before suggesting to parse/load files again.

Available tools:
- parse_kmz_file: Parse KMZ/KML files (no auto-calculation)
- display_kmz_info: Show all details of parsed KMZ data (use when user asks to list/show info)
- display_excel_info: Show details of loaded Excel file
- create_excel_from_kmz: Create Excel from parsed data
- read_excel_file: Read Excel files
- modify_excel_cell: Modify Excel cells
- save_excel_changes: Save Excel changes
- calculate_distances_for_sites: Calculate distances
- parse_tank_measurements: Parse tank dimensions
- assess_compliance: Check compliance

Remember to use display_kmz_info when users ask to see or list the parsed KMZ information."""

checkpointer = MemorySaver()
app = create_react_agent(llm, tank_tools, prompt=system_content, checkpointer=checkpointer)

def format_message(message: BaseMessage) -> str:
    """Format messages for display"""
    if isinstance(message, HumanMessage):
        return message.content
    elif isinstance(message, AIMessage):
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tools = []
            for tc in message.tool_calls:
                args = ', '.join(f"{k}={v}" for k, v in tc.get('args', {}).items())
                tools.append(f"**{tc.get('name')}**({args})")
            prefix = f"{message.content}\n\n" if message.content else ""
            return f"{prefix}🔧 Using: {', '.join(tools)}"
        return message.content or ""
    elif isinstance(message, ToolMessage):
        content = message.content
        # Don't truncate for display tools
        if hasattr(message, 'name') and 'display' in getattr(message, 'name', ''):
            return f"📊 Result:\n{content}"
        elif len(content) > 800:
            return f"📊 Result:\n{content[:800]}..."
        else:
            return f"📊 Result:\n{content}"
    return str(message.content) if hasattr(message, 'content') else str(message)

def run_chat_interface():
    st.set_page_config(
        page_title="Tank Compliance Agent (Persistent)",
        page_icon="🏭",
        layout="wide"
    )

    st.title("🏭 Tank Compliance Assessment Agent")
    st.markdown("*With persistent chat history across sessions*")

    # Sidebar
    with st.sidebar:
        st.header("💾 Session Management")

        # Session selection
        available_sessions = list_sessions()

        if available_sessions:
            st.subheader("Load Previous Session")
            selected_session = st.selectbox(
                "Select a session:",
                ["New Session"] + available_sessions,
                key="session_selector"
            )

            if selected_session != "New Session" and st.button("Load Session"):
                st.session_state.session_id = selected_session
                st.session_state.force_load = True
                st.rerun()

        # Current session ID
        if 'session_id' not in st.session_state:
            st.session_state.session_id = hashlib.md5(
                f"{datetime.now().isoformat()}_{id(st.session_state)}".encode()
            ).hexdigest()[:12]

        st.info(f"Current Session: {st.session_state.session_id}")

        # Load session data
        if 'force_load' in st.session_state and st.session_state.force_load:
            session_data = load_session_data(st.session_state.session_id)
            st.session_state.messages = session_data['messages']
            st.session_state.kmz_data = session_data.get('kmz_data', {})
            if session_data.get('excel_data'):
                st.session_state.current_excel = session_data['excel_data']
            st.session_state.force_load = False

        st.divider()

        # Session info
        st.header("📊 Current Data")

        if 'kmz_data' in st.session_state and st.session_state.kmz_data:
            st.success("✅ KMZ Loaded")
            kmz = st.session_state.kmz_data
            st.write(f"Sites: {len(kmz.get('sites', []))}")
            st.write(f"Polygons: {len(kmz.get('polygons', []))}")
        else:
            st.info("No KMZ loaded")

        if 'current_excel' in st.session_state:
            st.success("✅ Excel Loaded")
            st.write(f"Path: {st.session_state.current_excel.get('path', 'N/A')}")
        else:
            st.info("No Excel loaded")

        st.divider()

        # Actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 New Session"):
                # Save current session first
                if 'messages' in st.session_state:
                    save_session_data(
                        st.session_state.session_id,
                        st.session_state.messages,
                        st.session_state.get('kmz_data'),
                        st.session_state.get('current_excel')
                    )
                # Create new session
                st.session_state.session_id = hashlib.md5(
                    f"{datetime.now().isoformat()}_{id(st.session_state)}".encode()
                ).hexdigest()[:12]
                st.session_state.messages = []
                st.session_state.kmz_data = {}
                st.session_state.current_excel = None
                st.rerun()

        with col2:
            if st.button("💾 Save Session"):
                if 'messages' in st.session_state:
                    save_session_data(
                        st.session_state.session_id,
                        st.session_state.messages,
                        st.session_state.get('kmz_data'),
                        st.session_state.get('current_excel')
                    )
                    st.success("Session saved!")

        # Examples
        with st.expander("💡 Examples"):
            st.code("""
# 1. Parse KMZ
Parse the KMZ file at /home/avapc/Appspc/explosivos/pipeline_isolated/JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz

# 2. Create Excel
Create an Excel file from the KMZ data

# 3. Calculate distances
Calculate distances for all sites
            """)

    # Initialize messages from storage
    if 'messages' not in st.session_state:
        session_data = load_session_data(st.session_state.session_id)
        st.session_state.messages = session_data['messages']
        st.session_state.kmz_data = session_data.get('kmz_data', {})
        if session_data.get('excel_data'):
            st.session_state.current_excel = session_data['excel_data']

    # Display messages
    for message in st.session_state.messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user", avatar="👤"):
                st.markdown(format_message(message))
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(format_message(message))

    # Chat input
    if user_input := st.chat_input("Enter your query:"):
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Add to messages
        user_message = HumanMessage(content=user_input)
        st.session_state.messages.append(user_message)

        # Process with agent
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Processing..."):
                config = {"configurable": {"thread_id": st.session_state.session_id}}

                async def run_agent():
                    response_messages = []
                    async for chunk in app.astream(
                        {"messages": [user_message]},
                        config=config
                    ):
                        for key, value in chunk.items():
                            if 'messages' in value:
                                response_messages.extend(value['messages'])
                    return response_messages

                response_messages = asyncio.run(run_agent())

                # Display and save responses
                for msg in response_messages:
                    if not isinstance(msg, HumanMessage):
                        st.markdown(format_message(msg))
                        st.session_state.messages.append(msg)

        # Save session after each interaction
        save_session_data(
            st.session_state.session_id,
            st.session_state.messages,
            st.session_state.get('kmz_data'),
            st.session_state.get('current_excel')
        )

        st.rerun()

if __name__ == "__main__":
    run_chat_interface()