#!/usr/bin/env python3
"""
LangGraph-based Excel to JSON Converter using OpenAI.
Requires OPENAI_API_KEY in the environment. No offline/dummy fallbacks.
"""

import json
import pandas as pd
from typing import Dict, List, Optional, Any, TypedDict
from pathlib import Path
import os
import re
import sys
from enum import Enum

# Pydantic for structured output
from pydantic import BaseModel, Field, field_validator
from typing_extensions import Annotated

# LangChain and LangGraph imports
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain.output_parsers import OutputFixingParser
    from langgraph.graph import StateGraph, END
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    print("Missing dependencies. Install with: pip install langchain langchain-openai langgraph pydantic")
    print(f"Error: {e}")


# ============= Pydantic Models for Structured Output =============

class TankType(str, Enum):
    """Valid tank types"""
    DIESEL = "diesel"
    PRESSURIZED_GAS = "pressurized_gas"
    LPG = "lpg"
    GASOLINE = "gasoline"
    FUEL = "fuel"


class Tank(BaseModel):
    """Single tank configuration"""
    name: str = Field(description="Tank or site name")
    volume: float = Field(description="Tank volume in gallons (numeric only)", ge=0)
    type: TankType = Field(default=TankType.DIESEL, description="Type of fuel/tank")
    has_dike: bool = Field(default=False, description="Whether tank has a dike/containment")
    dike_dims: Optional[List[float]] = Field(
        default=None,
        description="Dike dimensions [length, width] in feet if has_dike is true",
        min_items=2,
        max_items=2
    )
    # Optional fields for richer context
    site: Optional[str] = Field(default=None, description="Client/site/business this tank belongs to")
    rect_dims_ft: Optional[List[float]] = Field(
        default=None,
        description="Rectangular tank internal dimensions [L, W, H] in feet (if known)",
        min_items=3,
        max_items=3
    )
    notes: Optional[str] = Field(default=None, description="Additional notes or information")
    
    @field_validator('dike_dims', mode='after')
    @classmethod
    def validate_dike_dims(cls, v, info):
        """Ensure dike_dims is consistent with has_dike"""
        # In Pydantic V2, we access other field values differently
        if 'has_dike' in info.data:
            has_dike = info.data['has_dike']
            if has_dike and not v:
                return None  # OK to not have dimensions even with dike
            if not has_dike and v:
                return None  # Remove dimensions if no dike
        return v

    @field_validator('rect_dims_ft', mode='after')
    @classmethod
    def validate_rect_dims(cls, v):
        # Accept None or 3 non-negative numbers
        if v is None:
            return v
        try:
            vals = [float(x) for x in v]
        except Exception:
            return None
        if len(vals) != 3:
            return None
        if any(x <= 0 for x in vals):
            return None
        return vals
    
    model_config = {"use_enum_values": True}


class TankList(BaseModel):
    """List of tanks parsed from Excel row"""
    tanks: List[Tank] = Field(description="List of tanks extracted from the data")


class ParsedRow(BaseModel):
    """Result of parsing a single Excel row"""
    row_index: int
    original_data: Dict[str, Any]
    tanks: List[Tank]
    parse_errors: List[str] = Field(default_factory=list)
    
    model_config = {"arbitrary_types_allowed": True}


# ============= LangGraph State Definition =============

class ParserState(TypedDict):
    """State for the parsing workflow"""
    excel_path: str
    current_row: Optional[int]
    row_data: Optional[Dict[str, Any]]
    parsed_tanks: List[Tank]
    all_tanks: List[Dict]
    errors: List[str]
    retry_count: int
    max_retries: int


# ============= Excel Parser with LangGraph =============

class LangGraphExcelParser:
    """Excel to JSON parser using LangGraph and OpenAI"""
    
    def __init__(
        self,
        excel_path: str,
        *,
        sheet_name: Optional[str] = None,
        start_row: int = 1,
        max_rows: Optional[int] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
    ):
        """Initialize parser with Excel file. Requires OPENAI_API_KEY.

        Args:
            excel_path: Path to the Excel file.
            sheet_name: Optional sheet name to parse (default: first sheet).
            start_row: 1-based row index to start from (default: 1, i.e., first row).
            max_rows: Optional maximum number of rows to process.
            model: Optional model name override (default: env OPENAI_MODEL or 'gpt-4o-mini').
            max_retries: Max LLM retries per row during validation.
        """

        if not IMPORTS_AVAILABLE:
            raise ImportError("Required packages not installed. Run: pip install langchain langchain-openai langgraph pydantic")

        self.excel_path = Path(excel_path)
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Configuration
        self.sheet_name = sheet_name
        # convert provided 1-based row index to 0-based for internal use
        self.start_row = max(1, int(start_row)) - 1
        self.max_rows = int(max_rows) if max_rows is not None else None
        self.max_retries = int(max_retries)
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

        # Require OpenAI API key from environment only
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Please export it in your environment.")

        # Initialize LLM with structured output
        try:
            self.llm = ChatOpenAI(
                model=self.model,
                temperature=0,
            ).with_structured_output(TankList)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        
        # Load Excel data
        try:
            ext = self.excel_path.suffix.lower()
            if ext == '.csv':
                self.file_type = 'csv'
                try:
                    self.df = pd.read_csv(self.excel_path)
                    # Try alternate delimiter if everything ended up in one column
                    if self.df.shape[1] == 1:
                        self.df = pd.read_csv(self.excel_path, sep=';')
                except Exception as ce:
                    raise RuntimeError(f"Failed to read CSV file '{self.excel_path}': {ce}")
            else:
                self.file_type = 'excel'
                if self.sheet_name:
                    self.df = pd.read_excel(self.excel_path, sheet_name=self.sheet_name)
                else:
                    self.df = pd.read_excel(self.excel_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to read file '{self.excel_path}'{f' (sheet: {self.sheet_name})' if self.sheet_name and self.file_type=='excel' else ''}: {e}"
            )

        total_rows = len(self.df)
        # Compute processing window
        if self.max_rows is None:
            end_row = total_rows
        else:
            end_row = min(total_rows, self.start_row + self.max_rows)
        self._row_window = (self.start_row, end_row)

        print(
            f"✓ Loaded {total_rows} rows from {self.file_type.upper()}"
            + (f" (sheet: {self.sheet_name})" if self.file_type=='excel' and self.sheet_name else "")
        )
        if self.start_row > 0 or self.max_rows is not None:
            print(f"  → Processing rows {self.start_row + 1} to {end_row} (1-based)")
        print(f"  → Using model: {self.model}")
        
        # Build the workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for parsing"""
        
        # Create workflow
        workflow = StateGraph(ParserState)
        
        # Add nodes
        workflow.add_node("load_row", self._load_row)
        workflow.add_node("parse_with_llm", self._parse_with_llm)
        workflow.add_node("validate_result", self._validate_result)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("save_result", self._save_result)
        
        # Add edges
        workflow.set_entry_point("load_row")
        
        workflow.add_edge("load_row", "parse_with_llm")
        
        workflow.add_conditional_edges(
            "parse_with_llm",
            self._should_validate,
            {
                "validate": "validate_result",
                "error": "handle_error"
            }
        )
        
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
            state["row_data"] = row_data
            state["retry_count"] = 0
        
        return state
    
    def _parse_with_llm(self, state: ParserState) -> ParserState:
        """Parse row data using LLM with structured output"""
        
        row_data = state["row_data"]
        
        # Create parsing prompt
        prompt = self._create_parsing_prompt(row_data)
        
        try:
            # Get structured output directly from LLM
            result = self.llm.invoke(prompt)
            if isinstance(result, TankList):
                state["parsed_tanks"] = result.tanks
                state["errors"] = []
            else:
                state["parsed_tanks"] = []
                state["errors"] = ["Invalid structured output from LLM"]
        except Exception as e:
            state["parsed_tanks"] = []
            state["errors"] = [f"LLM error: {e}"]
        
        return state
    
    def _create_parsing_prompt(self, row_data: Dict[str, Any]) -> str:
        """Create an optimized prompt for parsing"""
        
        # Format row data clearly
        formatted_data = []
        for key, value in row_data.items():
            if pd.notna(value) and str(value).strip():
                # Clean up column names
                clean_key = key.strip().replace('  ', ' ')
                formatted_data.append(f"{clean_key}: {value}")
        
        data_text = "\n".join(formatted_data)
        
        prompt = f"""You are extracting tank details from a single table row.
The table may come from Excel or CSV and headers may vary or be in Spanish.
Infer meaning from both headers and cell contents. Focus on tank info.

DATA:
{data_text}

PARSING RULES:
1. Extract all tanks (there may be multiple per row)
2. Volume/capacity synonyms: "tank capacity", "capacity", "capacidad", "volumen", "volume (gal)", "galones".
3. Measurements: Detect rectangular dimensions from formats like:
   - "Length 4 ft ; Width 3 ft ; Height 5 ft"
   - "4ft x 3.5ft x 5ft", "4 x 3.5 x 5 ft", "120in x 40in x 60in"
   - Spanish keywords: "largo", "ancho", "alto"/"altura".
   Convert to feet if needed (1 in = 1/12 ft, 1 m = 3.28084 ft, 1 cm = 0.0328084 ft).
4. If gallons are not provided, compute from rectangular dimensions using 1 ft^3 = 7.48052 gal.
5. Dike patterns:
   - "Length 4 ft ; Width 4 ft" → dike_dims: [4, 4]
   - "5 ft x 3.5 ft" → dike_dims: [5, 3.5]
   - Empty/NaN → has_dike: false
6. Tank type detection:
   - Contains "pressurized", "gas", "cryogenic" → pressurized_gas
   - Contains "lpg", "propane" → lpg
   - Otherwise default to diesel
7. Site/client/business: Capture from fields like "site", "client", "business", "company", "owner",
   or Spanish equivalents like "cliente", "negocio", "empresa". Put it in the 'site' field.
8. If site has multiple tanks in a single row, name them "<Site> Tank 1", "<Site> Tank 2", etc.
9. Output JSON must strictly follow the TankList schema. Fill 'rect_dims_ft' whenever you used rectangular dimensions.

Extract tanks following the schema exactly. Be precise with numeric values."""
        
        return prompt

    
    def _validate_result(self, state: ParserState) -> ParserState:
        """Validate parsed tanks"""
        
        tanks = state.get("parsed_tanks", [])
        errors = []
        row_data = state.get("row_data") or {}

        # Helper: try to compute volume from rect_dims_ft if missing
        def _compute_volume_from_dims(rect_dims_ft: Optional[List[float]]) -> Optional[float]:
            if not rect_dims_ft or len(rect_dims_ft) != 3:
                return None
            try:
                L, W, H = [float(x) for x in rect_dims_ft]
                if L > 0 and W > 0 and H > 0:
                    return L * W * H * 7.48052
            except Exception:
                return None
            return None

        # If no tanks parsed but the row looks like it contains tank data, flag for retry
        row_text = " ".join([f"{k}: {v}" for k, v in row_data.items() if pd.notna(v) and str(v).strip()])
        likely_tank_row = bool(re.search(r"(?i)\b(tank|tanque|capacity|capacidad|volume|volumen|gal|gallon|galon|galones)\b", row_text))
        if not tanks and likely_tank_row:
            errors.append("No tanks parsed from likely tank row")
        
        for tank in tanks:
            # Check for reasonable volume
            if tank.volume < 0:
                errors.append(f"Tank '{tank.name}' has negative volume")
            elif tank.volume > 100000:
                errors.append(f"Tank '{tank.name}' volume seems too large: {tank.volume}")
            
            # Check dike consistency
            if tank.has_dike and tank.dike_dims:
                if len(tank.dike_dims) != 2:
                    errors.append(f"Tank '{tank.name}' has invalid dike dimensions")

            # If volume missing or zero, try to compute from rect_dims_ft
            if (tank.volume is None or float(tank.volume) == 0.0) and getattr(tank, "rect_dims_ft", None):
                vol = _compute_volume_from_dims(getattr(tank, "rect_dims_ft", None))
                if vol:
                    try:
                        tank.volume = float(vol)
                    except Exception:
                        pass
                else:
                    errors.append(f"Tank '{tank.name}' has dimensions but volume could not be computed")
        
        if errors:
            state["errors"].extend(errors)
            state["retry_count"] += 1
        
        return state
    
    def _handle_error(self, state: ParserState) -> ParserState:
        """Handle parsing errors"""
        
        print(f"  ⚠️  Row {state['current_row'] + 1}: {', '.join(state['errors'][:2])}")
        # No fallback parsing; cap retries and proceed (no tanks for this row)
        state["retry_count"] = state["max_retries"]

        return state
    
    def _save_result(self, state: ParserState) -> ParserState:
        """Save parsed tanks to results"""
        
        tanks = state.get("parsed_tanks", [])
        
        for tank in tanks:
            # Convert to dict and add to all_tanks
            tank_dict = tank.model_dump(exclude_none=True)
            state["all_tanks"].append(tank_dict)
        
        return state
    
    # Conditional edge functions
    def _should_validate(self, state: ParserState) -> str:
        """Determine if we should validate or handle error"""
        if state.get("errors"):
            return "error"
        return "validate"
    
    def _validation_result(self, state: ParserState) -> str:
        """Determine validation outcome"""
        if not state.get("errors"):
            return "success"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "error"
    
    def _should_retry(self, state: ParserState) -> str:
        """Determine if we should retry or save"""
        if state["retry_count"] < state["max_retries"]:
            return "retry"
        return "save"
    
    def process_excel(self) -> Dict:
        """Process entire Excel file"""
        
        print("\n🚀 Processing Excel with LangGraph + OpenAI...")
        
        all_tanks = []
        tank_id = 1
        
        # Process each row
        start_idx, end_idx = self._row_window
        for idx in range(start_idx, end_idx):
            print(f"  Row {idx + 1}/{len(self.df)}: ", end='')
            
            # Initialize state for this row
            state = {
                "excel_path": str(self.excel_path),
                "current_row": idx,
                "row_data": None,
                "parsed_tanks": [],
                "all_tanks": [],
                "errors": [],
                "retry_count": 0,
                "max_retries": self.max_retries
            }
            
            # Run workflow
            try:
                result = self.workflow.invoke(state)
                
                # Add tanks with IDs
                row_tanks = result.get("all_tanks", [])
                for tank in row_tanks:
                    tank["id"] = tank_id
                    all_tanks.append(tank)
                    tank_id += 1
                
                print(f"✓ Found {len(row_tanks)} tank(s)")
                
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print(f"\n✅ Total tanks found: {len(all_tanks)}")
        
        # Create final JSON structure
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
        
        # Save to file (ensure parent exists)
        outp = Path(output_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open('w') as f:
            json.dump(json_config, f, indent=2, ensure_ascii=False)
        
        # Print summary
        self._print_summary(json_config, str(outp))
    
    def _print_summary(self, config: Dict, output_path: str):
        """Print processing summary"""
        
        print("\n" + "="*60)
        print("✅ LANGGRAPH PROCESSING COMPLETE")
        print("="*60)
        
        tanks = config["tanks"]
        
        print(f"\n📊 Summary:")
        print(f"  • Total tanks: {len(tanks)}")
        
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
        
        print(f"\n📄 Saved to: {output_path}")
        
        # Preview
        print("\n📋 Preview (first 5 tanks):")
        for tank in tanks[:5]:
            dike = f" [Dike: {tank['dike_dims']}]" if tank.get('has_dike') else ""
            print(f"    {tank['id']:2}. {tank['name'][:30]:30} {tank['volume']:7.0f}g - {tank['type']}{dike}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="LangGraph-based Excel to JSON converter using OpenAI"
    )
    parser.add_argument('excel_file', help='Path to Excel file')
    parser.add_argument('-o', '--output', default='tank_config_langgraph.json',
                       help='Output JSON file (creates parent dir if needed)')
    parser.add_argument('-s', '--sheet', default=None,
                       help='Excel sheet name to parse (default: first sheet)')
    parser.add_argument('--start-row', type=int, default=1,
                       help='1-based row to start processing from (default: 1)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Max number of rows to process (default: all)')
    parser.add_argument('--model', default=None,
                       help='LLM model name override (default: env OPENAI_MODEL or gpt-4o-mini)')
    parser.add_argument('--max-retries', type=int, default=2,
                       help='Max validation retries per row (default: 2)')
    # API key must be provided via environment only
    
    args = parser.parse_args()
    
    if not Path(args.excel_file).exists():
        print(f"❌ File not found: {args.excel_file}")
        sys.exit(1)
    
    try:
        parser = LangGraphExcelParser(
            args.excel_file,
            sheet_name=args.sheet,
            start_row=args.start_row,
            max_rows=args.limit,
            model=args.model,
            max_retries=args.max_retries,
        )
        parser.save(args.output)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
