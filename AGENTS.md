# Repository Guidelines

## Project Structure & Module Organization
- `api/`: FastAPI app (`api/main.py`) exposing pipeline endpoints; writes to `work/` and `output/`.
- `frontend/`: Vite UI for the API.
- Root Python tools: `excel_to_json_langgraph.py`, `fast_hud_processor.py`, `generate_pdf.py`, `update_excel_with_results.py`, `compliance_checker.py`, `kmz_parser_agent.py`, `calculate_distances.py`.
- Runtime folders (git-ignored): `.playwright-mcp/` (screenshots), `work/` (tmp), `output/` (artifacts).
- Other: `.env.example`, `requirements.txt`, helper scripts `run.sh`, `setup_isolated.sh`, `run_kmz_end_to_end.sh`.

## Build, Test, and Development Commands
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium`.
- Configure key: export `OPENAI_API_KEY` in your shell environment (do not commit secrets).
- End‑to‑end run: `./run.sh -i path/to/tank_measurements_filled.xlsx [-p polygon.txt]` → writes results to `output/`.
- API server: `uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload` then hit `GET /health` (see README for endpoints).
- KMZ quick path: `./run_kmz_end_to_end.sh -k file.kmz [-n 8] [--no-mocks] [-p polygon.txt]`.
- Frontend dev: `cd frontend && npm install && npm run dev` (configure API base in `.env`).

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indent, PEP 8; prefer type hints where practical.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- CLI scripts should be idempotent and write only under `work/` and `output/`.
- No enforced formatter/linter; keep consistent style. If proposing tooling, prefer `black` + `ruff` and add as dev‑only.

## Testing Guidelines
- Smoke test: `python test_different_kml.py` (exercises KMZ/KML parsing across variants).
- For new code, add small self‑contained tests (e.g., `test_*.py`) runnable without network; mock LLM/browser calls when possible.
- If introducing `pytest`, pin it and keep it in dev requirements; keep tests fast and deterministic.

## Commit & Pull Request Guidelines
- Commits: imperative mood, focused scope (e.g., `Add HUD PDF summary generation`).
- PRs must include: summary and rationale, linked issue, reproduction steps/command (e.g., `./run.sh -i …`), sample inputs if applicable, and a brief note of produced files in `output/`.
- Update README/API docs when changing endpoints or file formats. Never commit secrets; use `.env.example` for new vars.

## Security & Configuration Tips
- Store `OPENAI_API_KEY` in your environment (no dotenv in API). `.env` files are ignored by git, but the server does not read them.
- Avoid committing large data; `work/` and `output/` are ignored by default.
- Playwright is required; run `playwright install chromium` after installing requirements.
