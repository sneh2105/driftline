# QA plan (Codex ticks these)
- [x] 1 Ingest validation
- [x] 2 Scoring properties
- [x] 3 Auth + tenant isolation
- [x] 4 SDK failure modes
- [x] 5 API read paths
- [x] 6 Guardrail Health diff

## Round 2 rules (read before starting)
- Use ASCII only in QA_LOG.md and test files. No smart quotes, dashes or emoji in logs.
- Public surface only: HTTP API and the SDK's public methods against a real local fake server. Never touch private attributes like _q or _send.
- If SPEC.md does not define a response shape or limit, log a SPEC-GAP. Never loosen an assertion to make a test pass.
- Boundary tests use exact boundaries (N and N+1).
- A security expectation that fails is a BUG-n strict xfail, labeled SECURITY in the reason.

- [x] 7 Rate limit + body cap (SPEC 8): 300 req/60s per project, 429 + Retry-After, batch counts as one, project B unaffected by project A flooding, 413 over 1MB (Content-Length and chunked), exactly 1MB accepted
- [ ] 8 Admin + key lifecycle (SPEC 3): admin endpoints 403 when env unset, 401 wrong admin key, rotated key invalidates the old one, plaintext key never returned after creation
- [ ] 9 Digest delivery (SPEC 11): /v1/digest/send with nothing configured gives 200 and both disabled; Slack via a local fake webhook server; one channel failing does not block the other; SMTP needs both HOST and TO
- [ ] 10 Guardrail depth (SPEC 12): another project's run id gives 404; limit bounds 1..200; non-http adapter_url gives 422; adapter timeout or bad JSON gives passed null; SECURITY: adapter_url http://169.254.169.254/ and other link-local or private targets must be rejected (strict xfail if accepted)
- [ ] 11 Tenant isolation on EVERY read endpoint: approvers/{name}, digest, guardrail runs, with two projects holding different data
- [ ] 12 Flag thresholds (SPEC 5): each flag fires at its threshold and not one below (e.g. fast_median n=19 vs 20, zero_rejects n=49 vs 50)
- [ ] 13 CORS (SPEC 10): default origins are localhost only, never a wildcard; a foreign Origin gets no Access-Control-Allow-Origin
- [ ] 14 Redo boundaries: approver exactly 200 / 201 chars, action exactly 500 / 501; SDK tests rewritten against a real fake server using public methods only
