# HUD Tools - Isolated Pipeline

## Overview

This directory contains isolated, self-contained tools for processing Excel files through the HUD (Housing and Urban Development) ASD/BPU calculator. The pipeline converts tank data from Excel format, processes it through the HUD website, captures screenshots, and updates the Excel with results.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
playwright install chromium

# Run the complete pipeline
python hud_pipeline.py path/to/your/excel.xlsx
```

## 📁 Components

### Main Pipeline
- **`hud_pipeline.py`** - Main orchestrator that runs all steps sequentially

### Individual Tools
1. **`excel_to_json_improved.py`** - Converts Excel to JSON format
2. **`fast_hud_processor.py`** - Processes tanks through HUD website
3. **`generate_pdf.py`** - Merges screenshots into PDF report
4. **`update_excel_with_results.py`** - Updates Excel with HUD results

### Supporting Modules
- **`volume_calculator.py`** - Calculates tank volumes from dimensions
- **`tank_volume_calculator.py`** - Alternative volume calculation methods

## 📊 Input Excel Format

Your Excel file should contain the following columns:

### Required Columns
- **Tank Name/ID** - Unique identifier for each tank
- **Tank Dimensions** or **Tank Capacity** - Either dimensions (e.g., "10 x 20 ft") or volume (e.g., "50000 gal")

### Optional Columns
- **Type** - Tank type (diesel, gasoline, lpg, etc.)
- **Has Dike** - Whether tank has containment (Yes/No)
- **Dike Dimensions** - Containment dimensions if applicable
- **Location** - Tank location coordinates

### Example Excel Structure
```
| Tank ID | Tank Dimensions | Tank Capacity | Type   | Has Dike |
|---------|----------------|---------------|--------|----------|
| T-01    | 10 x 20 ft     |               | Diesel | Yes      |
| T-02    |                | 50000 gal     | LPG    | No       |
```

## 🔧 Individual Tool Usage

### 1. Convert Excel to JSON
```bash
python excel_to_json_improved.py input.xlsx -o tank_config.json
```

### 2. Process through HUD
```bash
python fast_hud_processor.py --config tank_config.json
```

### 3. Generate PDF Report
```bash
python generate_pdf.py -d .playwright-mcp -o HUD_Results.pdf --summary
```

### 4. Update Excel with Results
```bash
python update_excel_with_results.py original.xlsx fast_results.json -o updated.xlsx
```

## 📤 Output Files

After running the pipeline, you'll find:

```
hud_output_[timestamp]/
├── tank_config.json        # Converted tank data
├── hud_results.json        # HUD processing results
├── HUD_Results.pdf         # Combined screenshots report
└── Updated_Excel_with_HUD.xlsx  # Excel with ASD/BPU values
```

### Output Excel Columns Added
- **ASD PPU** - Allowable Stress Design (lbs per sq ft)
- **ASD BPU** - Allowable Stress Design for buried tanks
- **Processing Status** - Success/Error status
- **Processing Notes** - Any warnings or issues

## ⚙️ Configuration

### Environment Variables (Optional)
Create a `.env` file for API keys:
```bash
OPENAI_API_KEY=your_key_here  # For enhanced parsing (optional)
```

### Playwright Settings
The HUD processor uses Playwright with these defaults:
- Browser: Chromium (headless)
- Timeout: 60 seconds per tank
- Screenshot: Captured for each tank

## 🛠️ Troubleshooting

### Common Issues

1. **"Playwright browsers not installed"**
   ```bash
   playwright install chromium
   ```

2. **"Module not found" errors**
   ```bash
   pip install -r requirements.txt
   ```

3. **HUD website timeout**
   - Check internet connection
   - HUD website may be down
   - Try reducing batch size

4. **Excel parsing errors**
   - Ensure column names match expected format
   - Check for empty rows/columns
   - Verify tank dimensions format

## 📝 Advanced Usage

### Custom Output Directory
```bash
python hud_pipeline.py input.xlsx -o custom_output_dir
```

### Processing Specific Sheets
```python
# In excel_to_json_improved.py
python excel_to_json_improved.py input.xlsx --sheet "Sheet2"
```

### Batch Processing
```bash
# Process multiple Excel files
for file in *.xlsx; do
    python hud_pipeline.py "$file" -o "output_${file%.xlsx}"
done
```

## 🔄 Pipeline Flow

```
Excel Input
    ↓
[1. Excel → JSON Conversion]
    - Parse tank data
    - Calculate volumes
    - Validate data
    ↓
[2. HUD Processing]
    - Submit to HUD website
    - Capture screenshots
    - Extract ASD/BPU values
    ↓
[3. PDF Generation]
    - Merge screenshots
    - Add summary page
    ↓
[4. Excel Update]
    - Add HUD results
    - Mark compliance
    ↓
Output Files
```

## 📋 Requirements

### System Requirements
- Python 3.8+
- 4GB RAM minimum
- Internet connection (for HUD access)

### Python Packages
See `requirements.txt` for full list:
- pandas (Excel processing)
- playwright (Web automation)
- Pillow (Image/PDF handling)
- pydantic (Data validation)

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section
2. Review error messages in console output
3. Verify input Excel format matches requirements

## 🤖 AI Agent Integration

### New AI-Adjustable Excel Parser

The directory now includes an AI agent-adjustable version of the Excel parser that allows intelligent data processing with corrections and adjustments.

### AI Agent Tools

#### 1. **excel_to_json_agent_tool.py**
AI-adjustable Excel parser with multiple modes:
- **Auto Mode**: Automatic column detection
- **Strict Mode**: Requires exact column matches
- **Fuzzy Mode**: Approximate column matching
- **Manual Mode**: Explicit column mappings
- **AI-Guided Mode**: Intelligent processing with hints

```python
from excel_to_json_agent_tool import parse_excel_with_adjustments

# AI agent can adjust parsing
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="ai_guided",
    column_overrides={"tank_id": "Tank Number"},
    value_corrections=[
        {"tank_id": "T-001", "field": "capacity", "value": 50000}
    ],
    parsing_hints={"units": "gallons", "default_type": "diesel"}
)
```

#### 2. **hud_pipeline_with_agent.py**
Enhanced pipeline with AI capabilities:

```bash
# Run with AI assistance
python hud_pipeline_with_agent.py tanks.xlsx --mode ai_guided

# Interactive mode
python hud_pipeline_with_agent.py tanks.xlsx --interactive

# With corrections file
python hud_pipeline_with_agent.py tanks.xlsx --corrections fixes.json
```

#### 3. **example_agent_usage.py**
Demonstrates AI agent capabilities:

```bash
# Run demonstration
python example_agent_usage.py

# Process specific file
python example_agent_usage.py your_excel.xlsx
```

### AI Agent Features

1. **Automatic Column Detection**
   - Identifies tank data columns automatically
   - Handles multiple languages (English/Spanish)
   - Fuzzy matching for non-standard names

2. **Data Corrections**
   - Fix missing capacities
   - Correct tank types
   - Add calculated values
   - Validate data consistency

3. **Interactive Processing**
   - Agent asks for clarification
   - User can provide mappings
   - Real-time corrections

4. **Batch Learning**
   - Learn from successful parsings
   - Apply learned patterns to new files
   - Improve accuracy over time

### AI Agent Workflow

```
Excel File
    ↓
[AI Analysis & Suggestions]
    ↓
[Parsing with Selected Mode]
    ↓
[Apply Corrections if Needed]
    ↓
[Volume Calculations]
    ↓
[Data Validation]
    ↓
[Format for HUD Tool]
    ↓
JSON Output
```

### Example: AI-Guided Processing

```python
# Create agent
from example_agent_usage import ExcelProcessingAgent

agent = ExcelProcessingAgent()

# Process with AI guidance
result = agent.process_with_ai_guidance("tanks.xlsx")

# Interactive correction
result = agent.interactive_correction_session("tanks.xlsx")
```

### Corrections File Format

Create a `corrections.json` file:
```json
[
  {
    "tank_id": "T-001",
    "field": "capacity",
    "value": 50000
  },
  {
    "tank_id": "T-002",
    "field": "type",
    "value": "diesel"
  }
]
```

### Column Mappings File

Create a `mappings.json` file:
```json
{
  "tank_id": "Código del Tanque",
  "dimensions": "Medidas",
  "capacity": "Capacidad",
  "type": "Tipo de Combustible",
  "has_dike": "Tiene Dique"
}
```

## 📄 License

This tool is provided as-is for processing tank data through the HUD ASD calculator.