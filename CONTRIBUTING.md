# Contributing

Thanks for helping improve this pipeline. Please read both `README.md` (usage) and `AGENTS.md` (contributor guidelines) before making changes.

## Getting Set Up
- Create venv and install deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium`.
- Configure secrets: export `OPENAI_API_KEY` in your shell environment (do not commit secrets).

## Common Workflows
- End-to-end run: `./run.sh -i path/to/tank_measurements_filled.xlsx [-p polygon.txt]`.
- API dev: run `uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`, then use endpoints (see README) and `GET /health`.
- Frontend dev: `cd frontend && npm install && npm run dev` (set API base in `.env`).

## Style, Tests, and Quality
- Follow conventions in `AGENTS.md` (PEP 8, naming, idempotent scripts writing only to `work/` and `output/`).
- Smoke test KMZ parser: `python test_different_kml.py`.
- Prefer small, deterministic tests; avoid network where possible. If adding pytest, keep it dev-only.

## Branches, Commits, and PRs
- Branch naming: `feature/<short-topic>` or `fix/<short-topic>`.
- Commits: imperative, focused (e.g., `Add HUD PDF summary generation`).
- PRs must include: summary, linked issue, repro commands, sample inputs (if applicable), and note of produced files in `output/`. Update README/API docs when changing endpoints or formats.

For questions, open an issue or a draft PR.
