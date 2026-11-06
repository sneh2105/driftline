# AGENTS.md (QA / Codex)

You test Driftline. You do not build it.

## Rules
- Work ONLY on branch `qa/first-pass` in this worktree. Never commit to `main`. Never push (the run script pushes).
- You may ONLY create/edit files under `tests/qa/`. Never edit `server/`, `sdk/`, `web/`, `seed.py`, `SPEC.md`, `TASKS.md`, `CLAUDE.md`, or `logs/`.
- Test against `SPEC.md` and the public HTTP API / SDK surface. Do NOT read `server/` internals to decide what correct means. If SPEC.md is ambiguous, log a SPEC-GAP instead of guessing.
- Bug found? Commit a test marked `@pytest.mark.xfail(strict=True, reason="BUG-<n>: <one line>")`. CI stays green; when the builder fixes it the strict xfail goes XPASS=fail and you remove the marker next round.
- Use the real app via FastAPI TestClient with a temp DB. Write your own fixture in tests/qa/conftest.py.
- One focus area per run, one commit per run.

## Focus areas (work through in order, tick them in tests/qa/QA_PLAN.md)
1. Ingest validation: negative/zero/huge seconds, decided_at < shown_at, bad risk, unicode/very long strings, batch of 1000 and 1001, duplicate event_id (single + within one batch), mixed epoch/ISO/naive timestamps.
2. Scoring properties (hypothesis): slower median never lowers speed component; adding a reject never lowers reject component; score always in [0,100]; small samples never flag; empty input safe.
3. Auth: missing/invalid key, tenant isolation (one project's key can never read another's data).
4. SDK: server down, 5xx retry without duplicates, queue full, double approve/reject, never raises.
5. API read paths: days bounds, unknown approver 404, approver names with special chars.
6. Guardrail Health (when it exists): diff alerts ONLY on blocked->bypassed regressions.

## LOGGING (mandatory)
Append an entry to `tests/qa/QA_LOG.md` for every commit:

```
## <YYYY-MM-DD HH:MM> · qa/first-pass · <short sha or pending>
**Focus:** which area
**Tests added:** names/count and what each protects
**Findings:** BUG-n (repro, expected per SPEC section, actual) / SPEC-GAP / "none"
**Why these tests:** what risk they cover
**Verified:** exact command + result (passed / xfailed counts)
```
Append only. Never rewrite old entries. If blocked, add `### Blocked` with the reason.
