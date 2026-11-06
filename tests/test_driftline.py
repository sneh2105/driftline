import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from server.scoring import score_events, risk_sensitivity  # noqa: E402

NOW = time.time()


def ev(approver="a", risk=1, seconds=20.0, decision="approve", days_ago=1.0):
    return {"approver": approver, "risk": risk, "seconds": seconds, "decision": decision,
            "ts": NOW - days_ago * 86400}


def test_healthy_reviewer_scores_high():
    events = []
    for i in range(60):
        r = i % 4
        events.append(ev(risk=r, seconds=[10, 20, 40, 80][r], decision="reject" if i % 12 == 0 else "approve",
                         days_ago=i % 20))
    s = score_events(events, NOW)
    assert s["label"] == "healthy"
    assert s["score"] >= 70
    assert s["flags"] == []


def test_rubber_stamp_flags():
    events = [ev(risk=i % 4, seconds=1.5 + (i % 3) * 0.2, days_ago=i % 20) for i in range(80)]
    s = score_events(events, NOW)
    assert s["label"] == "rubber_stamp"
    codes = {f["code"] for f in s["flags"]}
    assert {"fast_median", "zero_rejects", "high_risk_fast"} <= codes


def test_risk_blind_flag():
    # moderate speed, plenty of rejects, but time unrelated to risk
    events = [ev(risk=i % 4, seconds=15 + (i * 7 % 5), decision="reject" if i % 10 == 0 else "approve",
                 days_ago=i % 20) for i in range(60)]
    s = score_events(events, NOW)
    assert "risk_blind" in {f["code"] for f in s["flags"]}


def test_speed_drift_flag():
    old = [ev(seconds=30, risk=1, days_ago=10 + (i % 15), decision="reject" if i % 10 == 0 else "approve") for i in range(40)]
    new = [ev(seconds=8, risk=1, days_ago=i % 6, decision="reject" if i % 10 == 0 else "approve") for i in range(20)]
    s = score_events(old + new, NOW)
    assert "speed_drift" in {f["code"] for f in s["flags"]}


def test_small_samples_dont_flag():
    s = score_events([ev(seconds=1, risk=3) for _ in range(5)], NOW)
    assert s["flags"] == []


def test_sensitivity_sign():
    good = [ev(risk=r, seconds=10 * (r + 1)) for r in (0, 1, 2, 3) for _ in range(5)]
    assert risk_sensitivity(good) > 0.8
    flat = [ev(risk=r, seconds=10) for r in (0, 1, 2, 3) for _ in range(5)]
    assert risk_sensitivity(flat) is None


# ---- API ----
@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFTLINE_DB", str(tmp_path / "t.db"))
    import importlib
    from server import db
    importlib.reload(db)
    from server import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    db.init()
    p = db.create_project("t", "dl_test")
    with TestClient(appmod.app) as c:
        c.headers.update({"X-Driftline-Key": "dl_test"})
        yield c


def test_auth_required(client):
    r = client.post("/v1/approvals", json={}, headers={"X-Driftline-Key": "nope"})
    assert r.status_code == 401


def test_ingest_and_idempotency(client):
    body = {"approver": "m", "action": "wire", "risk": "critical", "decision": "Approved",
            "shown_at": "2026-10-01T10:00:00Z", "decided_at": "2026-10-01T10:00:03Z", "event_id": "e1"}
    r = client.post("/v1/approvals", json=body)
    assert r.status_code == 201 and r.json()["duplicate"] is False
    r = client.post("/v1/approvals", json=body)
    assert r.json()["duplicate"] is True


def test_validation(client):
    r = client.post("/v1/approvals", json={"approver": "m", "action": "x", "decision": "maybe", "seconds": 3})
    assert r.status_code == 422
    r = client.post("/v1/approvals", json={"approver": "m", "action": "x", "decision": "approve"})
    assert r.status_code == 422
    r = client.post("/v1/approvals", json={"approver": "m", "action": "x", "decision": "approve",
                                            "shown_at": 100, "decided_at": 90})
    assert r.status_code == 422


def test_overview_flags_rubber_stamper(client):
    now = time.time()
    events = []
    for i in range(60):
        events.append({"approver": "fast", "action": "wire", "risk": i % 4, "decision": "approve",
                       "seconds": 1.5, "decided_at": now - i * 3600, "event_id": f"f{i}"})
        events.append({"approver": "slow", "action": "wire", "risk": i % 4,
                       "decision": "reject" if i % 10 == 0 else "approve",
                       "seconds": [10, 20, 40, 80][i % 4], "decided_at": now - i * 3600, "event_id": f"s{i}"})
    r = client.post("/v1/approvals/batch", json={"events": events})
    assert r.json()["created"] == 120
    o = client.get("/v1/overview").json()
    by = {a["approver"]: a for a in o["approvers"]}
    assert by["fast"]["label"] == "rubber_stamp"
    assert by["slow"]["label"] == "healthy"
    assert o["flagged_count"] == 1
    assert o["approvers"][0]["approver"] == "fast"  # worst first
    d = client.get("/v1/digest").json()
    assert "fast" in d["flagged"] and "slow" not in d["flagged"]
    det = client.get("/v1/approvers/fast").json()
    assert det["flags"] and len(det["histogram"]) == 6


# ---- project + key management ----

def test_api_key_stored_hashed_not_plaintext(client):
    from server import db
    with db.conn() as c:
        row = c.execute("SELECT api_key_hash FROM projects WHERE name='t'").fetchone()
    assert row["api_key_hash"] != "dl_test"
    assert db.project_for_key("dl_test") is not None


def test_rotate_key_invalidates_old_key(client):
    from server import db
    p = db.create_project("rot")
    old_key = p["api_key"]
    assert db.project_for_key(old_key) is not None
    rotated = db.rotate_key(p["id"])
    assert rotated["api_key"] != old_key
    assert db.project_for_key(old_key) is None
    assert db.project_for_key(rotated["api_key"])["id"] == p["id"]


def test_rotate_key_unknown_project_raises(client):
    from server import db
    with pytest.raises(KeyError):
        db.rotate_key(999999)


def test_admin_endpoints_disabled_without_admin_key(client):
    r = client.post("/v1/admin/projects", json={"name": "x"})
    assert r.status_code == 403


def test_admin_create_project_and_rotate_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFTLINE_DB", str(tmp_path / "admin.db"))
    monkeypatch.setenv("DRIFTLINE_ADMIN_KEY", "admin-secret")
    import importlib
    from server import db
    importlib.reload(db)
    from server import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    db.init()
    with TestClient(appmod.app) as c:
        r = c.post("/v1/admin/projects", json={"name": "newco"}, headers={"X-Driftline-Admin-Key": "wrong"})
        assert r.status_code == 401
        r = c.post("/v1/admin/projects", json={"name": "newco"}, headers={"X-Driftline-Admin-Key": "admin-secret"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "newco" and body["api_key"].startswith("dl_")
        pid = body["id"]
        r = c.get("/v1/overview", headers={"X-Driftline-Key": body["api_key"]})
        assert r.status_code == 200
        r = c.post(f"/v1/admin/projects/{pid}/rotate-key", headers={"X-Driftline-Admin-Key": "admin-secret"})
        assert r.status_code == 200
        new_key = r.json()["api_key"]
        assert new_key != body["api_key"]
        r = c.get("/v1/overview", headers={"X-Driftline-Key": body["api_key"]})
        assert r.status_code == 401
        r = c.get("/v1/overview", headers={"X-Driftline-Key": new_key})
        assert r.status_code == 200
        r = c.post(f"/v1/admin/projects/999999/rotate-key", headers={"X-Driftline-Admin-Key": "admin-secret"})
        assert r.status_code == 404


def test_sdk_roundtrip(client, monkeypatch):
    """SDK against the real app via TestClient transport."""
    import driftline
    sent = {}

    def fake_send(self, events):
        r = client.post("/v1/approvals/batch", json={"events": events})
        sent["status"] = r.status_code
        sent["created"] = r.json()["created"]

    monkeypatch.setattr(driftline.Client, "_send", fake_send)
    dl = driftline.Client(api_key="dl_test", flush_interval=60)
    rv = dl.present(approver="m", action="wire", risk="high", amount=900.0)
    rv.approve()
    rv.reject()  # second call is ignored
    dl.log_approval(approver="m", action="x", decision="reject", seconds=4.2)
    dl.flush()
    assert sent == {"status": 201, "created": 2}
