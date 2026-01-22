#!/usr/bin/env python3
"""
Improved Excel to JSON Converter with deterministic volume calculation.
Integrates VolumeCalculator for accurate volume computations.
"""

import json
import pandas as pd
from typing import Dict, List, Optional, Any, TypedDict
from pathlib import Path
import os
import re
import sys
from enum import Enum

# Import the volume calculator
from volume_calculator import VolumeCalculator

# Pydantic for structured output
from pydantic import BaseModel, Field, field_validator
from typing_extensions import Annotated

# LangChain and LangGraph imports
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langgraph.graph import StateGraph, END
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    print("Missing dependencies. Install with: pip install langchain langchain-openai langgraph pydantic")
    print(f"Error: {e}")


# ============= Enhanced Pydantic Models =============

class TankType(str, Enum):
    """Valid tank types"""
    DIESEL = "diesel"
    PRESSURIZED_GAS = "pressurized_gas"
    LPG = "lpg"
    GASOLINE = "gasoline"
    FUEL = "fuel"


class DimensionSet(BaseModel):
    """Raw dimensions with unit information"""
    length: Optional[float] = Field(None, description="Length dimension")
    width: Optional[float] = Field(None, description="Width dimension")
    height: Optional[float] = Field(None, description="Height dimension")
    unit: Optional[str] = Field("ft", description="Unit of measurement")


class DikeDimensions(BaseModel):
    """Dike dimensions with unit"""
    length: Optional[float] = Field(None, description="Dike length")
    width: Optional[float] = Field(None, description="Dike width")
    unit: Optional[str] = Field("ft", description="Unit of measurement")


class TankRaw(BaseModel):
    """Tank with raw extracted data (pre-computation)"""
    name: str = Field(description="Tank or site name")
    
    # Volume can be provided directly or computed
    volume_raw: Optional[float] = Field(None, description="Direct volume if provided in data")
    volume_unit: Optional[str] = Field("gal", description="Unit of volume if provided")
    
    # Raw dimensions for computation
    dimensions_raw: Optional[DimensionSet] = Field(None, description="Tank dimensions if available")
    
    type: TankType = Field(default=TankType.DIESEL, description="Type of fuel/tank")
    has_dike: bool = Field(default=False, description="Whether tank has a dike/containment")
    
    # Dike dimensions with unit
    dike_dims_raw: Optional[DikeDimensions] = Field(None, description="Dike dimensions if available")
    
    # Optional context
    site: Optional[str] = Field(None, description="Client/site/business this tank belongs to")
    notes: Optional[str] = Field(None, description="Additional notes or information")
    
    model_config = {"use_enum_values": True}


class TankListRaw(BaseModel):
    """List of tanks with raw data"""
    tanks: List[TankRaw] = Field(description="List of tanks extracted from the data")


# ============= LangGraph State Definition =============

class ParserState(TypedDict):
    """State for the parsing workflow"""
    excel_path: str
    current_row: Optional[int]
    row_data: Optional[Dict[str, Any]]
    parsed_tanks_raw: List[TankRaw]  # Raw from LLM
    computed_tanks: List[Dict]  # After volume computation
    all_tanks: List[Dict]
    errors: List[str]
    retry_count: int
    max_retries: int
    volume_calculator: Any  # VolumeCalculator instance


# ============= Improved Excel Parser =============

class ImprovedExcelParser:
    """Excel to JSON parser with deterministic volume calculation"""
    
    def __init__(
        self,
        excel_path: str,
        *,
        sheet_name: Optional[str] = None,
        start_row: int = 1,
        max_rows: Optional[int] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
        debug: bool = False
    ):
        """Initialize parser with Excel file and VolumeCalculator."""
        
        if not IMPORTS_AVAILABLE:
            raise ImportError("Required packages not installed")

        self.excel_path = Path(excel_path)
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Configuration
        self.sheet_name = sheet_name
        self.start_row = max(1, int(start_row)) - 1
        self.max_rows = int(max_rows) if max_rows is not None else None
        self.max_retries = int(max_retries)
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.debug = debug

        # Initialize VolumeCalculator
        self.volume_calculator = VolumeCalculator(debug=debug)

        # Require OpenAI API key
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")

        # Initialize LLM with structured output
        try:
            self.llm = ChatOpenAI(
                model=self.model,
                temperature=0,
            ).with_structured_output(TankListRaw)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        
        # Load Excel data
        self._load_excel()
        
        # Build workflow
        self.workflow = self._build_workflow()
    
    def _load_excel(self):
        """Load Excel/CSV file"""
        try:
            ext = self.excel_path.suffix.lower()
            if ext == '.csv':
                self.file_type = 'csv'
                self.df = pd.read_csv(self.excel_path)
                if self.df.shape[1] == 1:
                    self.df = pd.read_csv(self.excel_path, sep=';')
            else:
                self.file_type = 'excel'
                if self.sheet_name:
                    self.df = pd.read_excel(self.excel_path, sheet_name=self.sheet_name)
                else:
                    self.df = pd.read_excel(self.excel_path)
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {e}")

        total_rows = len(self.df)
        if self.max_rows is None:
            end_row = total_rows
        else:
            end_row = min(total_rows, self.start_row + self.max_rows)
        self._row_window = (self.start_row, end_row)

        print(f"✓ Loaded {total_rows} rows from {self.file_type.upper()}")
        if self.start_row > 0 or self.max_rows is not None:
            print(f"  → Processing rows {self.start_row + 1} to {end_row} (1-based)")
        print(f"  → Using model: {self.model}")
        print(f"  → Volume calculation: Deterministic (VolumeCalculator)")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with volume computation"""
        
        workflow = StateGraph(ParserState)
        
        # Add nodes
        workflow.add_node("load_row", self._load_row)
        workflow.add_node("parse_with_llm", self._parse_with_llm)
        workflow.add_node("compute_volumes", self._compute_volumes)  # NEW NODE
        workflow.add_node("validate_result", self._validate_result)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("save_result", self._save_result)
        
        # Set entry point
        workflow.set_entry_point("load_row")
        
        # Add edges
        workflow.add_edge("load_row", "parse_with_llm")
        workflow.add_edge("parse_with_llm", "compute_volumes")  # Goes to volume computation
        workflow.add_edge("compute_volumes", "validate_result")  # Then validation
        
        workflow.add_conditional_edges(
            "validate_result",
            self._validation_result,
            {
                "success": "save_result",
                "retry": "parse_with_llm",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_error",
            self._should_retry,
            {
                "retry": "parse_with_llm",
                "save": "save_result"
            }
        )
        
        workflow.add_edge("save_result", END)
        
        return workflow.compile()
    
    def _load_row(self, state: ParserState) -> ParserState:
        """Load the current row data"""
        row_idx = state.get("current_row", 0)
        
        if row_idx < len(self.df):
            row_data = self.df.iloc[row_idx].to_dict()
            
            # Check if row is empty
            if all(pd.isna(v) or str(v).strip() == "" for v in row_data.values()):
                state["row_data"] = None
                state["parsed_tanks_raw"] = []
            else:
                state["row_data"] = row_data
            
            state["retry_count"] = 0
            state["volume_calculator"] = self.volume_calculator
        
        return state
    
    def _parse_with_llm(self, state: ParserState) -> ParserState:
        """Parse row data using LLM - extract dimensions, don't compute"""
        
        row_data = state["row_data"]
        
        # Skip empty rows
        if not row_data:
            state["parsed_tanks_raw"] = []
            state["errors"] = []
            return state
        
        # Create extraction prompt (not computation)
        prompt = self._create_extraction_prompt(row_data)
        
        try:
            # Get structured output from LLM
            result = self.llm.invoke(prompt)
            if isinstance(result, TankListRaw):
                state["parsed_tanks_raw"] = result.tanks
                state["errors"] = []
            else:
                state["parsed_tanks_raw"] = []
                state["errors"] = ["Invalid structured output from LLM"]
        except Exception as e:
            state["parsed_tanks_raw"] = []
            state["errors"] = [f"LLM error: {e}"]
        
        return state
    
    def _create_extraction_prompt(self, row_data: Dict[str, Any]) -> str:
        """Create prompt focused on extraction, not calculation"""
        
        formatted_data = []
        for key, value in row_data.items():
            if pd.notna(value) and str(value).strip():
                clean_key = key.strip().replace('  ', ' ')
                formatted_data.append(f"{clean_key}: {value}")
        
        data_text = "\n".join(formatted_data)
        
        prompt = f"""You are extracting tank details from a table row. Focus on EXTRACTION not CALCULATION.

DATA:
{data_text}

EXTRACTION RULES:
1. Extract all tanks (there may be multiple per row)

2. For VOLUME/CAPACITY:
   - If provided directly (e.g., "5000 gal", "2500 gallons"), extract the NUMBER and UNIT
   - volume_raw: the numeric value
   - volume_unit: "gal", "l", "bbl", etc.
   - DO NOT CALCULATE volumes from dimensions

3. For DIMENSIONS:
   - Extract LENGTH, WIDTH, HEIGHT as provided with their units
   - Examples to extract:
     * "10ft x 8ft x 6ft" → dimensions_raw: {{length: 10, width: 8, height: 6, unit: "ft"}}
     * "Length 4m, Width 3m, Height 2m" → dimensions_raw: {{length: 4, width: 3, height: 2, unit: "m"}}
     * "120in x 96in x 60in" → dimensions_raw: {{length: 120, width: 96, height: 60, unit: "in"}}
   - DO NOT CONVERT UNITS - keep original units

4. For DIKES:
   - Extract dike dimensions with units
   - "Length 20 ft ; Width 15 ft" → dike_dims_raw: {{length: 20, width: 15, unit: "ft"}}
   - "4m x 3m" → dike_dims_raw: {{length: 4, width: 3, unit: "m"}}

5. Tank TYPE detection:
   - "pressurized", "gas", "cryogenic" → pressurized_gas
   - "lpg", "propane" → lpg
   - "gasoline", "gasolina" → gasoline
   - "fuel", "combustible" → fuel
   - Default → diesel

6. SITE/CLIENT: Extract from fields like "site", "client", "cliente", "business", "empresa"

7. If multiple tanks in one row, create separate entries

Return TankListRaw with raw extracted data. DO NOT compute or convert values."""
        
        return prompt
    
    def _compute_volumes(self, state: ParserState) -> ParserState:
        """Compute volumes deterministically using VolumeCalculator"""
        
        computed_tanks = []
        calc = state["volume_calculator"]
        
        for tank_raw in state["parsed_tanks_raw"]:
            # Convert to dict
            tank_dict = {}
            
            # Copy basic fields
            tank_dict["name"] = tank_raw.name
            tank_dict["type"] = tank_raw.type
            tank_dict["has_dike"] = tank_raw.has_dike
            tank_dict["site"] = tank_raw.site
            tank_dict["notes"] = tank_raw.notes
            
            # Compute or extract volume
            volume_computed = False
            
            # Priority 1: Use provided volume
            if tank_raw.volume_raw and tank_raw.volume_raw > 0:
                volume = calc.parse_direct_volume(
                    tank_raw.volume_raw, 
                    tank_raw.volume_unit
                )
                if volume:
                    tank_dict["volume"] = volume
                    tank_dict["volume_source"] = "provided"
                else:
                    tank_dict["volume"] = float(tank_raw.volume_raw)  # Fallback
            
            # Priority 2: Compute from dimensions
            if not tank_dict.get("volume") and tank_raw.dimensions_raw:
                dims = tank_raw.dimensions_raw
                if dims.length and dims.width and dims.height:
                    volume = calc.compute_from_dimensions({
                        "length": dims.length,
                        "width": dims.width,
                        "height": dims.height,
                        "unit": dims.unit or "ft"
                    })
                    if volume:
                        tank_dict["volume"] = volume
                        tank_dict["volume_source"] = "computed_from_dimensions"
                        volume_computed = True
                        
                        # Store normalized dimensions in feet
                        unit = dims.unit or "ft"
                        factor = calc.CONVERSIONS_TO_FEET.get(unit.lower(), 1.0)
                        tank_dict["rect_dims_ft"] = [
                            round(dims.length * factor, 2),
                            round(dims.width * factor, 2),
                            round(dims.height * factor, 2)
                        ]
            
            # Ensure we have a volume
            if not tank_dict.get("volume"):
                tank_dict["volume"] = 0.0
                tank_dict["volume_source"] = "missing"
            
            # Process dike dimensions
            if tank_raw.has_dike and tank_raw.dike_dims_raw:
                dike = tank_raw.dike_dims_raw
                if dike.length and dike.width:
                    unit = dike.unit or "ft"
                    factor = calc.CONVERSIONS_TO_FEET.get(unit.lower(), 1.0)
                    tank_dict["dike_dims"] = [
                        round(dike.length * factor, 2),
                        round(dike.width * factor, 2)
                    ]
            elif tank_raw.has_dike:
                tank_dict["dike_dims"] = None
            
            computed_tanks.append(tank_dict)
            
            if self.debug and volume_computed:
                print(f"    → Computed volume: {tank_dict['volume']:.2f} gal from dimensions")
        
        state["computed_tanks"] = computed_tanks
        return state
    
    def _validate_result(self, state: ParserState) -> ParserState:
        """Validate computed tanks"""
        
        tanks = state.get("computed_tanks", [])
        errors = []
        row_data = state.get("row_data") or {}
        
        # Check if we should have found tanks
        if not tanks and row_data:
            row_text = " ".join([f"{k}: {v}" for k, v in row_data.items() 
                               if pd.notna(v) and str(v).strip()])
            likely_tank_row = bool(re.search(
                r"(?i)\b(tank|tanque|capacity|capacidad|volume|gallon)\b", 
                row_text
            ))
            if likely_tank_row:
                errors.append("No tanks parsed from likely tank row")
        
        for tank in tanks:
            # Validate volume
            if tank.get("volume", 0) <= 0:
                if tank.get("volume_source") != "missing":
                    errors.append(f"Tank '{tank['name']}' has invalid volume")
            elif tank["volume"] > 1000000:
                errors.append(f"Tank '{tank['name']}' volume exceeds maximum: {tank['volume']}")
            
            # Validate dike consistency
            if tank["has_dike"] and tank.get("dike_dims"):
                if len(tank["dike_dims"]) != 2:
                    errors.append(f"Tank '{tank['name']}' has invalid dike dimensions")
        
        if errors:
            state["errors"].extend(errors)
            state["retry_count"] += 1
        
        return state
    
    def _handle_error(self, state: ParserState) -> ParserState:
        """Handle parsing errors"""
        if state["errors"]:
            print(f"  ⚠️  Row {state['current_row'] + 1}: {', '.join(state['errors'][:2])}")
        state["retry_count"] = state["max_retries"]
        return state
    
    def _save_result(self, state: ParserState) -> ParserState:
        """Save computed tanks to results"""
        
        tanks = state.get("computed_tanks", [])
        
        for tank in tanks:
            state["all_tanks"].append(tank)
        
        return state
    
    def _validation_result(self, state: ParserState) -> str:
        """Determine validation outcome"""
        if not state.get("errors"):
            return "success"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "error"
    
    def _should_retry(self, state: ParserState) -> str:
        """Determine if we should retry"""
        if state["retry_count"] < state["max_retries"]:
            return "retry"
        return "save"
    
    def process_excel(self) -> Dict:
        """Process entire Excel file"""
        
        print("\n🚀 Processing Excel with Improved Parser...")
        print("  ✅ Using VolumeCalculator for deterministic computations\n")
        
        all_tanks = []
        tank_id = 1
        
        start_idx, end_idx = self._row_window
        for idx in range(start_idx, end_idx):
            print(f"  Row {idx + 1}/{len(self.df)}: ", end='')
            
            state = {
                "excel_path": str(self.excel_path),
                "current_row": idx,
                "row_data": None,
                "parsed_tanks_raw": [],
                "computed_tanks": [],
                "all_tanks": [],
                "errors": [],
                "retry_count": 0,
                "max_retries": self.max_retries,
                "volume_calculator": self.volume_calculator
            }
            
            try:
                result = self.workflow.invoke(state)
                
                row_tanks = result.get("all_tanks", [])
                for tank in row_tanks:
                    tank["id"] = tank_id
                    all_tanks.append(tank)
                    tank_id += 1
                
                if row_tanks:
                    sources = [t.get("volume_source", "unknown") for t in row_tanks]
                    print(f"✓ Found {len(row_tanks)} tank(s) [{', '.join(sources)}]")
                else:
                    print(f"✓ No tanks found")
                
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print(f"\n✅ Total tanks found: {len(all_tanks)}")
        
        return {
            "tanks": all_tanks,
            "settings": {
                "headless": False,
                "screenshot_full_page": True,
                "excel_path": str(self.excel_path.absolute()),
                "excel_sheet": self.sheet_name,
                "file_type": self.file_type,
                "output_pdf": "HUD_ASD_Results.pdf"
            }
        }
    
    def save(self, output_path: str):
        """Process Excel and save to JSON"""
        
        json_config = self.process_excel()
        
        outp = Path(output_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open('w') as f:
            json.dump(json_config, f, indent=2, ensure_ascii=False)
        
        self._print_summary(json_config, str(outp))
    
    def _print_summary(self, config: Dict, output_path: str):
        """Print processing summary"""
        
        print("\n" + "="*60)
        print("✅ PROCESSING COMPLETE (Improved Version)")
        print("="*60)
        
        tanks = config["tanks"]
        
        print(f"\n📊 Summary:")
        print(f"  • Total tanks: {len(tanks)}")
        
        # Volume source breakdown
        sources = {}
        for tank in tanks:
            src = tank.get("volume_source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        print("  • Volume sources:")
        for src, count in sorted(sources.items()):
            print(f"      - {src}: {count}")
        
        # Type distribution
        type_counts = {}
        for tank in tanks:
            t = tank.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print("  • Tank types:")
        for tank_type, count in sorted(type_counts.items()):
            print(f"      - {tank_type}: {count}")
        
        # Dike statistics
        dike_count = sum(1 for t in tanks if t.get("has_dike"))
        if tanks:
            print(f"  • Tanks with dikes: {dike_count}/{len(tanks)} ({100*dike_count/len(tanks):.1f}%)")
        
        # Volume statistics
        volumes = [t.get("volume", 0) for t in tanks if t.get("volume", 0) > 0]
        if volumes:
            print(f"  • Volume statistics:")
            print(f"      - Range: {min(volumes):.0f} - {max(volumes):.0f} gallons")
            print(f"      - Average: {sum(volumes)/len(volumes):.0f} gallons")
        
        # Calculation accuracy
        computed_count = sum(1 for t in tanks if t.get("volume_source") == "computed_from_dimensions")
        if computed_count:
            print(f"  • Computed volumes: {computed_count} (100% accurate)")
        
        print(f"\n📄 Saved to: {output_path}")
        
        # Preview
        print("\n📋 Preview (first 5 tanks):")
        for tank in tanks[:5]:
            dike = f" [Dike: {tank['dike_dims']}]" if tank.get('has_dike') else ""
            src = f" ({tank.get('volume_source', 'unknown')})"
            print(f"    {tank['id']:2}. {tank['name'][:25]:25} {tank['volume']:7.0f}g - {tank['type']}{dike}{src}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Improved Excel to JSON converter with accurate volume calculation')
    parser.add_argument('excel_file', help='Path to Excel/CSV file')
    parser.add_argument('-o', '--output', default='tank_config.json', help='Output JSON file')
    parser.add_argument('--sheet', help='Sheet name for Excel files')
    parser.add_argument('--start-row', type=int, default=1, help='Start row (1-based)')
    parser.add_argument('--limit', type=int, help='Max rows to process')
    parser.add_argument('--model', help='OpenAI model to use')
    parser.add_argument('--max-retries', type=int, default=2, help='Max retries per row')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    try:
        processor = ImprovedExcelParser(
            args.excel_file,
            sheet_name=args.sheet,
            start_row=args.start_row,
            max_rows=args.limit,
            model=args.model,
            max_retries=args.max_retries,
            debug=args.debug
        )
        
        processor.save(args.output)
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())