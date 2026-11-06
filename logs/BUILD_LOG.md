# Build log (append only, builder-owned)

## 2026-11-06 14:00 · feat/auto-build · pending
**Change:** Ticked off the first TASKS.md item ("Project + API key management") — no code changes. Verified the feature is already fully built: `manage.py` CLI (`create-project`, `rotate-key`), admin HTTP endpoints `POST /v1/admin/projects` and `POST /v1/admin/projects/{id}/rotate-key` gated by `X-Driftline-Admin-Key`/`DRIFTLINE_ADMIN_KEY` (server/app.py:43-69), SHA-256-hashed key storage with no plaintext column (server/db.py:14,56-78), and the demo key (`dl_demo_key`) only created by `seed.py`, never on server startup (server/app.py lifespan only calls `db.init()`).
**Why:** No QA xfail/BUG-n findings and no other failing tests this run, so per CLAUDE.md priority 2 I took the first unchecked TASKS.md item. On inspection it was already fully implemented and covered by tests (tests/test_driftline.py:142-193: rotate invalidates old key, unknown project 404s, admin endpoints 403 without DRIFTLINE_ADMIN_KEY, 401 on wrong admin key, full create/rotate/404 flow through the HTTP API). Writing new code or tests for an already-shipped feature would be a drive-by change with no behavior difference, so the correct unit of work was reconciling the backlog checkbox with reality rather than re-implementing.
**Files:** TASKS.md
**Verified:** `pytest tests -q` -> 16 passed. No web/ changes, so `npm run build` was not required.
**Notes/risk:** None. SPEC.md section 3 already documents this behavior accurately, so no SPEC change was needed.
