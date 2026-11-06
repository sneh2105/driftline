# AGENTS.md (QA / Codex)

You test Driftline. You do not build it.

## Rules
- Work on `qa/<topic>` branches. Open PRs against `main`.
- You may ONLY write under `tests/qa/`. Never edit `server/`, `sdk/`, `web/`, `seed.py`, or `SPEC.md`.
- Test against `SPEC.md` and the public HTTP API / SDK surface. Do NOT read `server/` internals to decide what "correct" is. If SPEC.md is ambiguous, open an issue labeled `spec-gap` instead of guessing.
- Found a bug? Commit a failing test marked:
  `@pytest.mark.xfail(strict=True, reason="BUG-<n>: <one line>")`
  and open a GitHub issue labeled `qa-finding` with repro + expected (cite SPEC.md section). CI stays green; when the builder fixes it, strict xfail goes XPASS=fail and you remove the marker.
- Use the real app via FastAPI TestClient with a temp DB (see fixture in tests/test_driftline.py for the pattern, but write your own in tests/qa/conftest.py).

## Focus areas
1. Ingest validation: negative/zero/huge seconds, decided_at < shown_at, bad risk, unicode/very long strings, batch of 1000 and 1001, duplicate event_id (single + within one batch), mixed epoch/ISO timestamps, naive vs Z timestamps.
2. Scoring properties (hypothesis): slower median never lowers speed component; adding a reject never lowers reject component; score always in [0,100]; small samples never flag; empty input safe.
3. Auth: missing/invalid key, key from another project can't read this project's data (tenant isolation).
4. SDK: server down, 5xx retry without dup (idempotent event_id), queue full, double approve/reject, flush at exit, never raises.
5. API read paths: days bounds, unknown approver 404, approver names with special chars (+, /, @, spaces).
6. Guardrail Health (when it lands): diff alerts ONLY on blocked->bypassed regressions.
