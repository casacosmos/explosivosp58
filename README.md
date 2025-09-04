HUD Tank Pipeline (Isolated)

This folder provides a minimal, self-contained copy of the working HUD Tank pipeline so you can focus on developing the actual code without the rest of the repo.

Contents are created by running `setup_isolated.sh`, which copies the required scripts from `hud_tank_pipeline/` and `catano_distance_calculator/` into this folder. The `run.sh` script executes the complete pipeline end-to-end using only files placed here.

Quickstart
- Create venv and install deps: `pip install -r requirements.txt` and `playwright install chromium`.
- Export OpenAI key (required for Excel→JSON): `export OPENAI_API_KEY=...`.
- Initialize this folder: `./setup_isolated.sh`.
- Run the pipeline: `./run.sh -i path/to/tank_measurements_filled.xlsx [-p polygon.txt]`.

Traditional Run (no run.sh)
- Environment: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium`
- Excel→JSON (supports .xlsx and .csv):
  - `python excel_to_json_langgraph.py \`
  - `  "/path/to/tank_locations_with_measurements.xlsx" \`
  - `  -o output/run1/tank_config.json [--sheet Tanks] [--start-row 2] [--limit 50] [--model gpt-4o-mini]`
- Validate JSON: `python validate_tank_json.py output/run1/tank_config.json`
- HUD run: `python fast_hud_processor.py --config output/run1/tank_config.json`
- Generate PDF: `python generate_pdf.py -o output/run1/HUD_ASD_Results.pdf`
- Update Excel: `python update_excel_with_results.py \`
  - `  "/path/to/tank_locations_with_measurements.xlsx" fast_results.json -o output/run1/with_hud.xlsx`
- Compliance: `python compliance_checker.py output/run1/with_hud.xlsx fast_results.json --polygon polygon.txt -o output/run1/final_compliance.xlsx` (or `--no-distances`)

API Mode (for frontend)
- Start server with uvicorn (no bash scripts):
  - `uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`
- Endpoints (multipart/form-data unless noted):
  - `POST /session/new` → `{ session }` create a session
  - `POST /kmz/parse` (file=KMZ/KML, optional `session`) → runs `kmz_parser_agent.py`, stores polygon + template in session output
  - `POST /excel-to-json` (optional `file=Excel`, optional `session`) → uses uploaded Excel or existing session Excel; validates intrinsically; returns `{ session, json, validated: true }`
  - `POST /validate-json` (file=JSON) → `{ ok, stdout, stderr }`
  - `POST /hud/run` (optional `file=JSON config`, optional `session`) → uses session JSON if not provided; returns `{ job_id, session }` (poll `GET /jobs/{job_id}`)
  - WebSocket: `ws://host:8000/ws/jobs/{job_id}` streams logs and completion status
  - `POST /pdf/generate` (form: `output_name` optional, optional `session`) → `{ ok, pdf }`
  - `POST /excel/update-with-results` (optional `excel`, optional `hud_results`, optional `session`) → uses session artifacts if not provided → `{ ok, excel }`
  - `POST /compliance/check` (optional `excel`, optional `hud_results`, optional `polygon`, optional `session`) → uses session artifacts if not provided → `{ ok, report }`
  - `GET /files` → list saved outputs; `GET /files/{path}` → download
  - `GET /health` → simple health check

Frontend (Vite)
- Location: `pipeline_isolated/frontend`
- Dev: `cd pipeline_isolated/frontend && npm install && npm run dev`
- API base:
  - By default the app uses a dev proxy at `/api` (configured in `vite.config.ts`) to avoid CORS. No env needed.
  - Optionally set `VITE_API_BASE` in `frontend/.env` for direct backend access (e.g., `http://127.0.0.1:8000`).
- The UI tracks a `session` in localStorage to chain steps without re-uploading outputs.

Environment variables
- Set `OPENAI_API_KEY` in your shell environment before running CLI tools or the API server:
  - `export OPENAI_API_KEY=sk-...`
  - The API does not load `.env`; it only reads from the process environment.

What gets copied
- kmz_parser_agent.py (optional for KMZ parse step)
- excel_to_json_langgraph.py
- validate_tank_json.py
- fast_hud_processor.py
- generate_pdf.py
- update_excel_with_results.py
- compliance_checker.py
- calculate_distances.py (vendored from catano_distance_calculator)

Outputs
- `.playwright-mcp/`: screenshots
- `fast_results.json`: HUD results
- `HUD_ASD_Results.pdf`: combined PDF
- `with_hud.xlsx`: Excel updated with ASD values
- `final_compliance.xlsx` or `compliance_no_dist.xlsx`: compliance report

Notes
- `excel_to_json_langgraph.py` accepts `.xlsx` and `.csv`, tolerates varied header names (English/Spanish), and can infer tank capacity from measurements (L×W×H) when gallons are not provided. It also captures the site/client name when present. Options: `--sheet`, `--start-row`, `--limit`, `--model`, `--max-retries`.
- `fast_hud_processor.py` expects `tank_configurations.json`. The runner copies `tank_config.json` accordingly.
- If you skip the polygon, compliance runs with `--no-distances` and only uses HUD values appended to Excel.
