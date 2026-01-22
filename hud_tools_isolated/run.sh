#!/bin/bash

# HUD Pipeline Runner Script
# Usage: ./run.sh input.xlsx [output_dir]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "       HUD Pipeline Processing Tool"
echo "================================================"

# Check if input file provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: No input file provided${NC}"
    echo "Usage: $0 input.xlsx [output_dir]"
    exit 1
fi

# Check if input file exists
if [ ! -f "$1" ]; then
    echo -e "${RED}Error: File not found: $1${NC}"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if requirements installed
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import pandas, playwright, PIL, pydantic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt

    # Install Playwright browsers if needed
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    playwright install chromium
fi

# Run the pipeline
echo -e "${GREEN}Starting HUD Pipeline...${NC}"
echo "Input: $1"

if [ -z "$2" ]; then
    python3 hud_pipeline.py "$1"
else
    echo "Output directory: $2"
    python3 hud_pipeline.py "$1" -o "$2"
fi

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Pipeline completed successfully!${NC}"
else
    echo -e "${RED}❌ Pipeline failed. Check error messages above.${NC}"
    exit 1
fi