# CLAUDE.md (builder)

You build Driftline. Codex agents test it independently. Keep that separation clean.

## Rules
- Work on `feat/<name>` branches. Never commit to `main`. Open a PR when done.
- `SPEC.md` is the source of truth. If you change behavior, change SPEC.md in the same PR.
- NEVER edit anything under `tests/qa/`. That's Codex's territory.
- You own `tests/unit/` style tests (currently `tests/test_driftline.py`). Add tests for everything you build.
- Run before every PR: `pytest tests -q` and `cd web && npm run build`.
- When a QA finding exists (GitHub issue labeled `qa-finding`, or an xfail test in `tests/qa/` with `BUG-n`), fix it, then tell me. The xfail flips to XPASS and strict mode forces Codex to remove the marker.
- Keep SDK stdlib-only. It must never block or raise inside a customer's approval flow.
- Small PRs. One concern each.

## Layout
server/ (FastAPI + SQLite, scoring.py is pure functions), sdk/ (python), web/ (React+Vite), tests/, seed.py

## Run
pip install -r requirements.txt && python seed.py --reset && uvicorn server.app:app --port 8000
