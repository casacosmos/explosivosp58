# Unified Tank Compliance Pipeline Agent

## ONE Agent, TWO Modes

This is a **single unified agent** (`pipeline_agent.py`) that handles all tank compliance processing with both pipeline and chatbot capabilities.

## Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Pipeline Mode (Direct Processing)
```bash
# Process a KMZ file
python pipeline_agent.py tanks_juncos.kmz -o reports/

# Process an Excel file
python pipeline_agent.py JUNCOS_HUELLA_EXPLOSIVOS_SITES.xlsx

# Use session ID for persistence
python pipeline_agent.py tanks.csv --session my_session_001
```

### Chat Mode (Interactive)
```bash
# Start interactive chat
python pipeline_agent.py --chat

# Then use commands like:
# > process /path/to/file.kmz
# > create template with 10 tanks
# > help
# > exit
```

## Architecture

**ONE UNIFIED AGENT** with:

1. **11 Core Tools** (all in `pipeline_agent.py`):
   - `parse_kmz_tool` - Parse KMZ files
   - `excel_to_json_tool` - Convert Excel to JSON
   - `validate_json_tool` - Validate JSON structure
   - `process_hud_tool` - Fetch HUD data with Playwright
   - `generate_pdf_tool` - Merge screenshots into PDF
   - `update_excel_tool` - Update Excel with HUD results
   - `calculate_distances_tool` - Calculate boundary distances
   - `check_compliance_tool` - Determine compliance status
   - `create_output_kmz_tool` - Generate final KMZ
   - `calculate_volume_tool` - Convert measurements to volumes
   - `human_approval_tool` - Request human review

2. **State Management** using TypedDict:
   ```python
   class PipelineState(TypedDict):
       messages: List[BaseMessage]
       input_file: str
       output_dir: str
       # ... other state fields
   ```

3. **LangGraph Integration**:
   - StateGraph for orchestration
   - MemorySaver for persistence
   - Thread-based conversation tracking

4. **Two Entry Points**:
   - `run_pipeline_agent()` - Direct pipeline execution
   - `run_chatbot()` - Interactive chat interface

## Complete Workflow

1. **Parse Input** → KMZ/Excel with multi-sheet support
2. **Convert to JSON** → Structured tank data
3. **Process with HUD** → Fetch data + screenshots
4. **Generate PDF** → Single PDF with all screenshots
5. **Update Excel** → Add HUD results
6. **Calculate Distances** → Boundary analysis
7. **Check Compliance** → Determine status
8. **Create Output KMZ** → Final visualization

## Files Generated

- `tank_config.json` - Structured tank data
- `fast_results.json` - HUD processing results
- `HUD_ASD_Results.pdf` - Merged screenshots
- `with_hud.xlsx` - Updated Excel
- `final_compliance.xlsx` - Compliance report
- `tanks_output.kmz` - Final KMZ with labels

## Why One Agent?

- **Simplicity**: Single codebase to maintain
- **Consistency**: Same tools and logic in both modes
- **Flexibility**: Use as CLI tool or interactive chat
- **Integration**: All components work together seamlessly
- **Memory**: Thread-based persistence across sessions

## Notes

- Virtual environment required (externally managed system)
- All dependencies in `requirements.txt`
- Advanced parsers in supporting files:
  - `enhanced_excel_parser.py` - Multi-sheet Excel
  - `create_professional_kmz.py` - Styled KMZ output