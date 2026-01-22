# Excel to JSON Standalone Converter

## 🚀 Completely Isolated, Zero-Dependency Tool

The `excel_to_json_standalone.py` is a **fully self-contained** Excel to JSON converter that works without any external dependencies except `pandas`. All functionality is embedded directly in the single file.

## ✨ Key Features

### 100% Standalone
- **No external imports** - Volume calculator embedded
- **No dependency files** - Everything in one file
- **AI-adjustable** - Multiple parsing modes
- **Multi-language** - English/Spanish support built-in

### Embedded Components
1. **Volume Calculator** - Full tank volume calculations
2. **Fuzzy Matching** - Column detection algorithms
3. **Data Validation** - Type checking and corrections
4. **Multiple Parsers** - 5 different parsing strategies

## 📦 Installation

```bash
# Only requires pandas - nothing else!
pip install pandas openpyxl
```

## 🎯 Quick Start

### Basic Usage
```bash
# Auto mode (automatic detection)
python excel_to_json_standalone.py tanks.xlsx

# Output to specific file
python excel_to_json_standalone.py tanks.xlsx -o output.json

# Get suggestions
python excel_to_json_standalone.py tanks.xlsx --suggest
```

### Advanced Usage
```bash
# Fuzzy mode for non-standard columns
python excel_to_json_standalone.py tanks.xlsx -m fuzzy

# Specific sheet
python excel_to_json_standalone.py tanks.xlsx -s "Sheet2"

# With corrections file
python excel_to_json_standalone.py tanks.xlsx --corrections fixes.json

# With column mappings
python excel_to_json_standalone.py tanks.xlsx --mappings columns.json
```

## 🔧 Parsing Modes

### 1. **AUTO Mode** (Default)
Automatically detects columns and parses data
```python
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="auto"
)
```

### 2. **STRICT Mode**
Requires exact column name matches
```python
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="strict"
)
```

### 3. **FUZZY Mode**
Uses similarity matching for column detection
```python
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="fuzzy"
)
```

### 4. **MANUAL Mode**
Uses explicit column mappings only
```python
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="manual",
    column_overrides={
        "tank_id": "Tank Number",
        "capacity": "Volume (gallons)"
    }
)
```

### 5. **AI_GUIDED Mode**
Intelligent parsing with hints
```python
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="ai_guided",
    parsing_hints={
        "units": "gallons",
        "default_type": "diesel",
        "skip_rows": [0, 1]
    }
)
```

## 🔄 Python API Usage

### Import Functions
```python
from excel_to_json_standalone import (
    parse_excel_with_adjustments,
    save_json_output,
    suggest_corrections
)
```

### Parse Excel
```python
# Parse with adjustments
result = parse_excel_with_adjustments(
    excel_path="tanks.xlsx",
    mode="auto",
    sheet_name="Tanks",
    column_overrides={"tank_id": "ID"},
    value_corrections=[
        {"tank_id": "T-001", "field": "capacity", "value": 50000}
    ],
    parsing_hints={"units": "gallons"}
)

if result["success"]:
    print(f"Parsed {len(result['tanks'])} tanks")
```

### Get Suggestions
```python
# Analyze Excel for improvements
suggestions = suggest_corrections("tanks.xlsx")

if suggestions["success"]:
    print("Column mappings:", suggestions["column_mappings"])
    print("Data issues:", suggestions["data_issues"])
    print("Recommendations:", suggestions["recommendations"])
```

### Save Output
```python
# Save to JSON
save_result = save_json_output(result, "output.json")

if save_result["success"]:
    print(f"Saved {save_result['tank_count']} tanks")
```

## 📊 Input Excel Format

### Supported Column Names (Auto-Detected)

| Standard Field | Recognized Variations |
|---------------|----------------------|
| **tank_id** | tank id, id, tank, name, tank name, tank number |
| **dimensions** | dimensions, tank dimensions, size, medidas |
| **capacity** | capacity, volume, tank capacity, gallons |
| **type** | type, tank type, fuel type, fuel, product |
| **has_dike** | has dike, dike, containment, tiene dique |
| **location** | location, site, ubicacion, coordinates |

### Example Excel Structure
```
| Tank ID | Dimensions  | Capacity   | Type   | Has Dike |
|---------|------------|------------|--------|----------|
| T-001   | 10 x 20 ft |            | Diesel | Yes      |
| T-002   |            | 50000 gal  | LPG    | No       |
| T-003   | 15x30      |            | Fuel   | Y        |
```

## 🔢 Volume Calculations

### Supported Dimension Formats
- `10 x 20 ft` - Standard format
- `10x20` - Compact format
- `D:10 L:20` - Diameter/Length format
- `10' x 20'` - With feet symbols
- `10 ft x 20 ft` - Explicit units

### Supported Capacity Formats
- `50000 gal` - Gallons
- `1000 bbl` - Barrels (converted to gallons)
- `10000 L` - Liters (converted to gallons)
- `100 m3` - Cubic meters (converted to gallons)

## 📝 Corrections File Format

### corrections.json
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

### mappings.json
```json
{
  "tank_id": "Tank Number",
  "dimensions": "Size",
  "capacity": "Volume",
  "type": "Fuel Type",
  "has_dike": "Secondary Containment"
}
```

## 🧪 Testing

### Run Test Suite
```bash
# Run comprehensive tests
python test_standalone.py

# Test with your file
python test_standalone.py your_excel.xlsx
```

### Test Coverage
- ✅ Basic parsing (AUTO mode)
- ✅ Fuzzy column matching
- ✅ Manual mappings
- ✅ Value corrections
- ✅ AI-guided hints
- ✅ Suggestions analysis
- ✅ Volume calculations
- ✅ Spanish columns
- ✅ JSON output

## 🎯 Use Cases

### 1. Simple Conversion
```bash
python excel_to_json_standalone.py tanks.xlsx
```

### 2. Non-Standard Columns
```bash
python excel_to_json_standalone.py tanks.xlsx --mode fuzzy
```

### 3. Multi-Language Support
```python
# Spanish columns
mappings = {
    "tank_id": "Código del Tanque",
    "capacity": "Capacidad",
    "type": "Tipo de Combustible"
}
result = parse_excel_with_adjustments(
    "tanques.xlsx",
    mode="manual",
    column_overrides=mappings
)
```

### 4. Data Correction
```python
corrections = [
    {"tank_id": "T-001", "field": "capacity_raw", "value": "50000 gal"},
    {"tank_id": "T-002", "field": "has_dike", "value": True}
]
result = parse_excel_with_adjustments(
    "tanks.xlsx",
    value_corrections=corrections
)
```

## 📤 Output Format

### JSON Structure
```json
{
  "tanks": [
    {
      "name": "T-001",
      "capacity": 15708.0,
      "type": "diesel",
      "hasDike": true,
      "_metadata": {
        "volume_source": "calculated",
        "corrected": false
      }
    }
  ],
  "metadata": {
    "tank_count": 5,
    "parsing_mode": "auto",
    "timestamp": "2024-10-02T08:45:00"
  },
  "timestamp": "2024-10-02T08:45:00"
}
```

## 🛠️ Troubleshooting

### Common Issues

1. **No tanks parsed**
   - Check column names match expected patterns
   - Try `--suggest` to see detected columns
   - Use `--mode fuzzy` for loose matching

2. **Wrong volumes**
   - Verify dimension format (e.g., "10 x 20 ft")
   - Check units in capacity (gal/bbl/L)
   - Use corrections to override

3. **Column not detected**
   - Use `--mappings` with explicit mapping
   - Try fuzzy mode
   - Check for typos in column names

## 🚀 Integration Examples

### As a Module
```python
# In your code
from excel_to_json_standalone import parse_excel_with_adjustments

def process_tank_file(filepath):
    result = parse_excel_with_adjustments(filepath)
    if result["success"]:
        return result["tanks"]
    else:
        raise ValueError(result["error"])
```

### In a Pipeline
```bash
#!/bin/bash
# Convert Excel to JSON
python excel_to_json_standalone.py input.xlsx -o tank_config.json

# Use in HUD pipeline
python fast_hud_processor.py --config tank_config.json
```

### With AI Agent
```python
class TankAgent:
    def process_excel(self, file):
        # Try auto first
        result = parse_excel_with_adjustments(file, mode="auto")

        if not result["success"]:
            # Fall back to fuzzy
            result = parse_excel_with_adjustments(file, mode="fuzzy")

        # Apply corrections if needed
        if result["success"] and self.has_corrections:
            result = parse_excel_with_adjustments(
                file,
                value_corrections=self.corrections
            )

        return result
```

## 📄 License

Standalone tool provided as-is for Excel to JSON conversion.