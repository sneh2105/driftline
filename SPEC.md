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
- GET /healthz
- Out-of-range `days` -> 422.

## 7. SDK (python, stdlib only)
- `Client.log_approval(...)` and `Client.present(...).approve()/.reject()` are non-blocking, never raise.
- Every event gets an event_id (uuid) if none given, so retries are idempotent.
- 5xx/network error -> requeue and retry. 4xx -> drop with warning. Queue cap 10,000, overflow drops with warning.
- A Review finalizes once; second approve/reject is ignored.
- `flush()` blocks up to timeout; `close()` flushes at exit.

## 8. Not yet specified (open)
Multi-user auth, Postgres, digest delivery, Guardrail Health, Cascade Mapper.
