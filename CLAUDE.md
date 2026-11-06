# CLAUDE.md (builder)

You build Driftline. Codex agents test it independently. Keep that separation clean.

## Rules
- Work ONLY on branch `feat/auto-build`. Never commit to `main`. Never push (the run script pushes).
- `SPEC.md` is the source of truth. If you change behavior, change SPEC.md in the same commit.
- NEVER edit anything under `tests/qa/` (QA's territory). You may merge it in via git.
- You own `tests/test_driftline.py` and any `tests/unit/`. Every change ships with tests.
- Before committing: `pytest tests -q` (qa strict-xfail XPASS failures are OK to ignore: QA removes the marker next round, say so in the log) and `cd web && npm run build` if web/ changed.
- Keep the SDK stdlib-only. It must never block or raise inside a customer's approval flow.
- Do not touch anything unrelated to the current unit of work. No drive-by refactors.
- One unit of work per run, one commit per unit.

## Priority each run
1. QA findings: any `xfail` test in tests/qa marked `BUG-n`, or any failing non-qa test.
2. First unchecked item in TASKS.md.

## LOGGING (mandatory)
Append an entry to `logs/BUILD_LOG.md` for every commit, in this exact format:

```
## <YYYY-MM-DD HH:MM> · feat/auto-build · <short sha or pending>
**Change:** what you changed, plain language
**Why:** the reason (SPEC section / BUG-n / TASKS item) and why this approach over alternatives
**Files:** list
**Verified:** exact test commands + results
**Notes/risk:** anything a human should double check, or "none"
```
If you are blocked or skip something, add it under a `### Blocked` line in the same file with the reason. Never rewrite old entries; append only.

## Layout
server/ (FastAPI + SQLite; scoring.py is pure), sdk/ (python), web/ (React+Vite), tests/, seed.py, logs/

## Run
pip install -r requirements.txt && python seed.py --reset && uvicorn server.app:app --port 8000
