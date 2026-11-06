# Builder backlog (builder ticks these; humans can reorder/add)

- [x] Project + API key management: CLI and endpoint to create projects and rotate keys; store keys hashed, never plaintext; demo key only exists when seeded
- [x] Reconcile SPEC.md with actual behavior; fix code or spec for every mismatch and log which
- [x] Rate limit ingest endpoints and cap request body at 1MB; document in SPEC.md
- [x] Config via env vars (DB path, CORS origins); default CORS to localhost only
- [x] Digest delivery: Slack webhook + email (SMTP) sender, off by default
- [x] Guardrail Health v0: probe library loader (JailbreakBench via pip package, optional), probe runner with pluggable adapter, regression-only diff, endpoints, SPEC section

- [ ] SECURITY: SSRF protection on /v1/guardrail/run adapter_url. Resolve the hostname, reject loopback, private (RFC1918), link-local (169.254.0.0/16 incl. cloud metadata), and IPv6 equivalents; do not follow redirects to such targets. Env DRIFTLINE_ALLOW_PRIVATE_ADAPTERS=true re-enables them for local dev. Update SPEC.md section 12 and add tests.
- [ ] Define in SPEC.md section 12 the exact shape of run results and regression entries (field names, ids), then make the code match.
- [ ] Define an upper bound for seconds (e.g. reject values over 7 days with 422) and a sane float/overflow guard; document in SPEC.md section 2.
- [ ] Triage every SPEC-GAP entry in tests/qa/QA_LOG.md: decide the behavior, write it into SPEC.md, and note the decision in BUILD_LOG.md.
