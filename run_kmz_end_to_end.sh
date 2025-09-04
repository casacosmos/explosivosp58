#!/usr/bin/env bash
set -euo pipefail

# One-click KMZ → Excel (with mocks) → JSON (LLM) → HUD → Update Excel → Compliance
# Defaults to limiting HUD to a small number of tanks for quick testing.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

KMZ_FILE=""
MAX_TANKS=8
USE_MOCKS=1
POLYGON_FILE=""
OUT_DIR_BASE="$ROOT_DIR/output/kmz_run_$(date +%Y%m%d_%H%M%S)"

usage() {
  cat <<USAGE
Usage: $0 -k file.kmz [-n max_tanks] [-p polygon.txt] [--no-mocks]

Options:
  -k  Path to KMZ/KML file (required)
  -n  Max number of tanks to process in HUD (default: $MAX_TANKS)
  -p  Polygon boundary .txt (lon,lat per line). If omitted, uses parsed polygon if available.
  --no-mocks  Do not inject mock measurements (expects Excel to already contain capacities/measurements)
  -h  Help

Environment:
  OPENAI_API_KEY must be set for Excel→JSON (LLM) parsing.
  Activate your venv first if needed, e.g.:
    . ~/Apps/explosivoseval/.venv/bin/activate

Outputs:
  Created under a timestamped folder in output/ with all artifacts.
USAGE
}

while (("$#")); do
  case "$1" in
    -k) KMZ_FILE="$2"; shift 2;;
    -n) MAX_TANKS="$2"; shift 2;;
    -p) POLYGON_FILE="$2"; shift 2;;
    --no-mocks) USE_MOCKS=0; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$KMZ_FILE" ]]; then
  echo "[run] Missing -k KMZ file" >&2
  usage
  exit 1
fi
if [[ ! -f "$KMZ_FILE" ]]; then
  echo "[run] KMZ not found: $KMZ_FILE" >&2
  exit 1
fi

mkdir -p "$OUT_DIR_BASE" work .playwright-mcp

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[run] OPENAI_API_KEY not set (required for Excel→JSON LLM)" >&2
  exit 1
fi

if ! python -c "import playwright" >/dev/null 2>&1; then
  echo "[run] Playwright not installed. Run: pip install -r requirements.txt && playwright install chromium" >&2
  exit 1
fi

echo "[1/7] KMZ → Excel template + polygon"
python kmz_parser_agent.py "$KMZ_FILE" -o "$OUT_DIR_BASE"

TEMPLATE_EXCEL=$(ls -1 "$OUT_DIR_BASE"/tank_locations_*.xlsx | head -n1)
if [[ -z "$TEMPLATE_EXCEL" ]]; then
  echo "[run] No template Excel produced" >&2
  exit 1
fi

# Try to pick polygon if not provided
if [[ -z "$POLYGON_FILE" ]]; then
  POLYGON_FILE=$(ls -1 "$OUT_DIR_BASE"/polygon_*.txt 2>/dev/null | head -n1 || true)
fi

EXCEL_WITH_DATA="$OUT_DIR_BASE/tank_locations_with_measurements.xlsx"
if [[ "$USE_MOCKS" == "1" ]]; then
  echo "[2/7] Injecting simple mock measurements into Excel"
  python - <<PY
from hud_tank_pipeline.add_simple_mock_measurements import add_simple_mock_measurements
add_simple_mock_measurements(r"$TEMPLATE_EXCEL", r"$EXCEL_WITH_DATA")
print('OK')
PY
else
  cp "$TEMPLATE_EXCEL" "$EXCEL_WITH_DATA"
fi

echo "[3/7] Excel → JSON (LLM)"
CONFIG_JSON="$OUT_DIR_BASE/tank_config.json"
python excel_to_json_langgraph.py "$EXCEL_WITH_DATA" -o "$CONFIG_JSON"

echo "[4/7] Limiting to $MAX_TANKS tank(s) for quick HUD test"
LIMITED_JSON="$OUT_DIR_BASE/tank_config_limited.json"
python - <<PY
import json
src=r"$CONFIG_JSON"; dst=r"$LIMITED_JSON"; n=int($MAX_TANKS)
data=json.load(open(src))
data['tanks']=data.get('tanks',[])[:n]
json.dump(data, open(dst,'w'), indent=2)
print(f"Limited tanks: {len(data['tanks'])}")
PY

echo "[5/7] HUD ASD run (config: $LIMITED_JSON)"
python fast_hud_processor.py --config "$LIMITED_JSON"

echo "[6/7] Update Excel with HUD results"
python update_excel_with_results.py "$EXCEL_WITH_DATA" fast_results.json -o "$OUT_DIR_BASE/with_hud.xlsx"

echo "[7/7] Compliance assessment"
if [[ -n "$POLYGON_FILE" && -f "$POLYGON_FILE" ]]; then
  python compliance_checker.py "$OUT_DIR_BASE/with_hud.xlsx" fast_results.json --polygon "$POLYGON_FILE" -o "$OUT_DIR_BASE/final_compliance.xlsx"
else
  python compliance_checker.py "$OUT_DIR_BASE/with_hud.xlsx" fast_results.json --no-distances -o "$OUT_DIR_BASE/compliance_no_dist.xlsx"
fi

echo "\n[run] Done. Outputs in: $OUT_DIR_BASE"
ls -1 "$OUT_DIR_BASE" || true

