# Driftline SPEC (Approval Health v0.1)

Source of truth for behavior. Builder updates with every behavior change. QA tests against this.

## 1. Purpose
Tell a security lead whether human approval gates on AI agent actions are still real or rubber-stamping.

## 2. Event model
Fields: approver (str 1-200, required), action (str 1-500, required), decision (required), risk, agent?, amount?, event_id? (idempotency), shown_at+decided_at OR seconds, meta?.
- decision accepts approve/approved/accept/accepted -> `approve`; reject/rejected/deny/denied/decline/declined -> `reject` (case-insensitive). Anything else -> 422.
- risk: low|medium|high|critical (case-insensitive) or int 0-3. Default medium. Else 422.
- Timing: either `seconds` (>=0) or both `shown_at` and `decided_at`. Neither -> 422. decided_at < shown_at -> 422.
- Timestamps: epoch number, numeric string, or ISO-8601 (`Z` ok; naive = UTC).
- Idempotency: same (project, event_id) is stored once; repeat returns `duplicate: true`. Events without event_id are never deduped.
- Batch: max 1000 events per request. Over -> 422.

## 3. Auth
`X-Driftline-Key` or `Authorization: Bearer`. Missing/invalid -> 401. Every query is scoped to the key's project. A key must never see another project's data.
API keys are stored as a SHA-256 hash only; the plaintext is shown once, at creation or rotation, and cannot be recovered afterward (rotate instead).

### Project + key management
- CLI (`python manage.py create-project "<name>"` / `python manage.py rotate-key <project_id>`) always works locally.
- Admin HTTP endpoints require `X-Driftline-Admin-Key` to match env var `DRIFTLINE_ADMIN_KEY`; if that env var is unset, the endpoints are disabled (403) rather than open.
  - `POST /v1/admin/projects` {name} -> 201 {id, name, api_key}
  - `POST /v1/admin/projects/{id}/rotate-key` -> 200 {id, name, api_key}; unknown id -> 404
- The demo key (`dl_demo_key`) only exists after running `seed.py`; nothing creates it otherwise.

## 4. Scoring (per approver over window)
score = speed(0-40) + rejects(0-30) + risk_sensitivity(0-30), rounded to 0.1, range [0,100].
- speed = clamp(median_seconds / 30) * 40
- rejects = clamp(reject_rate / 0.05) * 30
- risk_sensitivity = clamp(spearman(risk, seconds) / 0.4) * 30; if correlation undefined (flat or <3 events) = 15 (neutral)
- label: >=70 healthy, >=40 watch, else rubber_stamp. No events -> no_data, score null.

## 5. Flags (all require minimum sample size; below it, never flag)
| code | severity | condition |
|---|---|---|
| fast_median | high | n>=20 and median < 5s |
| zero_rejects | high | n>=50 and rejects == 0 |
| high_risk_fast | high | >=10 events at risk>=2 and their median < 3s |
| risk_blind | medium | n>=30, >=2 risk levels, corr < 0.1 |
| speed_drift | medium | last 7d >=10 events, older >=20 events, recent median < 0.5 * older median |
Thresholds are in CONFIG and exposed at GET /v1/config.

## 6. API (all need key except /healthz, /v1/config)
- POST /v1/approvals -> 201 {ok, duplicate}
- POST /v1/approvals/batch -> 201 {ok, received, created}
- GET /v1/overview?days=1..365 (default 30): org score, per-approver list worst-first (null scores last), flagged_count, trend
- GET /v1/approvers/{name}?days=: detail, histogram (6 buckets), trend, last 25 events. Unknown -> 404
- GET /v1/digest?days=1..90 (default 7): plain text + flagged names
- POST /v1/digest/send?days=1..90 (default 7): same digest as above, plus delivers it over configured channels (ยง11); response adds `delivery: {slack, email}`, each `"sent"` / `"disabled"` / `"error: ..."`. No channels configured -> both `"disabled"`, still 200.
- GET /healthz
- Out-of-range `days` -> 422.

## 7. SDK (python, stdlib only)
- `Client.log_approval(...)` and `Client.present(...).approve()/.reject()` are non-blocking, never raise.
- Every event gets an event_id (uuid) if none given, so retries are idempotent.
- 5xx/network error -> requeue and retry. 4xx -> drop with warning. Queue cap 10,000, overflow drops with warning.
- A Review finalizes once; second approve/reject is ignored.
- `flush()` blocks up to timeout; `close()` flushes at exit.

## 8. Rate limits & body size
- Every request body is capped at 1MB; over -> 413. Checked via `Content-Length` and re-checked against actual bytes received (covers chunked requests).
- POST /v1/approvals and /v1/approvals/batch are rate limited per project: 300 requests / 60s fixed window. Over -> 429 with a `Retry-After` header (seconds). A batch request counts as one request regardless of event count. Counters are in-memory per server process (reset on restart; not shared across processes).

## 9. Not yet specified (open)
Multi-user auth, Postgres, Guardrail Health, Cascade Mapper.

## 10. Config via env vars
- `DRIFTLINE_DB`: path to the SQLite file. Defaults to `driftline.db` at the repo root.
- `DRIFTLINE_CORS_ORIGINS`: comma-separated list of allowed origins for CORS. Unset -> defaults to `http://localhost:5173,http://127.0.0.1:5173` (the Vite dev server), not a wildcard.
- `DRIFTLINE_ADMIN_KEY`: see §3.

## 11. Digest delivery
`POST /v1/digest/send` sends the digest text over Slack and/or email. Each channel is independent and off by default; it only activates once its env vars are set.
- Slack: `DRIFTLINE_SLACK_WEBHOOK_URL` (incoming webhook URL). Unset -> Slack delivery `"disabled"`.
- Email (SMTP): requires both `DRIFTLINE_SMTP_HOST` and `DRIFTLINE_SMTP_TO` (comma-separated recipients); either missing -> email delivery `"disabled"`. Optional: `DRIFTLINE_SMTP_PORT` (default 587), `DRIFTLINE_SMTP_USER`, `DRIFTLINE_SMTP_PASSWORD`, `DRIFTLINE_SMTP_FROM` (defaults to `DRIFTLINE_SMTP_USER`), `DRIFTLINE_SMTP_TLS` (default true; `"false"` disables STARTTLS).
- A send failure on one channel does not block the other; the response reports `"error: ..."` for that channel only.
