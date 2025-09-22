#!/usr/bin/env bash
set -euo pipefail

# End-to-end run inside the isolated folder
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

INPUT_EXCEL=""
POLYGON_FILE=""
OUT_DIR="$ROOT_DIR/output"

usage() {
  cat <<USAGE
Usage: $0 -i tank_measurements_filled.xlsx [-p polygon.txt]

Options:
  -i  Path to Excel with measurements (required)
  -p  Polygon boundary .txt for distance calc (optional)
  -h  Help

Environment:
  OPENAI_API_KEY must be set for Excel→JSON parsing.

Outputs (in output/):
  - fast_results.json
  - HUD_ASD_Results.pdf
  - with_hud.xlsx
  - final_compliance.xlsx (or compliance_no_dist.xlsx if no polygon)
USAGE
}

while getopts ":i:p:h" opt; do
  case $opt in
    i) INPUT_EXCEL="$OPTARG" ;;
    p) POLYGON_FILE="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Option -$OPTARG requires an argument" >&2; usage; exit 1 ;;
    *) echo "Unknown option -$OPTARG" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$INPUT_EXCEL" ]]; then
  echo "[run] Missing -i input Excel"
  usage
  exit 1
fi

if [[ ! -f "$INPUT_EXCEL" ]]; then
  echo "[run] Input Excel not found: $INPUT_EXCEL" >&2
  exit 1
fi

# Ensure modules are present
if [[ ! -f fast_hud_processor.py ]]; then
  echo "[run] Modules not found. Running setup_isolated.sh ..."
  bash ./setup_isolated.sh
fi

mkdir -p .playwright-mcp work "$OUT_DIR"

# Sanity checks
if ! command -v python >/dev/null 2>&1; then
  echo "[run] python not found in PATH" >&2
  exit 1
fi

if ! python -c "import playwright" >/dev/null 2>&1; then
  echo "[run] Playwright not installed. Run: pip install -r requirements.txt && playwright install chromium" >&2
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[run] OPENAI_API_KEY not set (required for Excel→JSON)" >&2
  exit 1
fi

# 1) Copy input Excel into work/ for a clean run context
WORK_EXCEL="work/$(basename "$INPUT_EXCEL")"
cp "$INPUT_EXCEL" "$WORK_EXCEL"

echo "[run] Step 1: Excel → JSON"
python excel_to_json_langgraph.py "$WORK_EXCEL" -o tank_config.json

echo "[run] Step 2: Validate JSON"
python validate_tank_json.py tank_config.json

echo "[run] Step 3: HUD processor (screenshots + fast_results.json)"
python fast_hud_processor.py --config tank_config.json

echo "[run] Step 4: PDF generation (summary)"
python generate_pdf.py --summary -o "$OUT_DIR/HUD_ASD_Results.pdf"

echo "[run] Step 5: Update Excel with HUD results"
python update_excel_with_results.py "$WORK_EXCEL" fast_results.json -o "$OUT_DIR/with_hud.xlsx"

echo "[run] Step 6: Compliance assessment"
if [[ -n "$POLYGON_FILE" ]]; then
  if [[ ! -f "$POLYGON_FILE" ]]; then
    echo "[run] Polygon file not found: $POLYGON_FILE" >&2
    exit 1
  fi
  python compliance_checker.py "$OUT_DIR/with_hud.xlsx" fast_results.json --polygon "$POLYGON_FILE" -o "$OUT_DIR/final_compliance.xlsx"
else
  python compliance_checker.py "$OUT_DIR/with_hud.xlsx" fast_results.json --no-distances -o "$OUT_DIR/compliance_no_dist.xlsx"
fi

echo "[run] Done. Outputs in: $OUT_DIR"
ls -1 "$OUT_DIR" || true
