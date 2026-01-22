# Pipeline Agent Visual Guide

**Complete Visual Documentation of LangGraph-Based Tank Processing Pipeline**

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE AGENT ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  USER INPUT LAYER                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │ CLI Args │  │ API Call │  │ WebSocket│                          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                          │
└───────┼─────────────┼─────────────┼────────────────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────────────┐
│  LANGGRAPH AGENT LAYER                                              │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  StateGraph Workflow Engine                                │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │    │
│  │  │  Node 1  │→ │  Node 2  │→ │  Node 3  │→ │  Node N  │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │    │
│  └────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  PipelineState (TypedDict)                                 │    │
│  │  • Artifacts: paths to files                               │    │
│  │  • Progress: current_step, completed_steps                 │    │
│  │  • Errors/Warnings: error tracking                         │    │
│  │  • Metrics: tank_count, stats, timing                      │    │
│  └────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Checkpointer (MemorySaver)                                │    │
│  │  • State persistence at each node                          │    │
│  │  • Resume capability on failure                            │    │
│  │  • Time-travel debugging support                           │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────┬──────────────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────────────┐
│  TOOL LAYER                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ parse_kmz    │ │ excel_to_json│ │ validate_json│               │
│  │ _tool        │ │ _tool        │ │ _tool        │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│  ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐               │
│  │ process_hud  │ │ generate_pdf │ │ update_excel │               │
│  │ _tool        │ │ _tool        │ │ _tool        │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│  ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐               │
│  │ calculate_   │ │ check_       │ │ calculate_   │               │
│  │ distances    │ │ compliance   │ │ volume       │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│         │                │                │                         │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
┌─────────▼────────────────▼────────────────▼─────────────────────────┐
│  EXECUTION LAYER (Subprocess Calls)                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │ kmz_parser_      │  │ excel_to_json_   │  │ validate_tank_  │   │
│  │ agent.py         │  │ improved.py      │  │ json.py         │   │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │ fast_hud_        │  │ generate_pdf.py  │  │ update_excel_   │   │
│  │ processor.py     │  │                  │  │ with_results.py │   │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │ calculate_       │  │ compliance_      │                        │
│  │ distances.py     │  │ checker.py       │                        │
│  └──────────────────┘  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘

Key Concepts:
• Layered architecture separates concerns
• LangGraph orchestrates workflow at agent layer
• Tools provide abstraction over subprocess execution
• State persists across all operations via checkpointer
• Each layer can be tested/replaced independently
```

---

## 2. Complete Pipeline Flow

```
                         ┌───────────────┐
                         │     START     │
                         └───────┬───────┘
                                 │
                     ┌───────────▼───────────┐
                     │  detect_input_node    │
                     │  Detect: KMZ/Excel/CSV│
                     └───────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │ input_type =   │       │ input_type =   │
            │    "kmz"       │       │ "excel"/"csv"  │
            └───────┬────────┘       └───────┬────────┘
                    │                         │
        ┌───────────▼───────────┐             │
        │  parse_kmz_node       │             │
        │  Tool: parse_kmz_tool │             │
        │  Extract locations,   │             │
        │  boundaries from KMZ  │             │
        └───────────┬───────────┘             │
                    │                         │
        ┌───────────▼───────────┐             │
        │ human_fill_excel_node │             │
        │ INTERRUPT for human   │             │
        │ to complete Excel     │             │
        └───────────┬───────────┘             │
                    │                         │
                    └────────────┬────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  excel_to_json_node    │
                     │  Tool: excel_to_json_  │
                     │        tool            │
                     │  Convert Excel → JSON  │
                     │  with VolumeCalculator │
                     └───────────┬────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  validate_json_node    │
                     │  Tool: validate_json_  │
                     │        tool            │
                     │  Check schema & data   │
                     └───────────┬────────────┘
                                 │
                    ┌────────────┴─────────────┐
                    │                          │
        ┌───────────▼──────────┐   ┌──────────▼──────────┐
        │ validation_passed =  │   │ validation_passed = │
        │       True           │   │       False         │
        └───────────┬──────────┘   └──────────┬──────────┘
                    │                          │
        ┌───────────▼───────────┐              │
        │  process_hud_node     │              │
        │  Tool: process_hud_   │              │
        │        tool           │              │
        │  Playwright automation│              │
        │  Calculate ASD values │              │
        │  ⏱️  6-8 min for 24   │              │
        │     tanks             │              │
        └───────────┬───────────┘              │
                    │                          │
        ┌───────────▼───────────┐              │
        │  generate_pdf_node    │              │
        │  Tool: generate_pdf_  │              │
        │        tool           │              │
        │  Create HUD_ASD_      │              │
        │  Results.pdf report   │              │
        └───────────┬───────────┘              │
                    │                          │
        ┌───────────▼───────────┐              │
        │  update_excel_node    │              │
        │  Tool: update_excel_  │              │
        │        tool           │              │
        │  Merge HUD results    │              │
        │  into Excel           │              │
        └───────────┬───────────┘              │
                    │                          │
       ┌────────────┴────────────┐             │
       │                         │             │
┌──────▼──────────┐   ┌──────────▼──────────┐ │
│ has_polygon =   │   │ has_polygon =       │ │
│     True        │   │     False           │ │
└──────┬──────────┘   └──────────┬──────────┘ │
       │                          │             │
┌──────▼──────────────┐           │             │
│ calculate_distances_│           │             │
│ node                │           │             │
│ Tool: calculate_    │           │             │
│       distances_tool│           │             │
│ Geospatial distance │           │             │
│ calculations        │           │             │
└──────┬──────────────┘           │             │
       │                          │             │
       └───────────┬──────────────┘             │
                   │                            │
       ┌───────────▼────────────┐               │
       │ check_compliance_node  │               │
       │ Tool: check_compliance_│               │
       │       tool             │               │
       │ Compare distances vs   │               │
       │ ASD requirements       │               │
       └───────────┬────────────┘               │
                   │                            │
                   └──────────┬─────────────────┘
                              │
                  ┌───────────▼───────────┐
                  │  summarize_results_   │
                  │  node                 │
                  │  Generate execution   │
                  │  summary with:        │
                  │  • Total time         │
                  │  • Tanks processed    │
                  │  • Files generated    │
                  │  • Errors/warnings    │
                  └───────────┬───────────┘
                              │
                         ┌────▼────┐
                         │   END   │
                         └─────────┘

Pipeline Statistics (24 tanks):
├─ KMZ Parse:          10-30 sec
├─ Excel→JSON:         30-60 sec
├─ Validate:           <1 sec
├─ HUD Process:        6-8 min  ⚠️ BOTTLENECK
├─ Generate PDF:       5-10 sec
├─ Update Excel:       2-5 sec
├─ Calc Distances:     5-10 sec
└─ Check Compliance:   2-5 sec
   ═══════════════════════════════
   TOTAL:              7-10 min
```

---

## 3. State Management Flow

```
STATE EVOLUTION THROUGH PIPELINE
═════════════════════════════════════════════════════════════════════

Initial State (t=0):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   input_file: "tanks.xlsx"                                        │
│   input_type: None  ← TO BE DETECTED                              │
│   output_dir: "outputs"                                           │
│   session_id: "juncos_2025_01"                                    │
│   config: {use_improved_parser: True}                             │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ ARTIFACTS (all None initially)                          │    │
│   │ kmz_parsed: None                                        │    │
│   │ excel_file: None                                        │    │
│   │ tank_config_json: None                                  │    │
│   │ validation_passed: False                                │    │
│   │ hud_results_json: None                                  │    │
│   │ pdf_report: None                                        │    │
│   │ updated_excel: None                                     │    │
│   │ distances_json: None                                    │    │
│   │ compliance_excel: None                                  │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ PROGRESS                                                │    │
│   │ current_step: ""                                        │    │
│   │ completed_steps: []                                     │    │
│   │ errors: []                                              │    │
│   │ warnings: []                                            │    │
│   │ messages: []                                            │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ METRICS                                                 │    │
│   │ tank_count: 0                                           │    │
│   │ processing_stats: {}                                    │    │
│   │ start_time: None                                        │    │
│   │ end_time: None                                          │    │
│   └─────────────────────────────────────────────────────────┘    │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  detect_input_node  │
                   └──────────┬──────────┘
                              │
After detect_input (t=1):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   input_type: "excel"  ← DETECTED                                 │
│   current_step: "detect_input"  ← UPDATED                         │
│   completed_steps: ["detect_input"]  ← UPDATED                    │
│   messages: [                                                     │
│     AIMessage("Detected Excel input file")                        │
│   ]                                                               │
│   ... rest unchanged ...                                          │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │ excel_to_json_node  │
                   └──────────┬──────────┘
                              │
After excel_to_json (t=2):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   tank_config_json: "outputs/tank_config.json"  ← ARTIFACT ADDED  │
│   tank_count: 24  ← METRIC UPDATED                                │
│   current_step: "excel_to_json"                                   │
│   completed_steps: ["detect_input", "excel_to_json"]              │
│   processing_stats: {                                             │
│     "volume_calculation": {                                       │
│       "from_dimensions": 22,                                      │
│       "from_excel": 2                                             │
│     }                                                             │
│   }                                                               │
│   messages: [                                                     │
│     AIMessage("Detected Excel input file"),                       │
│     AIMessage("Converted Excel to JSON: 24 tanks")                │
│   ]                                                               │
│   ... rest unchanged ...                                          │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  validate_json_node │
                   └──────────┬──────────┘
                              │
After validate_json (t=3):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   validation_passed: True  ← VALIDATION FLAG SET                  │
│   current_step: "validate_json"                                   │
│   completed_steps: [                                              │
│     "detect_input", "excel_to_json", "validate_json"              │
│   ]                                                               │
│   warnings: [                                                     │
│     "Tank T-05 missing dimension height"                          │
│   ]  ← VALIDATION WARNINGS                                        │
│   ... rest carries forward ...                                    │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │   process_hud_node  │
                   └──────────┬──────────┘
                              │
After process_hud (t=4):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   hud_results_json: "outputs/fast_results.json"  ← ARTIFACT       │
│   current_step: "process_hud"                                     │
│   completed_steps: [                                              │
│     "detect_input", "excel_to_json", "validate_json",             │
│     "process_hud"                                                 │
│   ]                                                               │
│   processing_stats: {                                             │
│     "volume_calculation": {...},                                  │
│     "hud_processing": {                                           │
│       "duration_seconds": 456,                                    │
│       "tanks_processed": 24,                                      │
│       "avg_time_per_tank": 19.0                                   │
│     }                                                             │
│   }                                                               │
│   ... rest carries forward ...                                    │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  generate_pdf_node  │
                   └──────────┬──────────┘
                              │
After generate_pdf (t=5):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   pdf_report: "outputs/HUD_ASD_Results.pdf"  ← ARTIFACT           │
│   current_step: "generate_pdf"                                    │
│   completed_steps: [                                              │
│     "detect_input", "excel_to_json", "validate_json",             │
│     "process_hud", "generate_pdf"                                 │
│   ]                                                               │
│   ... rest carries forward ...                                    │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘

... continues through remaining nodes ...

Final State (t=10):
┌───────────────────────────────────────────────────────────────────┐
│ PipelineState {                                                   │
│   input_file: "tanks.xlsx"                                        │
│   input_type: "excel"                                             │
│   output_dir: "outputs"                                           │
│   session_id: "juncos_2025_01"                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ ARTIFACTS (all populated)                               │    │
│   │ tank_config_json: "outputs/tank_config.json"            │    │
│   │ validation_passed: True                                 │    │
│   │ hud_results_json: "outputs/fast_results.json"           │    │
│   │ pdf_report: "outputs/HUD_ASD_Results.pdf"               │    │
│   │ updated_excel: "outputs/with_hud.xlsx"                  │    │
│   │ distances_json: "outputs/distances.json"                │    │
│   │ compliance_excel: "outputs/final_compliance.xlsx"       │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ PROGRESS                                                │    │
│   │ current_step: "summarize"                               │    │
│   │ completed_steps: [                                      │    │
│   │   "detect_input", "excel_to_json", "validate_json",     │    │
│   │   "process_hud", "generate_pdf", "update_excel",        │    │
│   │   "calculate_distances", "check_compliance",            │    │
│   │   "summarize"                                           │    │
│   │ ]                                                       │    │
│   │ errors: []                                              │    │
│   │ warnings: ["Tank T-05 missing dimension height"]        │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │ METRICS                                                 │    │
│   │ tank_count: 24                                          │    │
│   │ processing_stats: {                                     │    │
│   │   "volume_calculation": {...},                          │    │
│   │   "hud_processing": {...}                               │    │
│   │ }                                                       │    │
│   │ start_time: 1706553600.0                                │    │
│   │ end_time: 1706554080.0                                  │    │
│   └─────────────────────────────────────────────────────────┘    │
│ }                                                                 │
└───────────────────────────────────────────────────────────────────┘

Key State Characteristics:
• Immutable structure (TypedDict)
• Additive updates (artifacts accumulate)
• Progress tracking (completed_steps grows)
• Error collection (non-blocking)
• Metrics aggregation (processing_stats)
```

---

## 4. Tool Execution Pattern

```
TOOL INVOCATION FLOW
════════════════════════════════════════════════════════════════════

Node Execution:
┌───────────────────────────────────────────────────────────────────┐
│  excel_to_json_node(state: PipelineState) → PipelineState        │
│                                                                   │
│  Step 1: Extract parameters from state                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ excel_path = state["input_file"]                           │  │
│  │ output_dir = state["output_dir"]                           │  │
│  │ use_improved = state["config"].get("use_improved", True)   │  │
│  │ output_json = os.path.join(output_dir, "tank_config.json") │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │                                        │
│  Step 2: Invoke tool     │                                        │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │ result = excel_to_json_tool.invoke({                      │  │
│  │     "excel_path": excel_path,                             │  │
│  │     "output_json": output_json,                           │  │
│  │     "use_improved": use_improved                          │  │
│  │ })                                                        │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │                                        │
│  Step 3: Check result    │                                        │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │ if result["success"]:                                     │  │
│  │     # Update state with artifacts                         │  │
│  │     return {                                              │  │
│  │         "tank_config_json": result["json_path"],          │  │
│  │         "tank_count": result["tank_count"],               │  │
│  │         "current_step": "excel_to_json",                  │  │
│  │         "completed_steps": state["completed_steps"] +     │  │
│  │                            ["excel_to_json"],             │  │
│  │         "messages": [AIMessage("Converted Excel to JSON")]│  │
│  │     }                                                     │  │
│  │ else:                                                     │  │
│  │     # Add error and continue                              │  │
│  │     return {                                              │  │
│  │         "errors": state["errors"] +                       │  │
│  │                   [result["error"]],                      │  │
│  │         "current_step": "excel_to_json",                  │  │
│  │         "messages": [AIMessage("Excel to JSON failed")]   │  │
│  │     }                                                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘

Tool Implementation:
┌───────────────────────────────────────────────────────────────────┐
│  @tool                                                            │
│  def excel_to_json_tool(                                          │
│      excel_path: str,                                             │
│      output_json: str,                                            │
│      use_improved: bool = True                                    │
│  ) -> Dict[str, Any]:                                             │
│      """Convert Excel/CSV to tank configuration JSON."""          │
│                                                                   │
│      Step 1: Build subprocess command                             │
│      ┌────────────────────────────────────────────────────────┐  │
│      │ script = "excel_to_json_improved.py" if use_improved   │  │
│      │          else "excel_to_json_langgraph.py"             │  │
│      │ cmd = ["python", script, excel_path,                   │  │
│      │        "-o", output_json]                              │  │
│      └────────────────────────────────────────────────────────┘  │
│                          │                                        │
│      Step 2: Execute     │                                        │
│      ┌───────────────────▼───────────────────────────────────┐  │
│      │ result = subprocess.run(                              │  │
│      │     cmd,                                              │  │
│      │     capture_output=True,                              │  │
│      │     text=True,                                        │  │
│      │     timeout=600  # 10 min timeout                     │  │
│      │ )                                                     │  │
│      └───────────────────┬───────────────────────────────────┘  │
│                          │                                        │
│      Step 3: Parse output│                                        │
│      ┌───────────────────▼───────────────────────────────────┐  │
│      │ if result.returncode != 0:                            │  │
│      │     return {                                          │  │
│      │         "success": False,                             │  │
│      │         "error": f"Conversion failed: {result.stderr}"│  │
│      │     }                                                 │  │
│      │                                                       │  │
│      │ # Parse generated JSON for stats                      │  │
│      │ with open(output_json, 'r') as f:                     │  │
│      │     data = json.load(f)                               │  │
│      │     tank_count = len(data.get('tanks', []))           │  │
│      │                                                       │  │
│      │ return {                                              │  │
│      │     "success": True,                                  │  │
│      │     "json_path": output_json,                         │  │
│      │     "tank_count": tank_count,                         │  │
│      │     "volume_sources": {...}                           │  │
│      │ }                                                     │  │
│      └───────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘

Benefits of Tool Pattern:
├─ Subprocess isolation: Scripts run in separate process
├─ Error containment: Failures don't crash agent
├─ Timeout protection: Long-running scripts can be killed
├─ Output capture: Both stdout and stderr captured
├─ Testability: Tools can be unit tested independently
├─ Reusability: Tools can be used outside graph
└─ Observability: LangSmith traces tool calls
```

---

## 5. Conditional Routing Logic

```
ROUTING DECISION TREE
════════════════════════════════════════════════════════════════════

Router 1: route_after_detection
───────────────────────────────────────────────────────────────────
Input: state["input_type"]
┌─────────────────────────────────────────────────────────────────┐
│                     detect_input_node                           │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │ Check input_type│                            │
│                  └────────┬────────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                  │
│         │                 │                 │                  │
│    ┌────▼────┐      ┌─────▼─────┐    ┌─────▼─────┐            │
│    │input_type     │input_type  │    │input_type │            │
│    │== "kmz"  │     │== "excel" │    │== "csv"   │            │
│    └────┬────┘      └─────┬─────┘    └─────┬─────┘            │
│         │                 │                 │                  │
│    ┌────▼─────────┐       └────────┬────────┘                  │
│    │ parse_kmz_   │                │                           │
│    │ node         │           ┌────▼──────────┐                │
│    └──────────────┘           │ excel_to_json_│                │
│                               │ node          │                │
│                               └───────────────┘                │
└─────────────────────────────────────────────────────────────────┘

Code:
def route_after_detection(state: PipelineState) -> str:
    """Route based on input type."""
    input_type = state["input_type"]
    if input_type == "kmz":
        return "parse_kmz"
    else:  # excel or csv
        return "excel_to_json"


Router 2: route_after_validation
───────────────────────────────────────────────────────────────────
Input: state["validation_passed"]
┌─────────────────────────────────────────────────────────────────┐
│                     validate_json_node                          │
│                           │                                     │
│                  ┌────────▼────────────┐                        │
│                  │ Check validation_   │                        │
│                  │       passed        │                        │
│                  └────────┬────────────┘                        │
│                           │                                     │
│              ┌────────────┴────────────┐                        │
│              │                         │                        │
│      ┌───────▼────────┐       ┌────────▼────────┐              │
│      │validation_passed      │validation_passed │              │
│      │== True          │      │== False         │              │
│      └───────┬────────┘       └────────┬────────┘              │
│              │                         │                        │
│      ┌───────▼──────────┐              │                        │
│      │ process_hud_node │              │                        │
│      │ Continue pipeline│         ┌────▼────────┐              │
│      └──────────────────┘         │ summarize_  │              │
│                                   │ results_node│              │
│                                   │ Skip to end │              │
│                                   └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘

Code:
def route_after_validation(state: PipelineState) -> str:
    """Route based on validation result."""
    if state["validation_passed"]:
        return "process_hud"
    else:
        return "summarize"  # Skip to end with errors


Router 3: route_after_update_excel
───────────────────────────────────────────────────────────────────
Input: state["kmz_parsed"], state["kmz_parsed"]["polygon"]
┌─────────────────────────────────────────────────────────────────┐
│                     update_excel_node                           │
│                           │                                     │
│                  ┌────────▼────────────┐                        │
│                  │ Check if polygon    │                        │
│                  │ available           │                        │
│                  └────────┬────────────┘                        │
│                           │                                     │
│              ┌────────────┴────────────┐                        │
│              │                         │                        │
│      ┌───────▼────────┐       ┌────────▼────────┐              │
│      │kmz_parsed is   │       │kmz_parsed is    │              │
│      │not None AND    │       │None OR no       │              │
│      │has polygon     │       │polygon          │              │
│      └───────┬────────┘       └────────┬────────┘              │
│              │                         │                        │
│      ┌───────▼──────────────┐          │                        │
│      │ calculate_distances_ │          │                        │
│      │ node                 │     ┌────▼────────────┐           │
│      │ Geospatial calcs     │     │ check_compliance│           │
│      └──────────────────────┘     │ _node           │           │
│                                   │ Skip distances  │           │
│                                   └─────────────────┘           │
└─────────────────────────────────────────────────────────────────┘

Code:
def route_after_update_excel(state: PipelineState) -> str:
    """Route based on polygon availability."""
    kmz_parsed = state.get("kmz_parsed")
    if kmz_parsed and kmz_parsed.get("polygon"):
        return "calculate_distances"
    else:
        return "check_compliance"  # Skip distances


COMPLETE ROUTING TABLE
═══════════════════════════════════════════════════════════════════
Node                     │ Router                  │ Next Nodes
─────────────────────────┼─────────────────────────┼─────────────────
START                    │ (fixed)                 │ detect_input
detect_input             │ route_after_detection   │ parse_kmz OR
                         │                         │ excel_to_json
parse_kmz                │ (fixed)                 │ human_fill_excel
human_fill_excel         │ (fixed)                 │ excel_to_json
excel_to_json            │ (fixed)                 │ validate_json
validate_json            │ route_after_validation  │ process_hud OR
                         │                         │ summarize
process_hud              │ (fixed)                 │ generate_pdf
generate_pdf             │ (fixed)                 │ update_excel
update_excel             │ route_after_update_excel│ calculate_distances
                         │                         │ OR check_compliance
calculate_distances      │ (fixed)                 │ check_compliance
check_compliance         │ (fixed)                 │ summarize
summarize                │ (fixed)                 │ END
```

---

## 6. Error Handling & Recovery

```
ERROR HANDLING STRATEGY
════════════════════════════════════════════════════════════════════

Level 1: Tool-Level Error Handling
───────────────────────────────────────────────────────────────────
@tool
def process_hud_tool(config_json: str, output_json: str) -> Dict[str, Any]:
    try:
        # Step 1: Validate inputs
        if not os.path.exists(config_json):
            return {
                "success": False,
                "error": f"Config file not found: {config_json}"
            }

        # Step 2: Execute subprocess with timeout
        cmd = ["python", "fast_hud_processor.py", config_json, "-o", output_json]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200  # 20 min timeout
        )

        # Step 3: Check return code
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"HUD processing failed: {result.stderr}"
            }

        # Step 4: Validate output
        if not os.path.exists(output_json):
            return {
                "success": False,
                "error": "HUD results file not generated"
            }

        return {
            "success": True,
            "results_path": output_json,
            "tanks_processed": count_tanks(output_json)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "HUD processing timed out after 20 minutes"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

Level 2: Node-Level Error Handling
───────────────────────────────────────────────────────────────────
def process_hud_node(state: PipelineState) -> PipelineState:
    # Invoke tool
    result = process_hud_tool.invoke({
        "config_json": state["tank_config_json"],
        "output_json": os.path.join(state["output_dir"], "fast_results.json")
    })

    # Check success
    if result["success"]:
        # SUCCESS PATH: Update state with artifacts
        return {
            "hud_results_json": result["results_path"],
            "current_step": "process_hud",
            "completed_steps": state["completed_steps"] + ["process_hud"],
            "processing_stats": {
                **state["processing_stats"],
                "hud_processing": {
                    "tanks_processed": result["tanks_processed"],
                    "duration_seconds": result.get("duration", 0)
                }
            },
            "messages": [AIMessage(f"HUD processing complete: {result['tanks_processed']} tanks")]
        }
    else:
        # ERROR PATH: Log error but continue
        return {
            "current_step": "process_hud",
            "errors": state["errors"] + [f"HUD processing failed: {result['error']}"],
            "warnings": state["warnings"] + ["Pipeline will continue without HUD results"],
            "messages": [AIMessage("HUD processing failed, continuing pipeline")]
        }

Level 3: Graph-Level Recovery
───────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────┐
│  Checkpointer (MemorySaver)                                     │
│  • State saved after each node execution                        │
│  • On failure, resume from last checkpoint                      │
│  • No loss of intermediate artifacts                            │
│                                                                 │
│  Example: Pipeline fails at generate_pdf_node                   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Execution 1 (Failed):                                     │ │
│  │                                                           │ │
│  │ detect_input ✓ → Checkpoint 1                            │ │
│  │ excel_to_json ✓ → Checkpoint 2                           │ │
│  │ validate_json ✓ → Checkpoint 3                           │ │
│  │ process_hud ✓ → Checkpoint 4  (6-8 min elapsed)          │ │
│  │ generate_pdf ✗ → CRASH (disk full)                       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ User fixes disk space, re-runs with same session_id       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Execution 2 (Resumed):                                    │ │
│  │                                                           │ │
│  │ detect_input ⏭️ → Skip (load from Checkpoint 1)          │ │
│  │ excel_to_json ⏭️ → Skip (load from Checkpoint 2)         │ │
│  │ validate_json ⏭️ → Skip (load from Checkpoint 3)         │ │
│  │ process_hud ⏭️ → Skip (load from Checkpoint 4)           │ │
│  │ generate_pdf ✓ → Retry (now succeeds)                    │ │
│  │ update_excel ✓ → Continue pipeline                       │ │
│  │ calculate_distances ✓ → Continue pipeline                │ │
│  │ check_compliance ✓ → Complete                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  RESULT: No need to re-run expensive HUD processing!           │
└─────────────────────────────────────────────────────────────────┘

Level 4: Graceful Degradation
───────────────────────────────────────────────────────────────────
Optional Steps Continue Pipeline Even on Failure:

┌─────────────────────────────────────────────────────────────────┐
│  Critical Steps (MUST succeed):                                 │
│  ├─ detect_input: Required to know file type                    │
│  ├─ excel_to_json: Required for tank data                       │
│  └─ validate_json: Required for data integrity                  │
│                                                                 │
│  Optional Steps (CAN fail):                                     │
│  ├─ process_hud: Pipeline continues without ASD values          │
│  │   • Compliance check will show "No ASD data available"      │
│  │   • User can re-run HUD separately later                    │
│  │                                                             │
│  ├─ generate_pdf: Pipeline continues without PDF report         │
│  │   • All data still in JSON/Excel files                      │
│  │   • PDF can be generated separately later                   │
│  │                                                             │
│  ├─ calculate_distances: Pipeline continues without distances   │
│  │   • Compliance check uses only ASD requirements             │
│  │   • Distance calculation can be added later                 │
│  │                                                             │
│  └─ update_excel: Pipeline continues with separate files        │
│      • HUD results available in JSON                            │
│      • Excel can be manually merged                             │
└─────────────────────────────────────────────────────────────────┘

ERROR CLASSIFICATION
═══════════════════════════════════════════════════════════════════
Error Type          │ Handling Strategy        │ Recovery
────────────────────┼──────────────────────────┼─────────────────────
Input file not found│ FATAL: Stop immediately  │ User must provide file
Invalid file format │ FATAL: Stop after detect │ User must fix file
JSON validation fail│ FATAL: Stop after validate│ User must fix data
HUD timeout         │ WARNING: Continue        │ Re-run with same session
PDF generation fail │ WARNING: Continue        │ Generate PDF separately
Disk full           │ FATAL: Stop at failure   │ Free space, resume
Network error       │ RETRY: Automatic (3x)    │ Exponential backoff
Subprocess crash    │ WARNING: Continue        │ Check logs, retry

RECOVERY COMMANDS
═══════════════════════════════════════════════════════════════════
# Resume failed execution
python pipeline_agent.py tanks.xlsx --session <same_session_id>

# Skip specific step (if needed)
python pipeline_agent.py tanks.xlsx --session <session_id> --skip-hud

# Re-run only failed step
python pipeline_agent.py tanks.xlsx --session <session_id> --only generate_pdf
```

---

## 7. Streaming & WebSocket Communication

```
STREAMING ARCHITECTURE
════════════════════════════════════════════════════════════════════

Local Streaming (CLI):
───────────────────────────────────────────────────────────────────
workflow = create_pipeline_graph()
agent = workflow.compile(checkpointer=MemorySaver())

for event in agent.stream(initial_state, config):
    for node_name, node_state in event.items():
        print(f"[{node_name}] {node_state['current_step']}")
        for msg in node_state.get('messages', []):
            print(f"  {msg.content}")

Output:
[detect_input] detect_input
  Detected Excel input file
[excel_to_json] excel_to_json
  Converted Excel to JSON: 24 tanks
[validate_json] validate_json
  Validation passed with 1 warning
[process_hud] process_hud
  Processing tank 1/24...
  Processing tank 2/24...
  ...


WebSocket Streaming (API):
───────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT (Browser/Frontend)                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ const ws = new WebSocket(                                 │ │
│  │   'ws://localhost:8000/ws/pipeline/agent/session_123'     │ │
│  │ );                                                        │ │
│  │                                                           │ │
│  │ ws.onmessage = (event) => {                               │ │
│  │   const data = JSON.parse(event.data);                    │ │
│  │   console.log(`Step: ${data.current_step}`);              │ │
│  │   updateProgressBar(data.completed_steps.length / 9);     │ │
│  │   displayMessages(data.messages);                         │ │
│  │ };                                                        │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │
                          │ WebSocket connection
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│  SERVER (FastAPI)                                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ @app.websocket("/ws/pipeline/agent/{session_id}")         │ │
│  │ async def agent_stream(                                   │ │
│  │     websocket: WebSocket,                                 │ │
│  │     session_id: str                                       │ │
│  │ ):                                                        │ │
│  │     await websocket.accept()                              │ │
│  │                                                           │ │
│  │     # Create agent with checkpointer                      │ │
│  │     workflow = create_pipeline_graph()                    │ │
│  │     agent = workflow.compile(                             │ │
│  │         checkpointer=MemorySaver()                        │ │
│  │     )                                                     │ │
│  │                                                           │ │
│  │     # Stream events to WebSocket                          │ │
│  │     for event in agent.stream(initial_state, config):     │ │
│  │         for node_name, node_state in event.items():       │ │
│  │             await websocket.send_json({                   │ │
│  │                 "node": node_name,                        │ │
│  │                 "current_step": node_state["current_step"],│ │
│  │                 "completed_steps": node_state["completed_steps"],│ │
│  │                 "tank_count": node_state.get("tank_count", 0),│ │
│  │                 "errors": node_state["errors"],           │ │
│  │                 "warnings": node_state["warnings"],       │ │
│  │                 "messages": [                             │ │
│  │                     {"content": m.content, "type": "ai"}  │ │
│  │                     for m in node_state.get("messages", [])│ │
│  │                 ]                                         │ │
│  │             })                                            │ │
│  │                                                           │ │
│  │     # Send final state                                    │ │
│  │     await websocket.send_json({                           │ │
│  │         "status": "complete",                             │ │
│  │         "artifacts": {                                    │ │
│  │             "tank_config_json": final_state["tank_config_json"],│ │
│  │             "compliance_excel": final_state["compliance_excel"]│ │
│  │         }                                                 │ │
│  │     })                                                    │ │
│  │                                                           │ │
│  │     await websocket.close()                               │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

MESSAGE FLOW TIMELINE
═══════════════════════════════════════════════════════════════════
Time  │ Event                       │ WebSocket Message
──────┼─────────────────────────────┼────────────────────────────────
t=0   │ Connection established      │ { status: "connected" }
t=1   │ detect_input completed      │ { node: "detect_input",
      │                             │   current_step: "detect_input",
      │                             │   completed_steps: [1/9] }
t=2   │ excel_to_json in progress   │ { node: "excel_to_json",
      │                             │   messages: ["Converting..."] }
t=30  │ excel_to_json completed     │ { node: "excel_to_json",
      │                             │   tank_count: 24,
      │                             │   completed_steps: [2/9] }
t=31  │ validate_json completed     │ { node: "validate_json",
      │                             │   completed_steps: [3/9] }
t=32  │ process_hud started         │ { node: "process_hud",
      │                             │   messages: ["Starting HUD..."] }
t=50  │ process_hud progress (tank 1)│ { node: "process_hud",
      │                             │   messages: ["Tank 1/24 done"] }
t=68  │ process_hud progress (tank 2)│ { node: "process_hud",
      │                             │   messages: ["Tank 2/24 done"] }
...   │ ...                         │ ...
t=456 │ process_hud completed       │ { node: "process_hud",
      │                             │   completed_steps: [4/9] }
...   │ ...                         │ ...
t=480 │ All steps complete          │ { status: "complete",
      │                             │   artifacts: {...} }

FRONTEND RENDERING
═══════════════════════════════════════════════════════════════════
┌─────────────────────────────────────────────────────────────────┐
│  Pipeline Progress                                              │
│  ────────────────────────────────────────────────────────────── │
│  ✓ Detect Input            [██████████] 100%                    │
│  ✓ Excel to JSON           [██████████] 100%                    │
│  ✓ Validate JSON           [██████████] 100%                    │
│  ⏳ Process HUD            [████████░░] 80% (19/24 tanks)       │
│  ⏱️  Generate PDF          [░░░░░░░░░░] 0%                      │
│  ⏱️  Update Excel          [░░░░░░░░░░] 0%                      │
│  ⏱️  Calculate Distances   [░░░░░░░░░░] 0%                      │
│  ⏱️  Check Compliance      [░░░░░░░░░░] 0%                      │
│  ⏱️  Summarize Results     [░░░░░░░░░░] 0%                      │
│  ────────────────────────────────────────────────────────────── │
│  Messages:                                                      │
│  • Processing tank T-19 (19/24)                                 │
│  • ASD calculation complete for T-18                            │
│  • Estimated time remaining: 2 minutes                          │
│  ────────────────────────────────────────────────────────────── │
│  Warnings:                                                      │
│  ⚠️  Tank T-05 missing height dimension                         │
└─────────────────────────────────────────────────────────────────┘

STREAMING BENEFITS
═══════════════════════════════════════════════════════════════════
✓ Real-time progress updates (no polling)
✓ Immediate error visibility
✓ Better user experience for long-running tasks
✓ Can cancel/interrupt in progress
✓ Bandwidth efficient (events only on change)
✓ Works across network boundaries
✓ Compatible with LangSmith tracing
```

---

## 8. Memory & Checkpointing

```
CHECKPOINTING SYSTEM
════════════════════════════════════════════════════════════════════

In-Memory Checkpointer (MemorySaver):
───────────────────────────────────────────────────────────────────
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = workflow.compile(checkpointer=checkpointer)

Data Structure:
┌─────────────────────────────────────────────────────────────────┐
│  MemorySaver Internal State                                     │
│  {                                                              │
│    "session_123": {                                             │
│      "checkpoints": [                                           │
│        {                                                        │
│          "checkpoint_id": "cp_0",                               │
│          "node": "detect_input",                                │
│          "timestamp": 1706553600.0,                             │
│          "state": {                                             │
│            "input_type": "excel",                               │
│            "current_step": "detect_input",                      │
│            "completed_steps": ["detect_input"],                 │
│            ...                                                  │
│          }                                                      │
│        },                                                       │
│        {                                                        │
│          "checkpoint_id": "cp_1",                               │
│          "node": "excel_to_json",                               │
│          "timestamp": 1706553630.0,                             │
│          "state": {                                             │
│            "tank_config_json": "outputs/tank_config.json",      │
│            "tank_count": 24,                                    │
│            "current_step": "excel_to_json",                     │
│            "completed_steps": ["detect_input", "excel_to_json"],│
│            ...                                                  │
│          }                                                      │
│        },                                                       │
│        ...                                                      │
│      ],                                                         │
│      "current_checkpoint_id": "cp_4"                            │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘

Checkpoint Lifecycle:
───────────────────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────┐
│  Node Execution Cycle                                          │
│                                                                │
│  1. LOAD CHECKPOINT                                            │
│     ┌──────────────────────────────────────────────────────┐  │
│     │ state = checkpointer.load(session_id)                │  │
│     │ if state:                                            │  │
│     │     print("Resuming from checkpoint")                │  │
│     │     return state                                     │  │
│     │ else:                                                │  │
│     │     return initial_state                             │  │
│     └──────────────────────────────────────────────────────┘  │
│                          │                                     │
│  2. EXECUTE NODE         │                                     │
│     ┌──────────────────▼─────────────────────────────────┐   │
│     │ new_state = excel_to_json_node(state)              │   │
│     └──────────────────┬─────────────────────────────────┘   │
│                        │                                      │
│  3. SAVE CHECKPOINT    │                                      │
│     ┌──────────────────▼─────────────────────────────────┐   │
│     │ checkpointer.save(                                 │   │
│     │     session_id=session_id,                         │   │
│     │     checkpoint_id=generate_checkpoint_id(),        │   │
│     │     state=new_state,                               │   │
│     │     node="excel_to_json",                          │   │
│     │     timestamp=time.time()                          │   │
│     │ )                                                  │   │
│     └──────────────────┬─────────────────────────────────┘   │
│                        │                                      │
│  4. ROUTE TO NEXT NODE │                                      │
│     ┌──────────────────▼─────────────────────────────────┐   │
│     │ next_node = router(new_state)                      │   │
│     │ workflow.transition_to(next_node)                  │   │
│     └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘

Resume on Failure Example:
───────────────────────────────────────────────────────────────────
Initial Run:
┌────────────────────────────────────────────────────────────────┐
│  python pipeline_agent.py tanks.xlsx --session abc123         │
│                                                                │
│  [detect_input] ✓ → Checkpoint saved (cp_0)                   │
│  [excel_to_json] ✓ → Checkpoint saved (cp_1)                  │
│  [validate_json] ✓ → Checkpoint saved (cp_2)                  │
│  [process_hud] ✓ → Checkpoint saved (cp_3)                    │
│  [generate_pdf] ✗ → CRASH (out of memory)                     │
│                                                                │
│  State at cp_3:                                                │
│  {                                                             │
│    "tank_config_json": "outputs/tank_config.json",             │
│    "hud_results_json": "outputs/fast_results.json",  ← SAVED! │
│    "completed_steps": [..., "process_hud"],                    │
│    ...                                                         │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘

Resume Run:
┌────────────────────────────────────────────────────────────────┐
│  python pipeline_agent.py tanks.xlsx --session abc123         │
│                                                                │
│  [detect_input] ⏭️ Skipped (loaded from cp_0)                 │
│  [excel_to_json] ⏭️ Skipped (loaded from cp_1)                │
│  [validate_json] ⏭️ Skipped (loaded from cp_2)                │
│  [process_hud] ⏭️ Skipped (loaded from cp_3) ← 6-8 min saved! │
│  [generate_pdf] ✓ → Retry (now succeeds)                      │
│  [update_excel] ✓ → Continue                                  │
│  [calculate_distances] ✓ → Continue                           │
│  [check_compliance] ✓ → Complete                              │
└────────────────────────────────────────────────────────────────┘

Persistent Checkpointers:
───────────────────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────┐
│  SQLite Checkpointer (Production)                              │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ from langgraph.checkpoint.sqlite import SqliteSaver      │ │
│  │                                                          │ │
│  │ checkpointer = SqliteSaver(                              │ │
│  │     db_path="pipeline_checkpoints.db"                    │ │
│  │ )                                                        │ │
│  │ agent = workflow.compile(checkpointer=checkpointer)      │ │
│  │                                                          │ │
│  │ Benefits:                                                │ │
│  │ • Persists across server restarts                        │ │
│  │ • Survives crashes                                       │ │
│  │ • Multiple sessions supported                            │ │
│  │ • Query checkpoint history                               │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  PostgreSQL Checkpointer (Enterprise)                          │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ from langgraph.checkpoint.postgres import PostgresSaver  │ │
│  │                                                          │ │
│  │ checkpointer = PostgresSaver(                            │ │
│  │     connection_string="postgresql://..."                 │ │
│  │ )                                                        │ │
│  │ agent = workflow.compile(checkpointer=checkpointer)      │ │
│  │                                                          │ │
│  │ Benefits:                                                │ │
│  │ • Distributed checkpointing                              │ │
│  │ • Concurrent access                                      │ │
│  │ • High availability                                      │ │
│  │ • Audit trail                                            │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘

Time-Travel Debugging:
───────────────────────────────────────────────────────────────────
# Get all checkpoints for a session
checkpoints = checkpointer.list_checkpoints(session_id="abc123")

for cp in checkpoints:
    print(f"Checkpoint {cp['checkpoint_id']} at {cp['node']}")
    print(f"  Tank count: {cp['state']['tank_count']}")
    print(f"  Completed: {len(cp['state']['completed_steps'])}/9 steps")

# Load specific checkpoint
state_at_validation = checkpointer.load(
    session_id="abc123",
    checkpoint_id="cp_2"
)

# Continue from that point
agent.stream(state_at_validation, config)
```

---

## 9. Tool Dependencies

```
TOOL DEPENDENCY GRAPH
════════════════════════════════════════════════════════════════════

External Dependencies (Python Packages):
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  fastapi, uvicorn              ← API server                     │
│  pandas, openpyxl, xlrd        ← Excel processing               │
│  Pillow, reportlab             ← PDF generation                 │
│  playwright                    ← Browser automation             │
│  openai, langchain, langgraph  ← LLM & orchestration            │
│  numpy, scipy                  ← Math operations                │
│  requests, httpx               ← HTTP client                    │
│  orjson                        ← Fast JSON parsing              │
│  python-dotenv, pydantic       ← Utilities                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Tool → Script Dependencies:
───────────────────────────────────────────────────────────────────
┌──────────────────────────────────────────────────────────────────┐
│  Tool                      Script                  Dependencies   │
├──────────────────────────────────────────────────────────────────┤
│  parse_kmz_tool        →   kmz_parser_agent.py                   │
│                            ├─ zipfile (stdlib)                   │
│                            ├─ xml.etree (stdlib)                 │
│                            ├─ langchain (LLM parsing)            │
│                            └─ openai (GPT-4)                     │
├──────────────────────────────────────────────────────────────────┤
│  excel_to_json_tool    →   excel_to_json_improved.py            │
│                            ├─ pandas (Excel I/O)                 │
│                            ├─ openpyxl (XLSX format)             │
│                            ├─ volume_calculator.py               │
│                            │  └─ numpy (unit conversions)        │
│                            ├─ langchain (header mapping)         │
│                            └─ openai (GPT-4 for ambiguity)       │
├──────────────────────────────────────────────────────────────────┤
│  validate_json_tool    →   validate_tank_json.py                │
│                            ├─ jsonschema (validation)            │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  process_hud_tool      →   fast_hud_processor.py                │
│                            ├─ playwright (browser control)       │
│                            ├─ asyncio (async operations)         │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  generate_pdf_tool     →   generate_pdf.py                      │
│                            ├─ reportlab (PDF creation)           │
│                            ├─ Pillow (image processing)          │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  update_excel_tool     →   update_excel_with_results.py         │
│                            ├─ pandas (DataFrame operations)      │
│                            ├─ openpyxl (Excel writing)           │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  calculate_distances_  →   calculate_distances.py               │
│  tool                      ├─ geopy (geospatial calc)            │
│                            ├─ shapely (polygon operations)       │
│                            ├─ numpy (vector math)                │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  check_compliance_tool →   compliance_checker.py                │
│                            ├─ pandas (data analysis)             │
│                            ├─ openpyxl (Excel output)            │
│                            └─ json (stdlib)                      │
├──────────────────────────────────────────────────────────────────┤
│  calculate_volume_tool →   volume_calculator.py (direct import) │
│                            └─ numpy (calculations)               │
├──────────────────────────────────────────────────────────────────┤
│  human_approval_tool   →   (inline implementation)              │
│                            └─ input() (stdlib)                   │
└──────────────────────────────────────────────────────────────────┘

Data Flow Dependencies:
───────────────────────────────────────────────────────────────────
        INPUT FILE
           │
           ├─── tanks.xlsx OR tanks.kmz
           │
           ▼
    parse_kmz_tool (if KMZ)
           │
           ├─── boundary.geojson
           │
           ▼
    excel_to_json_tool
           │
           ├─── tank_config.json ◄────────┐
           │                              │
           ▼                              │
    validate_json_tool                    │
           │                              │
           ▼                              │
    process_hud_tool                      │
           │              Reads tank_config.json
           ├─── fast_results.json         │
           │                              │
           ▼                              │
    generate_pdf_tool ──────┐             │
           │                │             │
           ├─── HUD_ASD_Results.pdf       │
           │                │             │
           ▼                │             │
    update_excel_tool ◄─────┤             │
           │                └─ Reads fast_results.json
           ├─── with_hud.xlsx
           │
           ▼
    calculate_distances_tool ◄─ Reads boundary.geojson
           │
           ├─── distances.json
           │
           ▼
    check_compliance_tool ◄───┬─ Reads with_hud.xlsx
           │                  └─ Reads distances.json
           ├─── final_compliance.xlsx
           │
           ▼
        OUTPUT FILES

Critical Path Analysis:
───────────────────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────┐
│  Blocking Dependencies (must complete in order):               │
│                                                                │
│  1. Input file → parse_kmz OR excel_to_json                   │
│     ├─ Cannot proceed without valid input file                │
│     └─ KMZ must be parsed before Excel conversion             │
│                                                                │
│  2. tank_config.json → validate_json                          │
│     ├─ Validation requires JSON structure                     │
│     └─ Cannot process HUD without valid tank data             │
│                                                                │
│  3. tank_config.json → process_hud                            │
│     ├─ HUD processor reads tank dimensions                    │
│     └─ LONGEST STEP (6-8 minutes for 24 tanks)                │
│                                                                │
│  4. fast_results.json → generate_pdf, update_excel            │
│     ├─ PDF needs HUD results for screenshots                  │
│     └─ Excel update merges HUD results                        │
│                                                                │
│  5. with_hud.xlsx + distances.json → check_compliance         │
│     ├─ Compliance needs ASD values from with_hud.xlsx         │
│     └─ Compliance needs distances from distances.json         │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Parallelizable Steps (could run concurrently):                │
│                                                                │
│  • generate_pdf + update_excel (both read fast_results.json)  │
│    ├─ PDF creation is I/O bound                               │
│    └─ Excel update is CPU bound                               │
│                                                                │
│  Future Enhancement: Parallel HUD processing                   │
│  • Split tanks into batches                                   │
│  • Multiple browser instances                                 │
│  • Aggregate results at end                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 10. Complete Data Flow

```
END-TO-END DATA TRANSFORMATION
════════════════════════════════════════════════════════════════════

INPUT: tanks.xlsx
─────────────────────────────────────────────────────────────────
┌───────────────────────────────────────────────────────────────┐
│ Excel File Structure:                                         │
│                                                               │
│ | Tanque | Largo | Ancho | Alto | Capacidad | Producto | ... │
│ |--------|-------|-------|------|-----------|----------|-----│
│ | T-01   | 30 ft | 20 ft | 15 ft| 50000 gal | Diesel   | ... │
│ | T-02   | 25'   | 18'   | 12'  | 35000 gal | Gasoline | ... │
│ | ...    | ...   | ...   | ...  | ...       | ...      | ... │
│                                                               │
│ Problems to solve:                                            │
│ • Spanish column names (40+ variations)                       │
│ • Mixed units (ft, ', m, pies, feet)                          │
│ • Missing dimensions                                          │
│ • Inconsistent formatting                                     │
└───────────────────────────────────────────────────────────────┘

TRANSFORMATION 1: excel_to_json_tool
─────────────────────────────────────────────────────────────────
Process:
1. LangChain agent maps Spanish headers → English
2. VolumeCalculator normalizes units → feet
3. Calculate volume if missing: V = L × W × H × 7.48052
4. Validate reasonable dimensions

Output: tank_config.json
┌───────────────────────────────────────────────────────────────┐
│ {                                                             │
│   "tanks": [                                                  │
│     {                                                         │
│       "id": "T-01",                                           │
│       "dimensions": {                                         │
│         "length": 30.0,                                       │
│         "width": 20.0,                                        │
│         "height": 15.0,                                       │
│         "unit": "ft"                                          │
│       },                                                      │
│       "volume_gallons": 50000.0,                              │
│       "volume_source": "calculated",  ← or "excel"            │
│       "product": "Diesel",                                    │
│       "coordinates": {                                        │
│         "latitude": 18.2342,                                  │
│         "longitude": -66.1234                                 │
│       }                                                       │
│     },                                                        │
│     {                                                         │
│       "id": "T-02",                                           │
│       "dimensions": {                                         │
│         "length": 25.0,                                       │
│         "width": 18.0,                                        │
│         "height": 12.0,                                       │
│         "unit": "ft"                                          │
│       },                                                      │
│       "volume_gallons": 35000.0,                              │
│       "volume_source": "calculated",                          │
│       "product": "Gasoline",                                  │
│       "coordinates": {                                        │
│         "latitude": 18.2344,                                  │
│         "longitude": -66.1236                                 │
│       }                                                       │
│     }                                                         │
│   ],                                                          │
│   "metadata": {                                               │
│     "total_tanks": 24,                                        │
│     "source_file": "tanks.xlsx",                              │
│     "timestamp": "2025-01-29T10:30:00Z"                       │
│   }                                                           │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘

TRANSFORMATION 2: validate_json_tool
─────────────────────────────────────────────────────────────────
Validation:
✓ Required fields: id, dimensions, volume_gallons
✓ Dimension constraints: 5 ft < L,W,H < 200 ft
✓ Volume constraints: 100 gal < V < 500,000 gal
✓ Coordinates: valid lat/lon ranges
⚠ Warnings collected (e.g., missing height)

TRANSFORMATION 3: process_hud_tool
─────────────────────────────────────────────────────────────────
Process:
For each tank:
1. Open Playwright browser → HUD site
2. Fill tank dimensions (L, W, H)
3. Select product type
4. Click "Calculate ASD"
5. Screenshot result
6. Extract ASD values (ASD1, ASD2, ASD3)

Output: fast_results.json
┌───────────────────────────────────────────────────────────────┐
│ {                                                             │
│   "tanks": [                                                  │
│     {                                                         │
│       "tank_id": "T-01",                                      │
│       "asd_values": {                                         │
│         "ASD1": 120.5,  ← Inhabited Building Distance (ft)    │
│         "ASD2": 85.3,   ← Public Railway Distance (ft)        │
│         "ASD3": 42.7    ← Public Highway Distance (ft)        │
│       },                                                      │
│       "screenshot": "outputs/screenshots/T-01_hud.png",       │
│       "calculation_time": 18.2  ← seconds                     │
│     },                                                        │
│     {                                                         │
│       "tank_id": "T-02",                                      │
│       "asd_values": {                                         │
│         "ASD1": 105.2,                                        │
│         "ASD2": 74.1,                                         │
│         "ASD3": 37.0                                          │
│       },                                                      │
│       "screenshot": "outputs/screenshots/T-02_hud.png",       │
│       "calculation_time": 19.5                                │
│     }                                                         │
│   ],                                                          │
│   "processing_stats": {                                       │
│     "total_tanks": 24,                                        │
│     "successful": 24,                                         │
│     "failed": 0,                                              │
│     "total_time_seconds": 456.8,                              │
│     "avg_time_per_tank": 19.0                                 │
│   }                                                           │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘

TRANSFORMATION 4: generate_pdf_tool
─────────────────────────────────────────────────────────────────
Process:
1. Read fast_results.json + tank_config.json
2. For each tank, create PDF page with:
   • Tank info (ID, dimensions, volume)
   • ASD calculation results
   • Screenshot from HUD
3. Combine into single PDF

Output: HUD_ASD_Results.pdf (visual report)

TRANSFORMATION 5: update_excel_tool
─────────────────────────────────────────────────────────────────
Process:
1. Load original Excel file
2. Add new columns: ASD1, ASD2, ASD3
3. Merge ASD values from fast_results.json
4. Preserve original formatting

Output: with_hud.xlsx
┌───────────────────────────────────────────────────────────────┐
│ Excel File Structure (UPDATED):                               │
│                                                               │
│ | Tanque | Largo | Ancho | Alto | Capacidad | ASD1  | ASD2  | ASD3 |│
│ |--------|-------|-------|------|-----------|-------|-------|------|│
│ | T-01   | 30 ft | 20 ft | 15 ft| 50000 gal | 120.5 | 85.3  | 42.7 |│
│ | T-02   | 25'   | 18'   | 12'  | 35000 gal | 105.2 | 74.1  | 37.0 |│
│ | ...    | ...   | ...   | ...  | ...       | ...   | ...   | ...  |│
│                                                               │
│ New columns added ────────────────────────────^───────^──────^     │
└───────────────────────────────────────────────────────────────┘

TRANSFORMATION 6: calculate_distances_tool
─────────────────────────────────────────────────────────────────
Process:
1. Read boundary polygon from boundary.geojson
2. For each tank coordinate:
   • Calculate distance to nearest polygon edge
   • Calculate distance to inhabited buildings
   • Calculate distance to highways
3. Use geopy/shapely for calculations

Output: distances.json
┌───────────────────────────────────────────────────────────────┐
│ {                                                             │
│   "tanks": [                                                  │
│     {                                                         │
│       "tank_id": "T-01",                                      │
│       "distances": {                                          │
│         "to_boundary": 245.8,        ← feet                   │
│         "to_nearest_building": 150.2,                         │
│         "to_nearest_highway": 89.5                            │
│       }                                                       │
│     },                                                        │
│     {                                                         │
│       "tank_id": "T-02",                                      │
│       "distances": {                                          │
│         "to_boundary": 198.4,                                 │
│         "to_nearest_building": 125.7,                         │
│         "to_nearest_highway": 76.3                            │
│       }                                                       │
│     }                                                         │
│   ]                                                           │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘

TRANSFORMATION 7: check_compliance_tool
─────────────────────────────────────────────────────────────────
Process:
1. Read with_hud.xlsx (ASD values)
2. Read distances.json (actual distances)
3. For each tank, compare:
   • Actual distance to building vs ASD1
   • Actual distance to railway vs ASD2
   • Actual distance to highway vs ASD3
4. Determine compliance: YES / NO / REVIEW

Output: final_compliance.xlsx
┌───────────────────────────────────────────────────────────────┐
│ Excel File Structure (FINAL):                                 │
│                                                               │
│ | Tank | Capacity | ASD1  | Actual  | Compliance | Status  | │
│ |      |          |(req'd)| Distance| Building   |         | │
│ |------|----------|-------|---------|------------|---------|  │
│ | T-01 | 50000 gal| 120.5 | 150.2   | YES        | ✓ PASS  | │
│ | T-02 | 35000 gal| 105.2 | 125.7   | YES        | ✓ PASS  | │
│ | T-03 | 40000 gal| 110.0 | 95.3    | NO         | ✗ FAIL  | │
│ | T-04 | 30000 gal| 100.0 | 102.1   | YES        | ✓ PASS  | │
│ | ...  | ...      | ...   | ...     | ...        | ...     | │
│                                                               │
│ Summary:                                                      │
│ • Total tanks: 24                                             │
│ • Compliant: 22 (92%)                                         │
│ • Non-compliant: 2 (8%)                                       │
│ • Require review: 0                                           │
└───────────────────────────────────────────────────────────────┘

FINAL OUTPUT FILES
═══════════════════════════════════════════════════════════════════
outputs/
├── tank_config.json           # Structured tank data
├── fast_results.json          # HUD ASD calculations
├── HUD_ASD_Results.pdf        # Visual PDF report
├── with_hud.xlsx              # Excel with ASD columns
├── distances.json             # Geospatial distances
├── final_compliance.xlsx      # Compliance assessment ← DELIVERABLE
└── screenshots/
    ├── T-01_hud.png
    ├── T-02_hud.png
    └── ...

DATA QUALITY METRICS
═══════════════════════════════════════════════════════════════════
Volume Calculation Accuracy:
├─ Calculated from dimensions: 100% accurate (VolumeCalculator)
├─ Used from Excel: Depends on source data quality
└─ Validation: Reasonable range checks applied

ASD Calculation Accuracy:
├─ HUD website: Official source (100% reliable)
├─ Extraction: Screenshot + DOM parsing (99%+ reliable)
└─ Verification: Screenshot saved for manual review

Distance Calculation Accuracy:
├─ Geopy: WGS84 ellipsoid calculations (high precision)
├─ Shapely: Computational geometry (exact)
└─ Limitation: Accuracy depends on coordinate precision

Overall Pipeline Success Rate:
├─ 24/24 tanks processed (100%)
├─ 0 critical errors
├─ 1 warning (missing dimension, handled gracefully)
└─ Total execution time: 8.2 minutes
```

---

## Summary

This visual guide covers all aspects of the LangGraph Pipeline Agent:

1. **Architecture** - Layered design with clear separation of concerns
2. **Pipeline Flow** - Complete node graph with timing metrics
3. **State Management** - TypedDict evolution through execution
4. **Tool Pattern** - Subprocess wrappers with error handling
5. **Routing Logic** - Conditional edges based on state
6. **Error Handling** - Multi-level strategy with graceful degradation
7. **Streaming** - Real-time WebSocket progress updates
8. **Checkpointing** - Persistence and resume capabilities
9. **Dependencies** - Complete dependency graph
10. **Data Flow** - End-to-end transformations with examples

Use these diagrams as reference when:
- Debugging pipeline execution
- Explaining system to stakeholders
- Planning enhancements
- Training new developers
- Designing API integrations

---

**Created**: 2025-09-29
**Version**: 1.0.0
**Author**: Pipeline Agent Documentation Team