# Driftline

Runtime trust layer for AI agents. This repo is the first module: **Approval Health**, which measures whether
your human-in-the-loop approvals are still real or have quietly become rubber-stamping.

## What's here

```
server/    FastAPI + SQLite. Ingest API, scoring engine (scoring.py), read API, serves the UI
sdk/       Python SDK (stdlib only). Non-blocking, batched, idempotent
web/       React dashboard (Vite). Overview, per-approver detail, setup snippets
seed.py    60 days of fake data for a fictional fintech (demo key: dl_demo_key)
tests/     Scoring + API + SDK tests
```

## Run it

```bash
pip install -r requirements.txt
python seed.py --reset                       # demo data
cd web && npm install && npm run build && cd ..
uvicorn server.app:app --port 8000           # open http://localhost:8000, click "Use demo key"
pytest tests -q
```

Dev mode for the UI: `cd web && npm run dev` (proxies /v1 to :8000).

Create a real project key: `python -c "from server import db; db.init(); print(db.create_project('my co'))"`

## How scoring works (server/scoring.py)

Score 0-100 per approver over a window = review speed (40) + reject rate (30) + risk sensitivity (30).

- **Speed**: median decision time vs a 30s "real reading" baseline.
- **Rejects**: reject rate vs a 5% baseline. A gate that never says no isn't a gate.
- **Risk sensitivity**: Spearman correlation of risk level vs decision time. Reviewers should slow down on wires.

70+ healthy, 40-70 watch, under 40 rubber-stamping. Flags: `fast_median`, `zero_rejects`,
`high_risk_fast`, `risk_blind`, `speed_drift`. Thresholds live in `CONFIG` and need tuning against real
customer data. Small samples never flag.

## API

All endpoints take `X-Driftline-Key`.

- `POST /v1/approvals` and `/v1/approvals/batch`: `approver, action, decision, risk (low|medium|high|critical)`,
  and either `shown_at`+`decided_at` or `seconds`. Optional: `agent, amount, event_id (idempotency), meta`
- `GET /v1/overview?days=30`, `/v1/approvers/{name}`, `/v1/digest?days=7`, `/v1/config`

## Not built yet

Auth beyond a static API key, multi-user, Postgres, Slack/email digest delivery, SDKs other than Python,
Guardrail Health, Cascade Mapper.
