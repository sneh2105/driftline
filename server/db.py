import hashlib
import os
import sqlite3
import secrets
import time
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get("DRIFTLINE_DB", os.path.join(os.path.dirname(__file__), "..", "driftline.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key_hash TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    event_id TEXT,                      -- optional caller-supplied id for idempotency
    approver TEXT NOT NULL,
    agent TEXT,
    action TEXT NOT NULL,
    risk INTEGER NOT NULL,              -- 0 low .. 3 critical
    amount REAL,
    decision TEXT NOT NULL,             -- approve | reject
    shown_at REAL NOT NULL,
    decided_at REAL NOT NULL,
    seconds REAL NOT NULL,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_appr_proj_ts ON approvals(project_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_appr_proj_approver ON approvals(project_id, approver);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appr_event ON approvals(project_id, event_id) WHERE event_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS guardrail_runs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    created_at REAL NOT NULL,
    probe_source TEXT NOT NULL,
    n INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    errored INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS guardrail_results (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES guardrail_runs(id),
    probe_id TEXT NOT NULL,
    category TEXT NOT NULL,
    passed INTEGER,            -- NULL = adapter error, 1 = refused, 0 = complied
    response_snippet TEXT
);
CREATE INDEX IF NOT EXISTS idx_grun_proj ON guardrail_runs(project_id, id);
CREATE INDEX IF NOT EXISTS idx_gresult_run ON guardrail_results(run_id);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_project(name: str, api_key: str | None = None) -> dict:
    key = api_key or "dl_" + secrets.token_urlsafe(24)
    with conn() as c:
        cur = c.execute(
            "INSERT INTO projects(name, api_key_hash, created_at) VALUES (?,?,?)",
            (name, _hash_key(key), time.time()),
        )
        return {"id": cur.lastrowid, "name": name, "api_key": key}


def rotate_key(project_id: int) -> dict:
    """Issue a new API key for a project, invalidating the old one. Returns the plaintext key once."""
    key = "dl_" + secrets.token_urlsafe(24)
    with conn() as c:
        row = c.execute("SELECT name FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(f"no project with id {project_id}")
        c.execute("UPDATE projects SET api_key_hash=? WHERE id=?", (_hash_key(key), project_id))
        return {"id": project_id, "name": row["name"], "api_key": key}


def project_for_key(key: str):
    with conn() as c:
        return c.execute("SELECT * FROM projects WHERE api_key_hash=?", (_hash_key(key),)).fetchone()


def _hydrate_guardrail_run(row) -> dict:
    with conn() as c:
        rows = c.execute(
            "SELECT probe_id, category, passed, response_snippet FROM guardrail_results WHERE run_id=?",
            (row["id"],),
        ).fetchall()
    results = [
        {
            "probe_id": r["probe_id"],
            "category": r["category"],
            "passed": None if r["passed"] is None else bool(r["passed"]),
            "response_snippet": r["response_snippet"],
        }
        for r in rows
    ]
    return {**dict(row), "results": results}


def save_guardrail_run(project_id: int, probe_source: str, results: list[dict]) -> dict:
    """Store a completed probe run and its per-probe results."""
    n = len(results)
    passed = sum(1 for r in results if r["passed"] is True)
    failed = sum(1 for r in results if r["passed"] is False)
    errored = n - passed - failed
    with conn() as c:
        cur = c.execute(
            "INSERT INTO guardrail_runs(project_id, created_at, probe_source, n, passed, failed, errored) "
            "VALUES (?,?,?,?,?,?,?)",
            (project_id, time.time(), probe_source, n, passed, failed, errored),
        )
        run_id = cur.lastrowid
        for r in results:
            c.execute(
                "INSERT INTO guardrail_results(run_id, probe_id, category, passed, response_snippet) "
                "VALUES (?,?,?,?,?)",
                (run_id, r["probe_id"], r["category"],
                 None if r["passed"] is None else int(r["passed"]), r["response_snippet"]),
            )
        row = c.execute("SELECT * FROM guardrail_runs WHERE id=?", (run_id,)).fetchone()
    return _hydrate_guardrail_run(row)


def latest_guardrail_run(project_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(
            "SELECT * FROM guardrail_runs WHERE project_id=? ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return _hydrate_guardrail_run(row) if row else None


def guardrail_run(run_id: int, project_id: int) -> Optional[dict]:
    """Scoped to project_id -- a key must never see another project's runs."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM guardrail_runs WHERE id=? AND project_id=?",
            (run_id, project_id),
        ).fetchone()
    return _hydrate_guardrail_run(row) if row else None


def previous_guardrail_run(project_id: int, before_run_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(
            "SELECT * FROM guardrail_runs WHERE project_id=? AND id<? ORDER BY id DESC LIMIT 1",
            (project_id, before_run_id),
        ).fetchone()
    return _hydrate_guardrail_run(row) if row else None


def guardrail_runs_list(project_id: int, limit: int = 20) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, created_at, probe_source, n, passed, failed, errored FROM guardrail_runs "
            "WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
