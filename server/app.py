import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, Union

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from starlette.datastructures import Headers

from . import db, delivery, guardrail
from .scoring import CONFIG, RISK_LEVELS, RISK_RANK, daily_trend, score_events

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield


app = FastAPI(title="Driftline", version="0.1.0", lifespan=lifespan)

# ---------- request body size cap ----------
# SPEC.md ยง9: every request body is capped at 1MB, checked up-front via
# Content-Length and enforced again as bytes stream in (covers chunked
# requests that omit or lie about Content-Length).
MAX_BODY_BYTES = 1_000_000


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, asgi_app, max_bytes: int):
        self.app = asgi_app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        cl = headers.get("content-length")
        if cl is not None and cl.isdigit() and int(cl) > self.max_bytes:
            await self._reject(send)
            return

        total = 0

        async def guarded_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body") or b"")
                if total > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, guarded_receive, send)
        except _BodyTooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send):
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": b'{"detail":"Request body exceeds 1MB limit"}'})


def _cors_origins() -> list[str]:
    # SPEC.md §10: DRIFTLINE_CORS_ORIGINS is a comma-separated allowlist;
    # unset defaults to localhost only so a fresh deploy isn't wide open.
    raw = os.environ.get("DRIFTLINE_CORS_ORIGINS")
    if raw is None:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins(), allow_methods=["*"], allow_headers=["*"])


# ---------- auth ----------

def project(x_driftline_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    key = x_driftline_key
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization[7:].strip()
    if not key:
        raise HTTPException(401, "Missing API key. Send X-Driftline-Key.")
    p = db.project_for_key(key)
    if not p:
        raise HTTPException(401, "Invalid API key.")
    return p


ADMIN_KEY = os.environ.get("DRIFTLINE_ADMIN_KEY")


def require_admin(x_driftline_admin_key: Optional[str] = Header(None)):
    if not ADMIN_KEY:
        raise HTTPException(403, "Admin endpoints disabled. Set DRIFTLINE_ADMIN_KEY to enable.")
    if not x_driftline_admin_key or x_driftline_admin_key != ADMIN_KEY:
        raise HTTPException(401, "Invalid admin key.")


# ---------- admin: projects + keys ----------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@app.post("/v1/admin/projects", status_code=201)
def admin_create_project(body: ProjectIn, _=Depends(require_admin)):
    return db.create_project(body.name)


@app.post("/v1/admin/projects/{project_id}/rotate-key")
def admin_rotate_key(project_id: int, _=Depends(require_admin)):
    try:
        return db.rotate_key(project_id)
    except KeyError:
        raise HTTPException(404, "Unknown project")


# ---------- rate limiting (ingest only) ----------
# SPEC.md ยง9: fixed-window counter per project. In-memory, so it resets on
# restart and doesn't span multiple processes -- fine for the single-process
# v0 deployment this ships for.
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 300

_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict[int, tuple[float, int]] = {}


def rate_limit_ingest(p=Depends(project)):
    pid = p["id"]
    now = time.time()
    with _rate_limit_lock:
        window_start, count = _rate_limit_buckets.get(pid, (now, 0))
        if now - window_start >= RATE_LIMIT_WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1
        _rate_limit_buckets[pid] = (window_start, count)
        if count > RATE_LIMIT_MAX_REQUESTS:
            retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - window_start)))
            raise HTTPException(429, "Rate limit exceeded. Try again later.",
                                 headers={"Retry-After": str(retry_after)})
    return p


# ---------- ingest ----------

def _to_epoch(v: Union[float, int, str]) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    s = v.strip()
    try:
        return float(s)
    except ValueError:
        pass
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class ApprovalIn(BaseModel):
    approver: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=500, description="What was being approved, e.g. 'wire_transfer'")
    decision: str
    risk: Union[int, str] = "medium"
    agent: Optional[str] = None
    amount: Optional[float] = None
    event_id: Optional[str] = Field(None, max_length=200, description="Idempotency key")
    shown_at: Optional[Union[float, int, str]] = None
    decided_at: Optional[Union[float, int, str]] = None
    seconds: Optional[float] = Field(None, ge=0, description="Decision time if you don't have timestamps")
    meta: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _check(self):
        d = self.decision.lower()
        if d in ("approved", "approve", "accept", "accepted"):
            self.decision = "approve"
        elif d in ("rejected", "reject", "deny", "denied", "decline", "declined"):
            self.decision = "reject"
        else:
            raise ValueError("decision must be approve or reject")
        if isinstance(self.risk, str):
            r = self.risk.lower()
            if r not in RISK_RANK:
                raise ValueError(f"risk must be one of {RISK_LEVELS}")
            self.risk = RISK_RANK[r]
        elif not 0 <= self.risk <= 3:
            raise ValueError("numeric risk must be 0-3")
        if self.seconds is None and (self.shown_at is None or self.decided_at is None):
            raise ValueError("send either seconds, or both shown_at and decided_at")
        return self


class BatchIn(BaseModel):
    events: list[ApprovalIn] = Field(max_length=1000)


def _insert(c, pid: int, e: ApprovalIn) -> bool:
    if e.shown_at is not None and e.decided_at is not None:
        shown, decided = _to_epoch(e.shown_at), _to_epoch(e.decided_at)
        seconds = decided - shown
        if seconds < 0:
            raise HTTPException(422, "decided_at is before shown_at")
    else:
        seconds = float(e.seconds)
        decided = _to_epoch(e.decided_at) if e.decided_at is not None else time.time()
        shown = decided - seconds
    cur = c.execute(
        """INSERT OR IGNORE INTO approvals
           (project_id,event_id,approver,agent,action,risk,amount,decision,shown_at,decided_at,seconds,meta)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, e.event_id, e.approver, e.agent, e.action, e.risk, e.amount, e.decision,
         shown, decided, seconds, json.dumps(e.meta) if e.meta else None),
    )
    return cur.rowcount == 1


@app.post("/v1/approvals", status_code=201)
def ingest(e: ApprovalIn, p=Depends(rate_limit_ingest)):
    with db.conn() as c:
        created = _insert(c, p["id"], e)
    return {"ok": True, "duplicate": not created}


@app.post("/v1/approvals/batch", status_code=201)
def ingest_batch(b: BatchIn, p=Depends(rate_limit_ingest)):
    created = 0
    with db.conn() as c:
        for e in b.events:
            created += _insert(c, p["id"], e)
    return {"ok": True, "received": len(b.events), "created": created}


# ---------- read ----------

def _load(pid: int, days: int, approver: Optional[str] = None) -> list[dict]:
    since = time.time() - days * 86400
    q = "SELECT approver,agent,action,risk,amount,decision,seconds,decided_at AS ts FROM approvals WHERE project_id=? AND decided_at>=?"
    args: list[Any] = [pid, since]
    if approver:
        q += " AND approver=?"
        args.append(approver)
    q += " ORDER BY decided_at"
    with db.conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def _by_approver(events: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in events:
        out.setdefault(e["approver"], []).append(e)
    return out


@app.get("/v1/config")
def config():
    return {"thresholds": CONFIG, "risk_levels": RISK_LEVELS}


@app.get("/v1/overview")
def overview(days: int = Query(30, ge=1, le=365), p=Depends(project)):
    now = time.time()
    events = _load(p["id"], max(days, 30) + 7)
    window = [e for e in events if e["ts"] >= now - days * 86400]
    org = score_events(window, now)
    approvers = []
    for name, evs in _by_approver(window).items():
        s = score_events(evs, now)
        approvers.append({"approver": name, **{k: s[k] for k in
                          ("n", "score", "label", "median_seconds", "reject_rate", "risk_sensitivity", "flags")}})
    approvers.sort(key=lambda a: (a["score"] is None, a["score"]))
    flagged = [a for a in approvers if a["flags"]]
    return {
        "days": days,
        "org": {k: org.get(k) for k in ("n", "score", "label", "median_seconds", "reject_rate",
                                         "risk_sensitivity", "median_by_risk", "components")},
        "approvers": approvers,
        "flagged_count": len(flagged),
        "trend": daily_trend(events, now, days=min(days, 60)),
    }


@app.get("/v1/approvers/{name}")
def approver_detail(name: str, days: int = Query(30, ge=1, le=365), p=Depends(project)):
    now = time.time()
    events = _load(p["id"], max(days, 30) + 7, name)
    if not events:
        raise HTTPException(404, "No events for that approver")
    window = [e for e in events if e["ts"] >= now - days * 86400]
    s = score_events(window, now)
    # time histogram by bucket
    buckets = [("<2s", 0, 2), ("2-5s", 2, 5), ("5-15s", 5, 15), ("15-60s", 15, 60), ("1-5m", 60, 300), (">5m", 300, 1e12)]
    hist = [{"bucket": b, "count": sum(1 for e in window if lo <= e["seconds"] < hi)} for b, lo, hi in buckets]
    return {"approver": name, "days": days, **s, "histogram": hist,
            "trend": daily_trend(events, now, days=min(days, 60)),
            "recent": [dict(e, risk_name=RISK_LEVELS[e["risk"]]) for e in window[-25:]][::-1]}


@app.get("/v1/digest")
def digest(days: int = Query(7, ge=1, le=90), p=Depends(project)):
    """Plain-text weekly digest for the security/compliance lead."""
    now = time.time()
    events = _load(p["id"], days + 7)
    window = [e for e in events if e["ts"] >= now - days * 86400]
    org = score_events(window, now)
    lines = [f"Driftline approval digest: last {days} days", ""]
    if org["n"] == 0:
        lines.append("No approvals logged.")
        return {"text": "\n".join(lines), "flagged": []}
    lines.append(f"{org['n']} approvals, org trust score {org['score']:.0f}/100 ({org['label'].replace('_', ' ')}), "
                 f"median decision {org['median_seconds']}s, {org['reject_rate']*100:.1f}% rejected.")
    lines.append("")
    flagged = []
    for name, evs in _by_approver(window).items():
        s = score_events(evs, now)
        if s["flags"]:
            flagged.append((name, s))
    flagged.sort(key=lambda t: t[1]["score"])
    if not flagged:
        lines.append("Nobody flagged this period.")
    else:
        lines.append(f"{len(flagged)} approver(s) need a look:")
        for name, s in flagged:
            lines.append(f"- {name}: score {s['score']:.0f}, {s['n']} actions, median {s['median_seconds']}s, "
                         f"{s['rejects']} rejected")
            for f in s["flags"]:
                lines.append(f"    * {f['title']}: {f['detail']}")
        lines.append("")
        lines.append("Question for the control owner: is this gate still a real control?")
    return {"text": "\n".join(lines), "flagged": [n for n, _ in flagged]}


@app.post("/v1/digest/send")
def digest_send(days: int = Query(7, ge=1, le=90), p=Depends(project)):
    """Send the digest (see GET /v1/digest) over configured channels (Slack webhook / SMTP email).

    Both channels are off by default: with no channel configured, this is a no-op that
    still returns 200 with each channel marked "disabled" (SPEC.md ยง11).
    """
    result = digest(days=days, p=p)
    status = delivery.deliver_digest(f"Driftline approval digest ({days}d)", result["text"])
    return {**result, "delivery": status}


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------- guardrail health v0 ----------

class GuardrailRunIn(BaseModel):
    adapter_url: str = Field(min_length=1, max_length=2000,
                              description="HTTP(S) endpoint accepting POST {prompt} -> {response}")

    @model_validator(mode="after")
    def _check(self):
        if not (self.adapter_url.startswith("http://") or self.adapter_url.startswith("https://")):
            raise ValueError("adapter_url must be http:// or https://")
        return self


@app.post("/v1/guardrail/run", status_code=201)
def guardrail_run_create(body: GuardrailRunIn, p=Depends(project)):
    """Run every probe once against the given adapter, store the run, and diff
    it against the project's previous run (regressions only; SPEC.md ยง12)."""
    probes = guardrail.load_probes()
    results = guardrail.run_probes(probes, lambda prompt: guardrail.call_adapter(body.adapter_url, prompt))
    source = probes[0].source if probes else "builtin"
    baseline = db.latest_guardrail_run(p["id"])
    saved = db.save_guardrail_run(p["id"], source, results)
    regressions = guardrail.diff_regressions(baseline["results"] if baseline else None, results)
    return {**saved, "regressions": regressions}


@app.get("/v1/guardrail/runs")
def guardrail_runs_index(limit: int = Query(20, ge=1, le=200), p=Depends(project)):
    return {"runs": db.guardrail_runs_list(p["id"], limit)}


@app.get("/v1/guardrail/runs/{run_id}")
def guardrail_run_detail(run_id: int, p=Depends(project)):
    run = db.guardrail_run(run_id, p["id"])
    if not run:
        raise HTTPException(404, "Unknown guardrail run")
    baseline = db.previous_guardrail_run(p["id"], run_id)
    regressions = guardrail.diff_regressions(baseline["results"] if baseline else None, run["results"])
    return {**run, "regressions": regressions}


# ---------- static UI ----------
_dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = os.path.join(_dist, path)
        if path and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(os.path.join(_dist, "index.html"))
