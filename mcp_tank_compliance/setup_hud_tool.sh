#!/bin/bash
# Setup script for HUD browser automation tool

echo "Setting up HUD Browser Automation Tool..."
echo "========================================"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
python -m playwright install chromium

# Create directories
echo "Creating required directories..."
mkdir -p hud_screenshots
mkdir -p hud_reports

echo ""
echo "Setup complete!"
echo ""
echo "To test the HUD automation tool:"
echo "  python hud_automation_tool.py"
echo ""
echo "To use via MCP server:"
echo "  python server.py"
echo ""
echo "Note: The HUD calculator requires internet connection to access https://www.hud.gov"