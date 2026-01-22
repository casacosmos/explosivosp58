# Tank Processing Pipeline - Codebase Index

## Project Overview
A comprehensive tank compliance processing system with HUD (US Department of Housing and Urban Development) environmental review integration. The system processes tank data from Excel/KMZ files, performs HUD ASD calculations, and generates compliance reports.

## Directory Structure

```
pipeline_isolated/
├── api/                        # FastAPI backend
│   ├── main.py                 # API endpoints and WebSocket handlers
│   └── datastore.py            # Session data management
├── frontend/                   # React TypeScript frontend
│   ├── src/
│   │   ├── main.tsx            # Main application entry
│   │   ├── StreamlinedApp.tsx  # Streamlined UI component
│   │   ├── TankEditor.tsx      # Tank data editor
│   │   └── QuickDataEntry.tsx  # Quick data entry form
│   └── dist/                   # Built frontend assets
├── mcp_tank_compliance/        # MCP compliance tools
├── work/                       # Working directories for sessions
├── output/                     # Generated outputs
└── test_*/                    # Test directories

```

## Core Components

### 1. Main Processing Scripts

#### **Pipeline Orchestration**
- `pipeline_agent.py` - LangGraph-based orchestration of all 8 processing steps
- `pipeline_chatbot.py` - Conversational interface for pipeline
- `simple_chatbot.py` - Simplified chatbot interface

#### **Data Processing**
- `enhanced_excel_parser.py` - Multi-sheet Excel parsing with structure detection
- `kmz_parser_agent.py` - KMZ/KML parsing for geographic data
- `excel_to_json_langgraph.py` - LangGraph-powered Excel to JSON conversion
- `volume_calculator.py` - Tank volume calculations

#### **HUD Integration**
- `fast_hud_processor.py` - Optimized HUD ASD calculator using Playwright
- `compliance_checker.py` - Compliance validation against HUD standards
- `calculate_distances.py` - Distance calculations for compliance

#### **Output Generation**
- `create_professional_kmz.py` - Professional KMZ with color-coded markers
- `generate_pdf.py` - PDF report generation
- `update_excel_with_results.py` - Excel update with HUD results
- `create_enhanced_compliance_excel.py` - Enhanced compliance Excel reports

### 2. API Layer (`api/`)

#### **FastAPI Application**
- REST endpoints for all pipeline operations
- WebSocket support for real-time job monitoring
- Session management for multi-step workflows
- File upload/download handling

#### **Key Endpoints**
- `/session/new` - Create new processing session
- `/kmz/parse` - Parse KMZ/KML files
- `/excel-to-json` - Convert Excel to JSON
- `/hud/run` - Execute HUD calculations
- `/pdf/generate` - Generate PDF reports
- `/compliance/check` - Run compliance checks

### 3. Frontend (`frontend/`)

#### **React Components**
- Streamlined UI for complete pipeline workflow
- Tank data editor with validation
- Quick data entry forms
- Real-time job monitoring via WebSocket
- File upload/download management

### 4. Utility Scripts

#### **Data Processing Utilities**
- `clean_excel_data.py` - Excel data cleaning
- `parse_book1_to_template.py` - Template parsing
- `fix_compliance_logic.py` - Compliance logic fixes
- `match_kmz_to_excel.py` - KMZ-Excel matching

#### **Excel Manipulation**
- `create_book1_compliance.py` - Book1 compliance generation
- `create_final_excel.py` - Final Excel creation
- `update_book1_with_hud.py` - Book1 HUD updates
- `verify_excel_locations.py` - Location verification

#### **KMZ/Geographic Tools**
- `excel_to_kmz.py` - Excel to KMZ conversion
- `create_output_kmz.py` - Output KMZ generation
- `narrow_polygon.py` - Polygon processing
- `calculate_boundary_distances.py` - Boundary distance calculations

### 5. Testing Scripts
- `test_pipeline_agent.py` - Pipeline agent tests
- `test_pipeline_chatbot.py` - Chatbot tests
- `test_simple_chatbot.py` - Simple chatbot tests
- `test_chatbot_integration.py` - Integration tests
- `test_conversational_excel.py` - Excel conversation tests

### 6. Infrastructure Scripts
- `setup_isolated.sh` - Environment setup
- `run.sh` - Pipeline execution runner
- `run_pipeline.sh` - Complete pipeline runner
- `run_production.py` - Production runner
- `setup_venv.py` - Virtual environment setup
- `start_server.py` - Server startup

## Documentation Files

### System Documentation
- `README.md` - Main project documentation
- `COMPLETE_SYSTEM_OVERVIEW.md` - Comprehensive system architecture
- `PIPELINE_AGENT_README.md` - Pipeline agent documentation
- `PIPELINE_AGENT_VISUAL_GUIDE.md` - Visual workflow guide
- `PIPELINE_CHATBOT_README.md` - Chatbot documentation
- `SIMPLE_CHATBOT_README.md` - Simple chatbot guide
- `UNIFIED_AGENT_README.md` - Unified agent documentation

### Configuration Guides
- `AGENT_CONFIGURATION_GUIDE.md` - Agent configuration
- `CHATBOT_PIPELINE_EQUIVALENCE.md` - Chatbot-pipeline equivalence
- `pipeline_integration.md` - Pipeline integration guide

### Development Documentation
- `AGENTS.md` - Agent architecture
- `CONTRIBUTING.md` - Contribution guidelines
- `INTEGRATION_COMPLETE.md` - Integration documentation

## Data Files

### Input Data Examples
- `JUNCOS_HUELLA_EXPLOSIVOS_SITES.xlsx` - Sample Excel input
- `JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz` - Sample KMZ input
- Various `tank_locations_*.xlsx` files - Tank data samples

### Generated Outputs
- `book1_*.xlsx` - Processed Excel workbooks
- `book1_*.json` - JSON configurations
- `tanks_juncos*.kmz` - Generated KMZ files
- `HUD_ASD_Results.pdf` - HUD calculation results
- `fast_results.json` - Processing results JSON

## Key Technologies

### Backend
- **Python 3.x** - Core language
- **FastAPI** - API framework
- **LangGraph** - Workflow orchestration
- **LangChain** - AI/LLM integration
- **Playwright** - Browser automation for HUD
- **OpenAI API** - Natural language processing

### Frontend
- **React** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool
- **WebSocket** - Real-time communication

### Data Processing
- **pandas** - Excel/CSV processing
- **simplekml** - KML/KMZ generation
- **PyPDF2** - PDF manipulation
- **openpyxl** - Excel file operations

## Workflow Summary

1. **Input Processing** - Parse Excel/KMZ files
2. **Data Validation** - Validate tank configurations
3. **HUD Processing** - Calculate ASD values via HUD website
4. **Compliance Check** - Verify against regulations
5. **Report Generation** - Create Excel, PDF, KMZ outputs
6. **User Delivery** - Provide downloadable results

## Environment Requirements

- Python 3.8+
- Node.js 16+ (for frontend)
- Playwright with Chromium
- OpenAI API key (for LLM features)

## Session Management
The system uses session-based processing where each workflow creates a unique session ID. All intermediate files and outputs are stored in session-specific directories under `work/` and `output/`.

## New Untracked Files (57 total)

### New Chatbot/Agent Implementations
- `simple_chatbot.py` - Simplified conversational interface for pipeline
- `pipeline_chatbot.py` - Full chatbot with LangGraph integration
- `test_pipeline_chatbot.py` - Chatbot tests
- `test_simple_chatbot.py` - Simple chatbot tests
- `test_chatbot_integration.py` - Integration testing
- `test_conversational_excel.py` - Excel conversation tests
- `test_pipeline_agent.py` - Pipeline agent tests

### Book1 Processing Chain (Sample workflow)
- `parse_book1_to_template.py` - Parse Book1.xlsx to template
- `book1_template.json` - Extracted template structure
- `book1_complete.json` - Complete parsed data
- `create_book1_compliance.py` - Generate compliance report
- `update_book1_with_hud.py` - Add HUD results to Book1
- `book1_output/` - Output directory for Book1 processing
- `book1_hud_output/` - HUD results for Book1

### Enhanced Processing Scripts
- `enhanced_excel_parser.py` - Multi-sheet Excel parsing with AI
- `process_excel_with_hud.py` - Direct Excel to HUD processing
- `process_original_excel.py` - Original Excel processor
- `create_enhanced_compliance_excel.py` - Enhanced compliance reports
- `create_final_excel.py` - Final Excel generation
- `fix_compliance_logic.py` - Compliance logic improvements

### Geographic/KMZ Processing
- `calculate_boundary_distances.py` - Distance to polygon boundaries
- `create_output_kmz.py` - Generate output KMZ files
- `create_professional_kmz.py` - Professional KMZ with styling
- `excel_to_kmz.py` - Excel to KMZ converter
- `match_kmz_to_excel.py` - Match KMZ features to Excel rows
- `narrow_polygon.py` - Polygon processing utilities
- `professional_juncos.kmz` - Sample professional KMZ output
- `tanks_juncos*.kmz` - Various tank KMZ outputs

### Data Processing Utilities
- `clean_excel_data.py` - Excel data cleaning
- `update_excel_locations_manual.py` - Manual location updates
- `verify_excel_locations.py` - Location verification

### MCP Integration (`mcp_tank_compliance/`)
Complete MCP (Model Context Protocol) server implementation:
- `server.py` - MCP server implementation
- `hud_automation_tool.py` - HUD automation as MCP tool
- `agente_persistent.py` - Persistent agent implementation
- `enhanced_agent.py` - Enhanced agent features
- `streamlit_agent.py` - Streamlit UI for agent
- `create_compliance_excel.py` - Compliance Excel generation
- `kmz_to_excel.py` - KMZ to Excel conversion

### Frontend Components (New)
- `frontend/src/LegacySummaryPanel.jsx` - Legacy panel component
- `frontend/src/LegacyVueWidget.vue` - Vue widget for compatibility

### Documentation (New)
- `AGENT_CONFIGURATION_GUIDE.md` - LangGraph agent configuration
- `PIPELINE_AGENT_README.md` - Pipeline agent documentation
- `PIPELINE_AGENT_VISUAL_GUIDE.md` - Visual workflow guide
- `PIPELINE_CHATBOT_README.md` - Chatbot documentation
- `SIMPLE_CHATBOT_README.md` - Simple chatbot guide
- `UNIFIED_AGENT_README.md` - Unified agent documentation
- `CHATBOT_PIPELINE_EQUIVALENCE.md` - Chatbot-pipeline comparison

### Sample Data Files
- `JUNCOS HUELLA EXPLOSIVOS SITES_buffer1miles.kmz` - KMZ with buffer
- `doc.kml` - Sample KML document
- `juncos_structure.json` - Parsed Juncos structure
- `parsed_book1.json` - Parsed Book1 data
- `fast_results.json` - HUD processing results

### Work Directories
- `work/mfo4s291luas5w0tsk/` - Session work directory
- `work/mfvw1gkb8izq2vz8ir7/` - Session work directory
- `work/mfw3rygzxq0unnqz5g/` - Session work directory

## Current Status
- Modified files pending commit: API, frontend, and several processors
- 57 untracked files including new chatbot implementations, enhanced parsers, and MCP integration
- Active development on three parallel tracks:
  1. Chatbot/conversational interfaces
  2. Enhanced Excel/KMZ processing
  3. MCP server implementation for tool integration

## Source File Statistics
- Total source files: 9,452 (py/ts/tsx/js/jsx)
- Excludes: venv, node_modules