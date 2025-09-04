#!/bin/bash
# Complete Pipeline Runner for Tank Processing System
# Uses improved Excel to JSON parser with accurate volume calculations

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Tank Processing Pipeline Runner    ${NC}"
echo -e "${GREEN}=====================================${NC}\n"

# Check for required environment variable
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OPENAI_API_KEY environment variable not set${NC}"
    echo "Please export your OpenAI API key:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

# Parse arguments
INPUT_FILE=""
OUTPUT_DIR="outputs"
USE_IMPROVED="true"
SKIP_VALIDATION="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --legacy)
            USE_IMPROVED="false"
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION="true"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 -i INPUT_FILE [-o OUTPUT_DIR] [--legacy] [--skip-validation]"
            echo ""
            echo "Options:"
            echo "  -i, --input FILE       Input file (Excel/CSV or KMZ)"
            echo "  -o, --output DIR       Output directory (default: outputs)"
            echo "  --legacy               Use original parser (not recommended)"
            echo "  --skip-validation      Skip JSON validation step"
            echo ""
            echo "Pipeline Steps:"
            echo "  1. Parse KMZ (if .kmz input)"
            echo "  2. Convert Excel/CSV to JSON"
            echo "  3. Validate JSON (unless skipped)"
            echo "  4. Process with HUD calculator"
            echo "  5. Generate PDF report"
            echo "  6. Update Excel with results"
            echo "  7. Check compliance"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

if [ -z "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Input file required${NC}"
    echo "Usage: $0 -i INPUT_FILE [-o OUTPUT_DIR]"
    exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Input file not found: $INPUT_FILE${NC}"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Determine file type and process accordingly
EXTENSION="${INPUT_FILE##*.}"
EXTENSION=$(echo "$EXTENSION" | tr '[:upper:]' '[:lower:]')

echo -e "${YELLOW}Processing: $INPUT_FILE${NC}"
echo -e "${YELLOW}Output directory: $OUTPUT_DIR${NC}"
echo ""

# Step 1: Handle KMZ if provided
if [ "$EXTENSION" = "kmz" ] || [ "$EXTENSION" = "kml" ]; then
    echo -e "${GREEN}Step 1: Parsing KMZ/KML file...${NC}"
    python kmz_parser_agent.py "$INPUT_FILE" -o "$OUTPUT_DIR"
    
    # Find the generated Excel template
    EXCEL_FILE=$(find "$OUTPUT_DIR" -name "tank_locations_*.xlsx" -o -name "tank_locations_*.xls" | head -1)
    
    if [ -z "$EXCEL_FILE" ]; then
        echo -e "${RED}Error: No Excel template generated from KMZ${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Generated Excel template: $EXCEL_FILE${NC}"
    echo -e "${YELLOW}Please fill the Excel with tank measurements before continuing...${NC}"
    echo -e "${YELLOW}Press Enter when ready to continue...${NC}"
    read -r
else
    EXCEL_FILE="$INPUT_FILE"
fi

# Verify Excel/CSV file
if [[ ! "$EXCEL_FILE" =~ \.(xlsx|xls|csv)$ ]]; then
    echo -e "${RED}Error: Input must be Excel (.xlsx/.xls) or CSV (.csv) file${NC}"
    exit 1
fi

# Step 2: Convert Excel to JSON
echo -e "${GREEN}Step 2: Converting Excel to JSON...${NC}"
JSON_FILE="$OUTPUT_DIR/tank_config.json"

if [ "$USE_IMPROVED" = "true" ]; then
    echo -e "${YELLOW}Using improved parser with VolumeCalculator${NC}"
    
    # Check if volume_calculator.py exists
    if [ ! -f "volume_calculator.py" ]; then
        echo -e "${RED}Warning: volume_calculator.py not found${NC}"
        echo -e "${YELLOW}Falling back to original parser...${NC}"
        python excel_to_json_langgraph.py "$EXCEL_FILE" -o "$JSON_FILE"
    else
        python excel_to_json_improved.py "$EXCEL_FILE" -o "$JSON_FILE"
    fi
else
    echo -e "${YELLOW}Using original parser (legacy mode)${NC}"
    python excel_to_json_langgraph.py "$EXCEL_FILE" -o "$JSON_FILE"
fi

if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}Error: JSON file not created${NC}"
    exit 1
fi

# Step 3: Validate JSON (optional)
if [ "$SKIP_VALIDATION" = "false" ] && [ "$USE_IMPROVED" = "false" ]; then
    echo -e "${GREEN}Step 3: Validating JSON...${NC}"
    python validate_tank_json.py "$JSON_FILE"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: JSON validation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Step 3: Skipping validation (internal validation used)${NC}"
fi

# Step 4: Run HUD processor
echo -e "${GREEN}Step 4: Running HUD ASD calculations...${NC}"
HUD_RESULTS="$OUTPUT_DIR/fast_results.json"

if [ -f "fast_hud_processor.py" ]; then
    python fast_hud_processor.py "$JSON_FILE" -o "$HUD_RESULTS"
else
    echo -e "${YELLOW}HUD processor not found, skipping...${NC}"
    HUD_RESULTS=""
fi

# Step 5: Generate PDF report
if [ -n "$HUD_RESULTS" ] && [ -f "$HUD_RESULTS" ]; then
    echo -e "${GREEN}Step 5: Generating PDF report...${NC}"
    PDF_FILE="$OUTPUT_DIR/HUD_ASD_Results.pdf"
    
    if [ -f "generate_pdf.py" ]; then
        python generate_pdf.py "$HUD_RESULTS" -o "$PDF_FILE"
        echo -e "${YELLOW}PDF generated: $PDF_FILE${NC}"
    else
        echo -e "${YELLOW}PDF generator not found, skipping...${NC}"
    fi
fi

# Step 6: Update Excel with results
if [ -n "$HUD_RESULTS" ] && [ -f "$HUD_RESULTS" ]; then
    echo -e "${GREEN}Step 6: Updating Excel with ASD results...${NC}"
    UPDATED_EXCEL="$OUTPUT_DIR/with_hud.xlsx"
    
    if [ -f "update_excel_with_results.py" ]; then
        python update_excel_with_results.py "$EXCEL_FILE" "$HUD_RESULTS" -o "$UPDATED_EXCEL"
        echo -e "${YELLOW}Updated Excel: $UPDATED_EXCEL${NC}"
    else
        echo -e "${YELLOW}Excel updater not found, skipping...${NC}"
    fi
fi

# Step 7: Run compliance check
if [ -f "$UPDATED_EXCEL" ]; then
    echo -e "${GREEN}Step 7: Running compliance check...${NC}"
    COMPLIANCE_FILE="$OUTPUT_DIR/final_compliance.xlsx"
    
    # Check if we have polygon data
    POLYGON_FILE=$(find "$OUTPUT_DIR" -name "polygon_*.txt" | head -1)
    
    if [ -f "compliance_checker.py" ]; then
        if [ -n "$POLYGON_FILE" ]; then
            python compliance_checker.py "$UPDATED_EXCEL" --polygon "$POLYGON_FILE" -o "$COMPLIANCE_FILE"
        else
            echo -e "${YELLOW}No polygon file found, running without distances${NC}"
            python compliance_checker.py "$UPDATED_EXCEL" --no-distances -o "$COMPLIANCE_FILE"
        fi
        echo -e "${YELLOW}Compliance report: $COMPLIANCE_FILE${NC}"
    else
        echo -e "${YELLOW}Compliance checker not found, skipping...${NC}"
    fi
fi

# Summary
echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Pipeline Complete!                 ${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Output files:"
echo "  - JSON config: $JSON_FILE"

if [ -f "$HUD_RESULTS" ]; then
    echo "  - HUD results: $HUD_RESULTS"
fi

if [ -f "$PDF_FILE" ]; then
    echo "  - PDF report: $PDF_FILE"
fi

if [ -f "$UPDATED_EXCEL" ]; then
    echo "  - Updated Excel: $UPDATED_EXCEL"
fi

if [ -f "$COMPLIANCE_FILE" ]; then
    echo "  - Compliance report: $COMPLIANCE_FILE"
fi

echo ""

# Show tank summary
if [ -f "$JSON_FILE" ]; then
    TANK_COUNT=$(python -c "import json; data=json.load(open('$JSON_FILE')); print(len(data.get('tanks', [])))")
    echo -e "${GREEN}Total tanks processed: $TANK_COUNT${NC}"
    
    # Show volume source breakdown if using improved parser
    if [ "$USE_IMPROVED" = "true" ]; then
        python -c "
import json
data = json.load(open('$JSON_FILE'))
sources = {}
for tank in data.get('tanks', []):
    src = tank.get('volume_source', 'unknown')
    sources[src] = sources.get(src, 0) + 1
print('Volume sources:')
for src, count in sources.items():
    print(f'  - {src}: {count}')
"
    fi
fi

echo ""
echo -e "${GREEN}Pipeline execution completed successfully!${NC}"