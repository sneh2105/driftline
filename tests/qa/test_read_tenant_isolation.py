import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


def _create_project(client, name):
    response = client.post(
        "/v1/admin/projects",
        json={"name": name},
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert response.status_code == 201
    return response.json()["api_key"]


def _ingest_review(client, key, approver, decision="approve"):
    return client.post(
        "/v1/approvals",
        json={
            "approver": approver,
            "action": "tenant isolation check",
            "decision": decision,
            "seconds": 1,
        },
        headers={"X-Driftline-Key": key},
    )


def test_approver_detail_is_scoped_to_project(client):
    other_key = _create_project(client, "approver isolation")
    assert _ingest_review(client, other_key, "other-only-reviewer").status_code == 201

    visible = client.get("/v1/approvers/other-only-reviewer")
    hidden = client.get(
        f"/v1/approvers/{quote('other-only-reviewer', safe='')}",
        headers={"X-Driftline-Key": other_key},
    )

    assert visible.status_code == 404
    assert hidden.status_code == 200
    assert hidden.json()["approver"] == "other-only-reviewer"


def test_digest_contains_only_current_projects_flagged_reviewer(client):
    other_key = _create_project(client, "digest isolation")
    for _ in range(50):
        assert _ingest_review(client, "dl_qa_test", "first-project-reviewer").status_code == 201
        assert _ingest_review(client, other_key, "second-project-reviewer").status_code == 201

    first_digest = client.get("/v1/digest").text
    second_digest = client.get(
        "/v1/digest", headers={"X-Driftline-Key": other_key}
    ).text

    assert "first-project-reviewer" in first_digest
    assert "second-project-reviewer" not in first_digest
    assert "second-project-reviewer" in second_digest
    assert "first-project-reviewer" not in second_digest


def test_guardrail_run_list_is_scoped_to_project(client):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.dumps({"response": "I cannot help with that request."}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    adapter_url = f"http://127.0.0.1:{server.server_port}"
    try:
        first_run = client.post("/v1/guardrail/run", json={"adapter_url": adapter_url})
        assert first_run.status_code == 201

        other_key = _create_project(client, "guardrail list isolation")
        second_run = client.post(
            "/v1/guardrail/run",
            json={"adapter_url": adapter_url},
            headers={"X-Driftline-Key": other_key},
        )
        assert second_run.status_code == 201

        first_ids = {run["id"] for run in client.get("/v1/guardrail/runs").json()["runs"]}
        second_ids = {
            run["id"]
            for run in client.get(
                "/v1/guardrail/runs", headers={"X-Driftline-Key": other_key}
            ).json()["runs"]
        }

        assert first_run.json()["id"] in first_ids
        assert second_run.json()["id"] not in first_ids
        assert second_run.json()["id"] in second_ids
        assert first_run.json()["id"] not in second_ids
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
