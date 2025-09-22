#!/usr/bin/env bash
set -euo pipefail

# Initialize an isolated copy of the working pipeline modules
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="${ROOT_DIR}"
REPO_DIR="${ROOT_DIR}/.."

echo "[setup] Preparing isolated pipeline in ${SRC_DIR}"

need() {
  local f="$1"; shift
  if [[ ! -f "$f" ]]; then echo "[setup] missing: $f"; return 1; fi
}

copy_if_changed() {
  local src="$1" dst="$2"
  if [[ ! -f "$src" ]]; then echo "[setup] WARN: source not found: $src"; return; fi
  if [[ ! -f "$dst" ]] || ! cmp -s "$src" "$dst"; then
    cp "$src" "$dst"
    echo "[setup] copied: $(basename "$src")"
  fi
}

mkdir -p "${SRC_DIR}/.playwright-mcp" "${SRC_DIR}/work" "${SRC_DIR}/output"

# Source locations
HP="${REPO_DIR}/hud_tank_pipeline"
DC="${REPO_DIR}/catano_distance_calculator"

# Files to copy from hud_tank_pipeline
FILES=(
  "kmz_parser_agent.py"
  "kmz_parser_langgraph.py"
  "excel_to_json_langgraph.py"
  "validate_tank_json.py"
  "fast_hud_processor.py"
  "generate_pdf.py"
  "update_excel_with_results.py"
  "compliance_checker.py"
)

for f in "${FILES[@]}"; do
  copy_if_changed "${HP}/${f}" "${SRC_DIR}/${f}"
done

# Copy distance calc dependency
copy_if_changed "${DC}/calculate_distances.py" "${SRC_DIR}/calculate_distances.py"

# Optional utility
if [[ -f "${HP}/tank_volume_calculator.py" ]]; then
  copy_if_changed "${HP}/tank_volume_calculator.py" "${SRC_DIR}/tank_volume_calculator.py"
fi

# Tweak compliance_checker to import local calculate_distances (comment out external sys.path append)
if grep -q "catano_distance_calculator" "${SRC_DIR}/compliance_checker.py" >/dev/null 2>&1; then
  sed -i.bak "s/^sys.path.append.*catano_distance_calculator.*/# (isolated) sys.path injection removed/" "${SRC_DIR}/compliance_checker.py" || true
  rm -f "${SRC_DIR}/compliance_checker.py.bak"
fi

echo "[setup] done. Copied working modules into $(basename "$SRC_DIR")."
echo "[setup] Next: create venv, install requirements, run playwright install chromium"
