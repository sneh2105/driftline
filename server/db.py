import hashlib
import os
import sqlite3
import secrets
import time
from contextlib import contextmanager

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
