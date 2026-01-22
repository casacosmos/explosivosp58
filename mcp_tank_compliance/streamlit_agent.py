#!/usr/bin/env python3
"""
Improved LangGraph Agent for Tank Compliance with proper message history handling
"""

import asyncio
import os
from typing import Annotated, Dict, List, Any, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import streamlit as st
from server import TankComplianceTools  # Import from the provided server.py

# Initialize the tools class
tools_instance = TankComplianceTools()

# Define LangChain tools wrapping the MCP tools
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
async def parse_kmz_file(kmz_path: str) -> str:
    """Parse KMZ/KML file to extract site locations and polygon boundaries"""
    result = await tools_instance.parse_kmz_file(kmz_path)
    return str(result)

@tool
async def convert_dms_to_decimal(degrees: float, minutes: float, seconds: float, direction: str = "N") -> float:
    """Convert coordinates from degrees/minutes/seconds to decimal degrees"""
    result = await tools_instance.convert_dms_to_decimal(degrees, minutes, seconds, direction)
    return result

@tool
async def match_sites_fuzzy(excel_sites: List[str], kmz_sites: List[Dict[str, Any]]) -> str:
    """Match site names between Excel and KMZ using fuzzy matching"""
    result = await tools_instance.match_sites_fuzzy(excel_sites, kmz_sites)
    return str(result)

@tool
async def calculate_distance_to_polygon(point_lat: float, point_lon: float, polygon_coords: List[List[float]]) -> str:
    """Calculate minimum distance from a point to polygon boundary using proper projection"""
    result = await tools_instance.calculate_distance_to_polygon(point_lat, point_lon, polygon_coords)
    return str(result)

@tool
async def batch_calculate_distances(sites: List[Dict[str, Any]], polygon_coords: List[List[float]]) -> str:
    """Calculate distances for multiple sites to polygon boundary"""
    result = await tools_instance.batch_calculate_distances(sites, polygon_coords)
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

@tool
async def process_hud_calculations(tanks: List[Dict[str, Any]], generate_pdf: bool = True, capture_screenshots: bool = True) -> str:
    """Process tanks through HUD ASD calculator browser automation to get compliance distances and generate PDF reports"""
    result = await tools_instance.process_hud_calculations(tanks, generate_pdf, capture_screenshots)
    return str(result)

# Collect all tools
tank_tools = [
    parse_tank_measurements,
    parse_multi_tank_capacities,
    extract_asd_values,
    parse_kmz_file,
    convert_dms_to_decimal,
    match_sites_fuzzy,
    calculate_distance_to_polygon,
    batch_calculate_distances,
    assess_compliance,
    process_excel_compliance,
    create_kmz_file,
    update_excel_with_results,
    process_hud_calculations
]

# State definition for LangGraph
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], "The messages in the conversation"]

# Initialize the LLM with tool binding
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tank_tools)

# Updated Prompt template with explicit tool descriptions
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant specialized in tank compliance assessment.

Available tools:

- parse_tank_measurements: Parse tank measurements (e.g., '39"x46"x229"') and calculate volume in gallons
- parse_multi_tank_capacities: Parse capacity string with multiple tanks and identify largest for compliance
- extract_asd_values: Extract ASDPPU and ASDBPU values from ASD calculation string
- parse_kmz_file: Parse KMZ/KML file to extract site locations and polygon boundaries
- convert_dms_to_decimal: Convert coordinates from degrees/minutes/seconds to decimal degrees
- match_sites_fuzzy: Match site names between Excel and KMZ using fuzzy matching
- calculate_distance_to_polygon: Calculate minimum distance from a point to polygon boundary
- batch_calculate_distances: Calculate distances for multiple sites to polygon boundary
- assess_compliance: Assess compliance based on distance and ASD requirements
- process_excel_compliance: Process entire Excel file for comprehensive compliance assessment
- create_kmz_file: Create KMZ file with sites, polygons, and compliance visualization
- update_excel_with_results: Update Excel file with calculated distances and compliance results
- process_hud_calculations: Process tanks through HUD ASD calculator browser automation

Use these tools to assist the user with parsing data, calculating distances, assessing compliance, and generating reports."""),
    MessagesPlaceholder(variable_name="messages"),
])

# Agent node: calls the LLM (updated to handle ToolMessages for OpenAI validation)
agent_chain = prompt | llm_with_tools

async def call_model(state: AgentState):
    messages = state["messages"]

    # Convert ToolMessages to HumanMessages for LLM call to avoid OpenAI validation error
    llm_messages = []
    for m in messages:
        if isinstance(m, ToolMessage):
            llm_messages.append(HumanMessage(content=f"Tool Result: {m.content}"))
        else:
            llm_messages.append(m)

    # Invoke chain with converted messages
    response = await agent_chain.ainvoke({"messages": llm_messages})
    return {"messages": [response]}

# Tool node: executes tools
tool_node = ToolNode(tank_tools)

# Conditional edge: decide whether to continue or end
async def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END

# Build the graph
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# Compile the graph with MemorySaver for persistence
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Helper function to format messages for display
def format_message_for_display(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return message.content
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                tool_calls.append(f"**{tc['name']}**({', '.join(f'{k}={v}' for k, v in tc['args'].items())})")
            return f"Using tools: {', '.join(tool_calls)}"
        return message.content
    elif isinstance(message, ToolMessage):
        # Parse and format tool results
        content = message.content
        if "sites" in content and "count" in content:
            # KMZ parsing result
            return f"✅ Parsed KMZ file: Found {content.split('count')[1].split('}')[0].replace(':', '').strip()} sites"
        return f"Tool result: {content[:200]}..." if len(content) > 200 else f"Tool result: {content}"
    return str(message.content)

# Streamlit Chat Interface
def run_chat_interface():
    st.set_page_config(
        page_title="Tank Compliance Assessment Agent",
        page_icon="🏭",
        layout="wide"
    )

    st.title("🏭 Tank Compliance Assessment Agent")
    st.markdown("Interact with the agent to perform compliance assessments using the available tools.")

    # Sidebar for session management
    with st.sidebar:
        st.header("Session Management")

        # Initialize thread_id for persistence (unique per session)
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = "tank_compliance_session"

        # Session controls
        if st.button("🔄 Reset Conversation"):
            st.session_state.display_messages = []
            st.session_state.thread_id = f"tank_compliance_session_{asyncio.get_event_loop().time()}"
            st.rerun()

        st.divider()
        st.caption(f"Session ID: {st.session_state.thread_id[:20]}...")

        # Available tools info
        st.header("Available Tools")
        with st.expander("📋 Data Parsing"):
            st.markdown("""
            - **parse_kmz_file**: Extract locations from KMZ/KML files
            - **parse_tank_measurements**: Parse tank dimensions
            - **parse_multi_tank_capacities**: Parse multiple tank capacities
            - **extract_asd_values**: Extract ASD values
            """)

        with st.expander("📐 Calculations"):
            st.markdown("""
            - **calculate_distance_to_polygon**: Calculate boundary distances
            - **batch_calculate_distances**: Calculate for multiple sites
            - **convert_dms_to_decimal**: Convert coordinates
            """)

        with st.expander("✅ Compliance"):
            st.markdown("""
            - **assess_compliance**: Check compliance status
            - **process_excel_compliance**: Process full Excel files
            - **process_hud_calculations**: HUD ASD calculations
            """)

        with st.expander("📁 File Operations"):
            st.markdown("""
            - **create_kmz_file**: Create KMZ with results
            - **update_excel_with_results**: Update Excel files
            - **match_sites_fuzzy**: Match site names
            """)

    # Initialize display_messages properly
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

    # Main chat interface
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for idx, message in enumerate(st.session_state.display_messages):
            if isinstance(message, HumanMessage):
                with st.chat_message("user", avatar="👤"):
                    st.markdown(format_message_for_display(message))
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(format_message_for_display(message))

    # Chat input
    if user_input := st.chat_input("Enter your query about tank compliance:", key="user_input"):
        # Display user message immediately
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)

        # Create user message
        user_message = HumanMessage(content=user_input)

        # Prepare config for invocation
        config = {"configurable": {"thread_id": st.session_state.thread_id}}

        # Process with spinner
        with st.spinner("Processing..."):
            # Collect all new messages from the stream
            all_new_messages = []

            # Run the async stream
            async def process_stream():
                async for chunk in app.astream({"messages": [user_message]}, config=config, stream_mode="values"):
                    if "messages" in chunk and len(chunk["messages"]) > 0:
                        # Only get the last message from each chunk to avoid duplicates
                        last_msg = chunk["messages"][-1]
                        # Avoid adding duplicates
                        if not all_new_messages or last_msg != all_new_messages[-1]:
                            all_new_messages.append(last_msg)

            # Run the async function
            asyncio.run(process_stream())

            # Update display messages with user message and new responses
            st.session_state.display_messages.append(user_message)

            # Add only unique new messages (not the user message)
            for msg in all_new_messages:
                if msg != user_message and msg not in st.session_state.display_messages:
                    st.session_state.display_messages.append(msg)

        # Rerun to display the new messages
        st.rerun()

    # Example queries
    with st.expander("💡 Example Queries"):
        st.markdown("""
        Try these example queries:
        - "Parse the KMZ file at /home/avapc/Appspc/explosivos/pipeline_isolated/JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz"
        - "Calculate distances from sites to the polygon boundaries"
        - "Create an Excel file with the extracted data and distances"
        - "Assess compliance for all sites based on their distances"
        """)

if __name__ == "__main__":
    run_chat_interface()