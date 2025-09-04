#!/usr/bin/env python3
"""
Agent-Based KMZ Parser with LangGraph
Uses tools and agents for robust KMZ/KML parsing with optional LLM supervision.
No heuristics/dummy fallback: if no API key, LLM enhancements are skipped.
"""

import os
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Any, Literal, Annotated
from pathlib import Path
import json
import argparse
import pandas as pd
from datetime import datetime
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode, create_react_agent, InjectedState
from langgraph.graph.message import add_messages, MessagesState
from langgraph.types import Command, Send
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ============================================================================
# DATA MODELS
# ============================================================================

class PlacemarkData(BaseModel):
    """Raw placemark data from KML"""
    index: int
    name: Optional[str] = None
    description: Optional[str] = None
    xml_string: str
    element_type: Optional[str] = None  # Structural detection


class ClassifiedPlacemark(BaseModel):
    """Classified placemark with type and metadata"""
    index: int
    name: str
    type: Literal["polygon", "point", "polyline", "unknown"]
    confidence: float
    coordinates: Optional[List[Tuple[float, float]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedPolygon(BaseModel):
    """Extracted polygon information"""
    name: str
    coordinates: List[Tuple[float, float]]
    type: str = "site_boundary"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedPoint(BaseModel):
    """Extracted point information"""
    name: str
    latitude: float
    longitude: float
    tank_capacity: Optional[str] = None
    tank_type: Optional[str] = None
    has_dike: Optional[bool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class KMZAgentState(MessagesState):
    """State for agent-based KMZ parsing"""
    # Input/Output
    kmz_path: str
    output_dir: str = "."
    
    # Processing queues
    raw_kml: Optional[str] = None
    placemarks_queue: List[PlacemarkData] = Field(default_factory=list)
    current_batch: List[PlacemarkData] = Field(default_factory=list)
    
    # Results
    classified_placemarks: List[ClassifiedPlacemark] = Field(default_factory=list)
    extracted_polygons: List[ExtractedPolygon] = Field(default_factory=list)
    extracted_points: List[ExtractedPoint] = Field(default_factory=list)
    
    # Progress tracking
    total_placemarks: int = 0
    processed_count: int = 0
    current_batch_num: int = 0
    
    # Error handling
    processing_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ============================================================================
# TOOLS FOR AGENT
# ============================================================================

@tool
def analyze_placemark_structure(xml_string: str) -> Dict[str, Any]:
    """
    Analyze KML placemark structure to determine type and extract basic info.
    This is a fast, reliable method that doesn't require LLM.
    """
    result = {
        "type": "unknown",
        "confidence": 0.8,
        "has_polygon": False,
        "has_point": False,
        "has_linestring": False,
        "name": None,
        "description": None
    }
    
    # Check for geometric elements
    if "Polygon" in xml_string or "LinearRing" in xml_string:
        result["type"] = "polygon"
        result["has_polygon"] = True
        result["confidence"] = 0.95
    elif "Point" in xml_string:
        result["type"] = "point"
        result["has_point"] = True
        result["confidence"] = 0.95
    elif "LineString" in xml_string:
        result["type"] = "polyline"
        result["has_linestring"] = True
        result["confidence"] = 0.95
    
    # Extract name
    name_match = re.search(r'<name[^>]*>([^<]+)</name>', xml_string)
    if name_match:
        result["name"] = name_match.group(1).strip()
    
    # Extract description
    desc_match = re.search(r'<description[^>]*>([^<]+)</description>', xml_string)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    
    return result


@tool
def extract_coordinates_from_xml(xml_string: str) -> List[Dict[str, float]]:
    """
    Extract coordinates from KML XML string.
    Returns list of coordinate dictionaries with lon, lat keys.
    """
    coordinates = []
    
    # Find coordinates element (including multiline content)
    coord_match = re.search(r'<coordinates[^>]*>(.*?)</coordinates>', xml_string, re.DOTALL)
    if not coord_match:
        return coordinates
    
    coord_text = coord_match.group(1).strip()
    
    # Clean up whitespace and newlines
    coord_text = re.sub(r'\s+', ' ', coord_text)
    
    # Split into coordinate pairs
    for pair in coord_text.split():
        if ',' in pair:
            parts = pair.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates.append({"lon": lon, "lat": lat})
                except ValueError:
                    continue
    
    return coordinates


@tool
def classify_with_llm(
    name: str,
    description: Optional[str],
    structural_type: str
) -> Dict[str, Any]:
    """
    Use LLM to enhance classification and extract metadata from placemark when
    OPENAI_API_KEY is configured; otherwise return structural_type with empty metadata.
    """
    import json as _json
    metadata: Dict[str, Any] = {}

    # If API key present, try a real LLM call with structured JSON output.
    try:
        if os.getenv('OPENAI_API_KEY'):
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            prompt = (
                "You classify KML placemarks. Return a strict JSON object with keys "
                "type (one of: polygon, point, polyline, unknown), confidence (0..1), "
                "and metadata {capacity, tank_type, has_dike}. Use structural_type as default.\n\n"
                f"name: {name or ''}\n"
                f"description: {description or ''}\n"
                f"structural_type: {structural_type}\n\n"
                "Respond with JSON only."
            )
            resp = llm.invoke(prompt)
            text = getattr(resp, 'content', str(resp))
            parsed = _json.loads(text)
            # minimal validation
            out_type = parsed.get('type') or structural_type
            conf = float(parsed.get('confidence', 0.85))
            meta = parsed.get('metadata') or {}
            return {
                "type": out_type,
                "confidence": max(0.0, min(1.0, conf)),
                "metadata": meta,
            }
    except Exception:
        # If LLM fails, skip enhancements (no dummy heuristics)
        pass

    # No API key or LLM failed: return structural type with empty metadata
    return {
        "type": structural_type,
        "confidence": 0.85,
        "metadata": {}
    }


@tool
def save_parsing_results(
    polygons: List[Dict],
    points: List[Dict],
    output_dir: str,
    timestamp: str
) -> Dict[str, str]:
    """
    Save parsing results to files.
    Returns paths to saved files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    saved_files = {}
    
    # Save polygons to text files
    if polygons:
        for i, polygon in enumerate(polygons, 1):
            name_safe = polygon['name'].replace(' ', '_').replace('/', '_')
            filename = output_dir / f"polygon_{i}_{name_safe}_{timestamp}.txt"
            with open(filename, 'w') as f:
                for coord in polygon['coordinates']:
                    f.write(f"{coord[0]},{coord[1]}\n")
            saved_files[f"polygon_{i}"] = str(filename)
    
    # Save points to Excel
    if points:
        points_data = []
        for point in points:
            # Base row from parsed point
            row = {
                'Site Name or Business Name ': point['name'],
                'Latitude (NAD83)': point['latitude'],
                'Longitude (NAD83)': point['longitude'],
                'Tank Capacity': point.get('tank_capacity', ''),
                'Tank Type': point.get('tank_type', ''),
                'Has Dike': 'Yes' if point.get('has_dike') else '',
                'Additional information ': json.dumps(point.get('metadata', {}))
            }
            # Pre-create capacity-related helper columns so later steps don't add them
            row['Tank Measurements'] = ''
            # Dike measurements placeholder (area-only later)
            row['Dike Measurements'] = ''
            # Compliance-related columns placeholders (match final table)
            row['Acceptable Separation Distance Calculated '] = ''
            row['Approximate Distance to Site (appoximately) '] = ''
            row['Compliance'] = ''
            # Distance-to-polygon columns (present in final tables)
            row['Calculated Distance to Polygon (ft)'] = ''
            row['Closest Point Lat'] = ''
            row['Closest Point Lon'] = ''
            row['Point Location'] = ''
            # Optional contact column, left blank
            row['Person Contacted'] = ''
            points_data.append(row)

        df = pd.DataFrame(points_data)

        # Reorder columns to canonical order used by API normalization so order remains stable
        first_col = 'Site Name or Business Name '
        target_columns = [
            'Person Contacted',
            'Tank Capacity',
            'Tank Measurements',
            'Dike Measurements',
            'Acceptable Separation Distance Calculated ',
            'Approximate Distance to Site (appoximately) ',
            'Compliance',
            'Additional information ',
            'Latitude (NAD83)',
            'Longitude (NAD83)',
            'Calculated Distance to Polygon (ft)',
            'Closest Point Lat',
            'Closest Point Lon',
            'Point Location',
        ]
        # Include optional extras if present, but avoid duplicating columns that already
        # exist in the canonical target set (e.g., 'Additional information ').
        other_columns = [
            'Tank Type',
            'Has Dike',
        ]

        # Ensure all desired columns exist
        desired = [first_col] + [c for c in target_columns if c != first_col] + [c for c in other_columns if c in df.columns]
        # Deduplicate while preserving order to avoid Excel writing '... .1' headers
        seen = set()
        desired = [c for c in desired if not (c in seen or seen.add(c))]
        for col in desired:
            if col not in df.columns:
                df[col] = ''
        # Apply order
        df = df[desired]

        excel_file = output_dir / f"tank_locations_{timestamp}.xlsx"
        df.to_excel(excel_file, index=False)
        saved_files['excel'] = str(excel_file)
    
    # Save complete JSON
    json_file = output_dir / f"kmz_parse_result_{timestamp}.json"
    with open(json_file, 'w') as f:
        json.dump({
            'polygons': polygons,
            'points': points,
            'timestamp': timestamp
        }, f, indent=2)
    saved_files['json'] = str(json_file)
    
    return saved_files


# ============================================================================
# KMZ PARSER AGENT
# ============================================================================

class KMZParserAgent:
    """Agent-based KMZ parser using LangGraph"""
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        batch_size: int = 5
    ):
        """Initialize the parser agent"""
        self.model_name = model_name
        self.temperature = temperature
        self.batch_size = batch_size
        
        # Initialize LLM lazily only if an API key is configured.
        # KMZ→Excel does not require LLM; keep this optional to avoid hard dependency.
        self.llm = None
        try:
            if os.getenv('OPENAI_API_KEY'):
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    timeout=30,
                    max_retries=2,
                )
        except Exception:
            # If the key is missing or misconfigured, proceed without LLM.
            self.llm = None
        
        # Build the workflow
        self.app = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the agent workflow"""
        builder = StateGraph(KMZAgentState)
        
        # Add nodes
        builder.add_node("extract_kml", self._extract_kml_node)
        builder.add_node("parse_placemarks", self._parse_placemarks_node)
        builder.add_node("process_batch", self._process_batch_node)
        builder.add_node("classify_placemarks", self._classify_placemarks_node)
        builder.add_node("compile_results", self._compile_results_node)
        builder.add_node("save_results", self._save_results_node)
        
        # Add edges
        builder.add_edge(START, "extract_kml")
        builder.add_edge("extract_kml", "parse_placemarks")
        builder.add_edge("parse_placemarks", "process_batch")
        
        # Conditional edge for batch processing
        builder.add_conditional_edges(
            "process_batch",
            self._should_continue_batching,
            {
                "continue": "classify_placemarks",
                "done": "compile_results"
            }
        )
        
        builder.add_edge("classify_placemarks", "process_batch")
        builder.add_edge("compile_results", "save_results")
        builder.add_edge("save_results", END)
        
        return builder.compile()
    
    def _extract_kml_node(self, state: KMZAgentState) -> Dict:
        """Extract KML from KMZ file"""
        print(f"📦 Extracting KML from: {state['kmz_path']}")
        
        try:
            path = Path(state['kmz_path'])
            
            if path.suffix.lower() == '.kmz':
                with zipfile.ZipFile(path, 'r') as kmz:
                    for file_name in kmz.namelist():
                        if file_name.endswith('.kml'):
                            with kmz.open(file_name) as kml_file:
                                kml_content = kml_file.read().decode('utf-8')
                                print(f"   ✓ Extracted {len(kml_content)} characters")
                                return {"raw_kml": kml_content}
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    kml_content = f.read()
                    return {"raw_kml": kml_content}
                    
        except Exception as e:
            error_msg = f"Failed to extract KML: {e}"
            print(f"   ❌ {error_msg}")
            return {"processing_errors": [error_msg]}
    
    def _parse_placemarks_node(self, state: KMZAgentState) -> Dict:
        """Parse placemarks from KML"""
        print("📋 Parsing placemarks from KML...")
        
        try:
            # Clean up unbound namespace prefixes before parsing
            kml_content = state['raw_kml']
            
            # Remove unbound namespace prefixes like ns1:, ns2:, etc.
            import re
            kml_content = re.sub(r'<ns\d+:', '<', kml_content)
            kml_content = re.sub(r'</ns\d+:', '</', kml_content)
            
            # Register namespaces to handle them properly
            ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
            ET.register_namespace('gx', 'http://www.google.com/kml/ext/2.2')
            ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
            
            root = ET.fromstring(kml_content)
            
            # Find all placemarks (handling namespaces)
            placemarks = []
            for elem in root.iter():
                if 'Placemark' in elem.tag:
                    # Convert element to string, removing namespace prefixes for easier processing
                    pm_str = ET.tostring(elem, encoding='unicode')
                    
                    # Remove namespace prefixes from the XML string for tools to process
                    # This makes it easier for regex-based tools to work
                    pm_str_clean = pm_str
                    pm_str_clean = re.sub(r'<ns\d+:', '<', pm_str_clean)
                    pm_str_clean = re.sub(r'</ns\d+:', '</', pm_str_clean)
                    pm_str_clean = re.sub(r' xmlns:ns\d+="[^"]*"', '', pm_str_clean)
                    
                    # Extract basic info
                    name = None
                    desc = None
                    for child in elem:
                        if 'name' in child.tag.lower():
                            name = child.text
                        elif 'description' in child.tag.lower():
                            desc = child.text
                    
                    placemark = PlacemarkData(
                        index=len(placemarks),
                        name=name,
                        description=desc,
                        xml_string=pm_str_clean  # Use cleaned XML
                    )
                    placemarks.append(placemark)
            
            print(f"   ✓ Found {len(placemarks)} placemarks")
            
            return {
                "placemarks_queue": placemarks,
                "total_placemarks": len(placemarks)
            }
            
        except Exception as e:
            error_msg = f"Failed to parse placemarks: {e}"
            print(f"   ❌ {error_msg}")
            return {"processing_errors": [error_msg]}
    
    def _process_batch_node(self, state: KMZAgentState) -> Dict:
        """Process next batch of placemarks"""
        queue = state.get('placemarks_queue', [])
        
        if not queue:
            print("   ✓ All batches processed")
            return {"current_batch": []}
        
        # Take next batch
        batch_size = min(self.batch_size, len(queue))
        current_batch = queue[:batch_size]
        remaining_queue = queue[batch_size:]
        
        batch_num = state.get('current_batch_num', 0) + 1
        print(f"\n📦 Processing batch {batch_num} ({len(current_batch)} placemarks)")
        
        return {
            "current_batch": current_batch,
            "placemarks_queue": remaining_queue,
            "current_batch_num": batch_num
        }
    
    def _classify_placemarks_node(self, state: KMZAgentState) -> Dict:
        """Classify placemarks in current batch using tools"""
        batch = state.get('current_batch', [])
        if not batch:
            return {}
        
        classified = []
        errors = []
        
        for pm in batch:
            try:
                # Step 1: Structural analysis (fast, reliable)
                structural_result = analyze_placemark_structure.invoke({
                    "xml_string": pm.xml_string
                })
                
                # Step 2: Extract coordinates
                # Debug: check if coordinates tag exists
                if '<coordinates' in pm.xml_string:
                    print(f"      XML has coordinates tag for {pm.name}")
                    # Print a snippet of the coordinates
                    coord_start = pm.xml_string.find('<coordinates')
                    coord_end = pm.xml_string.find('</coordinates>', coord_start)
                    if coord_start != -1 and coord_end != -1:
                        snippet = pm.xml_string[coord_start:coord_end+14][:200]
                        print(f"      Snippet: {snippet}")
                
                coords_result = extract_coordinates_from_xml.invoke({
                    "xml_string": pm.xml_string
                })
                
                # Convert coordinates format
                coordinates = [(c['lon'], c['lat']) for c in coords_result]
                
                # Debug: print coordinates found
                if coordinates:
                    print(f"      Found {len(coordinates)} coordinates for {pm.name or f'Feature_{pm.index}'}")
                else:
                    print(f"      No coordinates found for {pm.name}")
                
                # Step 3: Optional LLM enhancement (only if description exists)
                metadata = {}
                final_type = structural_result['type']
                confidence = structural_result['confidence']
                
                if pm.description and len(pm.description) > 10:
                    try:
                        llm_result = classify_with_llm.invoke({
                            "name": pm.name,
                            "description": pm.description,
                            "structural_type": structural_result['type']
                        })
                        final_type = llm_result.get('type', final_type)
                        confidence = llm_result.get('confidence', confidence)
                        metadata = llm_result.get('metadata', {})
                    except Exception as llm_error:
                        # Fallback to structural analysis
                        print(f"   ⚠️ LLM enhancement failed for {pm.name}: {llm_error}")
                
                # Create classified placemark
                classified_pm = ClassifiedPlacemark(
                    index=pm.index,
                    name=pm.name or f"Feature_{pm.index}",
                    type=final_type,
                    confidence=confidence,
                    coordinates=coordinates if coordinates else None,
                    metadata=metadata
                )
                
                classified.append(classified_pm)
                
                print(f"   {pm.index + 1}. {classified_pm.name}: {classified_pm.type} "
                      f"(conf: {classified_pm.confidence:.2f})")
                
            except Exception as e:
                error_msg = f"Failed to classify placemark {pm.index}: {e}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")
        
        # Update processed count
        processed_count = state.get('processed_count', 0) + len(classified)
        
        return {
            "classified_placemarks": state.get('classified_placemarks', []) + classified,
            "processed_count": processed_count,
            "processing_errors": state.get('processing_errors', []) + errors
        }
    
    def _should_continue_batching(self, state: KMZAgentState) -> str:
        """Determine if we should continue processing batches"""
        queue = state.get('placemarks_queue', [])
        current_batch = state.get('current_batch', [])
        
        if queue or current_batch:
            return "continue"
        else:
            return "done"
    
    def _compile_results_node(self, state: KMZAgentState) -> Dict:
        """Compile classified placemarks into final results"""
        print("\n📊 Compiling results...")
        
        classified = state.get('classified_placemarks', [])
        polygons = []
        points = []
        
        print(f"   Processing {len(classified)} classified placemarks...")
        
        for pm in classified:
            # Debug: show what we're processing
            if pm.coordinates:
                print(f"   - {pm.name}: {pm.type} with {len(pm.coordinates)} coords")
            
            if pm.type == "polygon" and pm.coordinates and len(pm.coordinates) >= 3:
                polygon = ExtractedPolygon(
                    name=pm.name,
                    coordinates=pm.coordinates,
                    metadata=pm.metadata
                )
                polygons.append(polygon)
                
            elif pm.type == "point" and pm.coordinates and len(pm.coordinates) > 0:
                lon, lat = pm.coordinates[0]
                point = ExtractedPoint(
                    name=pm.name,
                    latitude=lat,
                    longitude=lon,
                    tank_capacity=pm.metadata.get('capacity'),
                    tank_type=pm.metadata.get('tank_type'),
                    has_dike=pm.metadata.get('has_dike'),
                    metadata=pm.metadata
                )
                points.append(point)
        
        print(f"   • Polygons: {len(polygons)}")
        print(f"   • Points: {len(points)}")
        print(f"   • Errors: {len(state.get('processing_errors', []))}")
        
        return {
            "extracted_polygons": polygons,
            "extracted_points": points
        }
    
    def _save_results_node(self, state: KMZAgentState) -> Dict:
        """Save results to files"""
        print("\n💾 Saving results...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Convert to dict format for saving
        polygons_dict = [
            {
                'name': p.name,
                'coordinates': p.coordinates,
                'metadata': p.metadata
            } for p in state.get('extracted_polygons', [])
        ]
        
        points_dict = [
            {
                'name': p.name,
                'latitude': p.latitude,
                'longitude': p.longitude,
                'tank_capacity': p.tank_capacity,
                'tank_type': p.tank_type,
                'has_dike': p.has_dike,
                'metadata': p.metadata
            } for p in state.get('extracted_points', [])
        ]
        
        saved_files = save_parsing_results.invoke({
            "polygons": polygons_dict,
            "points": points_dict,
            "output_dir": state.get('output_dir', '.'),
            "timestamp": timestamp
        })
        
        for file_type, path in saved_files.items():
            print(f"   ✓ Saved {file_type}: {path}")
        
        return {"messages": [AIMessage(content="✅ Parsing complete!")]}
    
    def parse(self, kmz_path: str, output_dir: str = ".") -> Dict[str, Any]:
        """
        Parse a KMZ file using the agent workflow
        
        Args:
            kmz_path: Path to KMZ/KML file
            output_dir: Directory for output files
            
        Returns:
            Parsing results dictionary
        """
        print("\n" + "="*50)
        print("🤖 AGENT-BASED KMZ PARSER")
        print("="*50)
        
        # Initialize state
        initial_state = {
            "kmz_path": kmz_path,
            "output_dir": output_dir,
            "messages": [HumanMessage(content=f"Parse KMZ file: {kmz_path}")]
        }
        
        # Run the agent workflow
        try:
            final_state = self.app.invoke(initial_state)
            
            # Extract results
            result = {
                "polygons": [p.model_dump() for p in final_state.get('extracted_polygons', [])],
                "points": [p.model_dump() for p in final_state.get('extracted_points', [])],
                "errors": final_state.get('processing_errors', []),
                "warnings": final_state.get('warnings', [])
            }
            
            print("\n✅ Parsing complete!")
            print(f"   • Polygons: {len(result['polygons'])}")
            print(f"   • Points: {len(result['points'])}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Error during parsing: {e}")
            return {
                "polygons": [],
                "points": [],
                "errors": [str(e)],
                "warnings": []
            }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Agent-based KMZ/KML parser using LangGraph',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('kmz_file', help='KMZ or KML file to parse')
    parser.add_argument('-o', '--output-dir', default='.',
                       help='Output directory for results')
    parser.add_argument('--model', default='gpt-4o-mini',
                       help='OpenAI model to use (default: gpt-4o-mini)')
    parser.add_argument('--batch-size', type=int, default=5,
                       help='Batch size for processing (default: 5)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Check file exists
    if not Path(args.kmz_file).exists():
        print(f"❌ Error: File not found: {args.kmz_file}")
        return 1
    
    try:
        # Initialize parser
        agent_parser = KMZParserAgent(
            model_name=args.model,
            batch_size=args.batch_size
        )
        
        # Parse KMZ
        result = agent_parser.parse(args.kmz_file, args.output_dir)
        
        # Display summary
        if result['polygons']:
            print("\n🔷 Polygons (Site Boundaries):")
            for polygon in result['polygons']:
                coords_count = len(polygon.get('coordinates', []))
                print(f"   • {polygon['name']} ({coords_count} vertices)")
        
        if result['points']:
            print("\n📍 Points (Tank Locations):")
            for i, point in enumerate(result['points'][:10], 1):
                capacity = f" - {point['tank_capacity']}" if point.get('tank_capacity') else ""
                print(f"   {i}. {point['name']}{capacity}")
            if len(result['points']) > 10:
                print(f"   ... and {len(result['points']) - 10} more")
        
        if result['errors']:
            print("\n⚠️ Errors encountered:")
            for error in result['errors'][:5]:
                print(f"   • {error}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
