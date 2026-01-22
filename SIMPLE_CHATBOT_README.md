# Simple Pipeline Chatbot

**A straightforward conversational interface for tank processing - no complex session management!**

---

## Why This Approach?

The original chatbot had unnecessary complexity with session tracking, status checking, and multiple management tools. This simplified version focuses on what matters: **processing tanks and creating compliance reports**.

### What Changed

- ❌ **Removed:** Session management, status tracking, multiple tools for checking progress
- ✅ **Added:** Simple `process_file` command that does everything
- ✅ **Added:** Conversational Excel filling for KMZ workflows
- ✅ **Added:** Output KMZ generation with labeled tank locations

---

## Quick Start

```bash
# Run the chatbot
python simple_chatbot.py

# Example interaction
You: help
Bot: [Shows available commands]

You: Process tanks.kmz
Bot: [Runs complete pipeline, creates all outputs including labeled KMZ]

You: Create template for 24 tanks
Bot: [Creates blank Excel template]
```

---

## Complete Pipeline Workflow

```
1. User provides KMZ/Excel OR asks for template
   ↓
2. Parse file (KMZ → Excel template, Excel → validate)
   ↓
3. Convert measurements → Calculate volumes → Generate JSON
   ↓
4. Use HUD tool with Playwright → Retrieve data + take screenshots
   ↓
5. Update Excel with HUD results
   ↓
6. Calculate distances to boundaries
   ↓
7. Determine compliance (YES/NO/REVIEW)
   ↓
8. Create output KMZ with tank locations labeled by capacities ← NEW!
   ↓
9. Generate final reports
```

---

## Available Tools

### 1. `process_file_tool`
**Processes a KMZ or Excel file through the complete pipeline.**

```python
You: Process tanks.kmz
Bot: [Executes all 9 steps automatically]
```

**What it does:**
- Parses input file
- Converts measurements to volumes
- Creates structured JSON
- Runs HUD queries with Playwright (takes screenshots)
- Updates Excel with HUD data
- Calculates boundary distances
- Determines compliance
- **Creates output KMZ with labeled tank locations**
- Generates final reports

**Outputs (in `outputs/TIMESTAMP/`):**
- `tank_config.json` - Structured tank data
- `fast_results.json` - HUD query results
- `HUD_ASD_Results.pdf` - Screenshots from HUD
- `with_hud.xlsx` - Excel with HUD data
- `distances.json` - Boundary distance calculations
- `final_compliance.xlsx` - Compliance report
- **`tanks_output.kmz` - Google Earth file with labeled tanks** ← NEW!

---

### 2. `fill_tank_data_tool`
**Fill Excel template conversationally without manual editing.**

```python
You: Tank T-01 has capacity 50000 gallons, dimensions 30ft x 20ft x 15ft, stores Diesel
Bot: [Fills Excel template with provided data]
```

**Use case:** When processing KMZ files that create Excel templates, you can provide tank details through chat instead of manually editing the Excel.

---

### 3. `create_template_tool`
**Create blank Excel template for manual data entry.**

```python
You: Create template for 10 tanks
Bot: [Creates Excel with 10 blank rows]
```

**Use case:** When you don't have a KMZ file but want to start entering tank data.

---

### 4. `help_tool`
**Get help and instructions.**

```python
You: help
Bot: [Displays available commands and workflow]
```

---

## Output KMZ Features

The new `tanks_output.kmz` file includes:

### Visual Markers
- **Green pins** = Compliant tanks (YES)
- **Red pins** = Non-compliant tanks (NO)
- **Yellow pins** = Needs review (REVIEW)

### Tank Labels
Each tank is labeled with: `Tank ID (Capacity)`

Example: `T-01 (50000)`

### Popup Information
Click any tank marker to see:
- Tank ID
- Capacity
- Product stored
- Compliance status (color-coded)

### Google Earth Integration
- Open `tanks_output.kmz` in Google Earth
- Fly to tank locations
- View satellite imagery
- Measure distances
- Export to other GIS tools

---

## Example Conversations

### Processing a KMZ File

```
You: Process tanks_juncos.kmz
Bot: Starting pipeline...
     ✓ Parsing KMZ file...
     ✓ Creating Excel template...
     ✓ Converting to JSON...
     ✓ Running HUD queries... (this takes 6-8 minutes)
     ✓ Generating PDF with screenshots...
     ✓ Updating Excel with HUD results...
     ✓ Calculating distances...
     ✓ Checking compliance...
     ✓ Creating output KMZ with labeled tanks...

     Pipeline completed! 24 tanks processed.

     Generated files in outputs/20250130_143022/:
     - Compliance Report: final_compliance.xlsx
     - PDF Report: HUD_ASD_Results.pdf
     - Output KMZ: tanks_output.kmz
```

### Conversational Data Entry

```
You: Create template for 3 tanks
Bot: Created template with 3 tank rows at tank_template.xlsx

You: Fill the template:
     Tank T-01: 50000 gallons, 30x20x15 ft, Diesel
     Tank T-02: 75000 gallons, 40x25x18 ft, Gasoline
     Tank T-03: 100000 gallons, 50x30x20 ft, Kerosene

Bot: Filled 3 tanks in Excel template.
     Ready to process! Use: Process tank_template.xlsx

You: Process tank_template.xlsx
Bot: [Runs complete pipeline]
```

---

## How It Works

### Architecture

```
User Input → LLM → Tool Selection → Pipeline Execution
                ↓                           ↓
         Natural Language           Complete Workflow
         Understanding              (9 automated steps)
                                          ↓
                                   Labeled KMZ Output
```

### Tool Selection Logic

The LLM automatically decides which tool to use based on your message:

| User Says | Tool Used |
|-----------|-----------|
| "Process tanks.kmz" | `process_file_tool` |
| "Create template for 10 tanks" | `create_template_tool` |
| "Tank T-01 has..." | `fill_tank_data_tool` |
| "help" | `help_tool` |

### Pipeline Integration

`process_file_tool` directly calls `run_pipeline_agent()` from `pipeline_agent.py`, ensuring:
- ✅ Identical execution to command-line usage
- ✅ Same outputs and artifacts
- ✅ Same error handling
- ✅ Same HUD processing with Playwright
- ✅ Now includes output KMZ generation

---

## Testing

```bash
# Run automated tests
python test_simple_chatbot.py

# Expected output:
✅ All imports successful
✅ Tools work correctly
✅ Graph created successfully
✅ Pipeline integration verified
```

---

## Comparison: Old vs New

### Old Chatbot (pipeline_chatbot.py)
- 800+ lines
- 5 tools (process, check_status, get_results, list_sessions, help)
- Complex session tracking
- Manual status checking
- No KMZ output

### New Chatbot (simple_chatbot.py)
- 350 lines
- 4 tools (process_file, fill_data, create_template, help)
- No session management
- Automatic execution
- **Output KMZ with labeled tanks**

**Result:** Simpler code, same functionality, better outputs!

---

## Technical Details

### Dependencies
- `langchain` - LLM integration
- `langchain-anthropic` - Claude models
- `langgraph` - Graph-based workflow
- `pandas` - Excel manipulation
- `openpyxl` - Excel file handling

### LLM Model
- Claude 3.5 Sonnet (latest)
- Optimal for tool selection and natural language understanding

### Memory
- Uses `MemorySaver` for conversation context
- Thread-based conversation tracking

---

## Files Created

### New Files
- `simple_chatbot.py` - Simplified chatbot implementation
- `create_output_kmz.py` - KMZ generation script
- `test_simple_chatbot.py` - Test suite
- `SIMPLE_CHATBOT_README.md` - This file

### Modified Files
- `pipeline_agent.py` - Added `create_output_kmz_node` and tool

---

## What's Next?

The chatbot now does exactly what you asked for:

1. ✅ Starts as chatbot
2. ✅ User provides KMZ/Excel or asks for template
3. ✅ Agent converts measurements → volumes → JSON
4. ✅ Uses HUD tool with Playwright to retrieve data + screenshots
5. ✅ Updates Excel with HUD data
6. ✅ Determines compliance
7. ✅ **Creates output KMZ with tank locations labeled by capacities**

**No unnecessary session management. Just pure functionality.**

---

## Running the Chatbot

```bash
# Activate environment
source .venv/bin/activate

# Run chatbot
python simple_chatbot.py

# Type 'help' for instructions
# Type 'quit' to exit
```

That's it! Simple, clean, and focused on the task. 🚀