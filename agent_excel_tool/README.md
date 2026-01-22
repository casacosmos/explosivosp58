# Agent Excel Tool - AI Decision-Based Conversion

## Overview

This tool provides Excel analysis capabilities where **the AI agent makes all decisions** about how to convert measurements to volumes. The tool analyzes and presents options - the agent decides.

## 🎯 Core Principle

**Tool Analyzes → Agent Decides → Tool Applies**

The tool NEVER makes decisions. It only:
1. Analyzes the Excel file
2. Identifies possibilities
3. Calculates options
4. Applies agent's decisions

## 📁 Files

- **`excel_analysis_tool.py`** - Main analysis tool (no decisions)
- **`agent_example.py`** - Example agent implementation
- **`test_with_agent.py`** - Test script showing agent workflow
- **`requirements.txt`** - Dependencies (just pandas)

## 🚀 Quick Start

### Basic Usage

```python
from excel_analysis_tool import analyze_excel_for_conversion, apply_conversion_decisions

# Step 1: Tool analyzes (no decisions)
analysis = analyze_excel_for_conversion("tanks.xlsx")

# Step 2: Agent makes decisions
decisions = []
for row in analysis["rows_analyzed"]:
    if row["has_data"]:
        # Agent decides here
        decision = {
            "row_index": row["row_index"],
            "tank_id": "T-001",  # Agent's choice
            "use_conversion": {...}  # Agent's choice
        }
        decisions.append(decision)

# Step 3: Tool applies agent's decisions
result = apply_conversion_decisions(analysis, decisions)
```

### Using Example Agent

```bash
# Run with example agent
python agent_example.py tanks.xlsx

# With confidence threshold
python agent_example.py tanks.xlsx high
python agent_example.py tanks.xlsx medium
python agent_example.py tanks.xlsx low
```

## 📊 What the Tool Provides

### Analysis Structure

```json
{
  "sheets_available": ["Tanks", "Data"],
  "recommended_sheet": "Tanks",
  "rows_analyzed": [
    {
      "row_index": 0,
      "has_data": true,
      "possible_tank_ids": [
        {
          "column": "Tank ID",
          "value": "T-001",
          "confidence": "high"
        }
      ],
      "conversion_possibilities": [
        {
          "column": "Dimensions",
          "raw_value": "10 x 20 ft",
          "possibilities": [
            {
              "method": "calculate_from_dimensions",
              "interpretation": "10 ft diameter x 20 ft length",
              "result_gallons": 11775,
              "confidence": "high",
              "formula_used": "π × r² × length × 7.48 gal/ft³"
            }
          ]
        }
      ]
    }
  ]
}
```

### Conversion Possibilities

The tool identifies multiple interpretation options:

1. **Dimension Calculations**
   - Pattern: "10 x 20 ft"
   - Method: `calculate_from_dimensions`
   - Provides: Volume in gallons
   - Confidence: high/medium/low

2. **Direct Volume**
   - Pattern: "50000 gal"
   - Method: `direct_gallons`
   - Provides: Direct value
   - Confidence: high if units present

3. **Barrel Conversion**
   - Pattern: "1000 bbl"
   - Method: `convert_from_barrels`
   - Provides: Gallons (× 42)
   - Confidence: high if units present

4. **Unknown/Ambiguous**
   - Pattern: Just numbers
   - Method: `unknown`
   - Provides: `needs_agent_decision: true`
   - Agent must decide

## 🤖 Agent Decision Structure

```python
decision = {
    "row_index": 0,                    # Which row
    "tank_id": "T-001",                # Agent's chosen ID
    "use_conversion": {                # Agent's chosen conversion
        "method": "calculate_from_dimensions",
        "result_gallons": 11775
    },
    "override_capacity": None,         # Agent can override
    "tank_type": "diesel",            # Agent's inference
    "has_dike": True,                 # Agent's decision
    "agent_reasoning": [              # Why agent decided
        "Selected high confidence ID",
        "Used dimension calculation"
    ]
}
```

## 🎯 Agent Decision Points

### 1. Tank ID Selection
```python
# Tool provides options
possible_ids = [
    {"value": "T-001", "confidence": "high"},
    {"value": "001", "confidence": "medium"}
]

# Agent decides
if high_confidence_exists:
    use_high_confidence_id()
else:
    generate_new_id()
```

### 2. Conversion Method Selection
```python
# Tool provides options
possibilities = [
    {"method": "calculate", "confidence": "high", "result": 11775},
    {"method": "direct", "confidence": "low", "result": 10000}
]

# Agent decides
if confidence == "high":
    use_conversion()
elif confidence == "medium" and looks_reasonable():
    use_with_warning()
else:
    ask_for_clarification()
```

### 3. Handling Ambiguous Data
```python
# Tool says: needs_agent_decision = true

# Agent decides based on context
if large_number and tank_type == "fuel":
    interpret_as_gallons()
elif small_number:
    interpret_as_barrels()
else:
    set_to_zero_with_warning()
```

## 💡 Example Agent Logic

```python
class SmartAgent:
    def make_decision(self, row_analysis):
        # Prefer calculated over estimated
        if has_dimensions:
            return use_calculation()

        # Trust high confidence
        elif has_high_confidence_volume:
            return use_volume()

        # Context-based inference
        elif has_number_without_units:
            if number > 1000:
                return assume_gallons()
            else:
                return assume_barrels()

        # Skip if too uncertain
        else:
            return skip_tank()
```

## 📈 Confidence Levels

The tool provides confidence ratings:

- **HIGH**: Clear pattern match with units
- **MEDIUM**: Pattern match without units
- **LOW**: Ambiguous, could be multiple things
- **NONE**: Cannot interpret

Agents decide how to handle each level.

## 🔧 Installation

```bash
# Minimal requirements
pip install pandas openpyxl

# That's it!
```

## 🧪 Testing

```bash
# Create test Excel
python test_with_agent.py --create

# Test with sample data
python test_with_agent.py sample_tanks.xlsx

# Test different confidence levels
python agent_example.py sample_tanks.xlsx high
python agent_example.py sample_tanks.xlsx medium
python agent_example.py sample_tanks.xlsx low
```

## 📝 Custom Agent Implementation

```python
from excel_analysis_tool import analyze_excel_for_conversion, apply_conversion_decisions

class MyCustomAgent:
    def process(self, excel_path):
        # Get analysis
        analysis = analyze_excel_for_conversion(excel_path)

        # Make decisions
        decisions = []
        for row in analysis["rows_analyzed"]:
            decision = self.decide_for_row(row)
            decisions.append(decision)

        # Apply decisions
        return apply_conversion_decisions(analysis, decisions)

    def decide_for_row(self, row):
        # Your custom logic here
        return {
            "row_index": row["row_index"],
            "tank_id": self.choose_id(row),
            "use_conversion": self.choose_conversion(row)
        }
```

## 🎮 Interactive Mode

```python
# Agent can ask for human input
for row in analysis["rows_analyzed"]:
    if low_confidence:
        print(f"Row {row['row_index']}: {row['raw_value']}")
        print("Options:")
        for opt in row["possibilities"]:
            print(f"  - {opt['interpretation']}")

        choice = input("Select option (1-n): ")
        decision = use_human_choice(choice)
```

## 📊 Output Format

```json
{
  "tanks": [
    {
      "name": "T-001",
      "capacity": 11775,
      "type": "diesel",
      "hasDike": true,
      "_conversion_method": "calculate_from_dimensions",
      "_agent_reasoning": [
        "Selected high confidence ID",
        "Used dimension calculation"
      ]
    }
  ],
  "agent_decisions_applied": 10,
  "skipped_rows": []
}
```

## ⚠️ Important Notes

1. **Tool Never Decides**: The tool only analyzes and calculates
2. **Agent Has Full Control**: Every decision is made by the agent
3. **Transparency**: All options are visible before decisions
4. **Override Capability**: Agent can override any analysis
5. **Reasoning Tracking**: Agent decisions are logged

## 🤝 Integration

### With LangChain
```python
from langchain.tools import tool

@tool
def process_excel_with_judgment(file_path: str) -> dict:
    """Agent processes Excel with decision-making"""
    analysis = analyze_excel_for_conversion(file_path)

    # Agent logic here
    decisions = make_smart_decisions(analysis)

    return apply_conversion_decisions(analysis, decisions)
```

### With Custom Pipeline
```python
# In your pipeline
def excel_to_json_step(excel_file):
    agent = TankProcessingAgent(confidence_threshold="medium")
    result = agent.process_excel(excel_file)

    # Save for next step
    with open("tanks.json", "w") as f:
        json.dump(result, f)

    return result["tanks"]
```

## 📄 License

Tool provided as-is for AI agent Excel processing.