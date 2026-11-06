# Builder backlog (builder ticks these; humans can reorder/add)

- [x] Project + API key management: CLI and endpoint to create projects and rotate keys; store keys hashed, never plaintext; demo key only exists when seeded
- [x] Reconcile SPEC.md with actual behavior; fix code or spec for every mismatch and log which
- [x] Rate limit ingest endpoints and cap request body at 1MB; document in SPEC.md
- [x] Config via env vars (DB path, CORS origins); default CORS to localhost only
- [x] Digest delivery: Slack webhook + email (SMTP) sender, off by default
- [ ] Guardrail Health v0: probe library loader (JailbreakBench via pip package, optional), probe runner with pluggable adapter, regression-only diff, endpoints, SPEC section
