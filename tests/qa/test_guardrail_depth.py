import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def adapter_responses():
    state = {"mode": "bad_json"}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if state["mode"] == "timeout":
                threading.Event().wait(2)
                return
            payload = b"not json" if state["mode"] == "bad_json" else json.dumps(
                {"response": "I cannot help with that request."}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except BrokenPipeError:
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_guardrail_run_id_is_hidden_from_another_project(client, adapter_responses):
    _, url = adapter_responses
    owner_run = client.post("/v1/guardrail/run", json={"adapter_url": url})
    assert owner_run.status_code == 201

    created = client.post(
        "/v1/admin/projects",
        json={"name": "other guardrail project"},
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert created.status_code == 201
    other = client.get(
        f"/v1/guardrail/runs/{owner_run.json()['id']}",
        headers={"X-Driftline-Key": created.json()["api_key"]},
    )
    assert other.status_code == 404


@pytest.mark.parametrize("limit, expected", [(0, 422), (1, 200), (200, 200), (201, 422)])
def test_guardrail_run_limit_bounds(client, limit, expected):
    response = client.get(f"/v1/guardrail/runs?limit={limit}")
    assert response.status_code == expected


@pytest.mark.parametrize("url", ["file:///tmp/adapter", "ftp://example.test/adapter"])
def test_guardrail_rejects_non_http_adapter_urls(client, url):
    response = client.post("/v1/guardrail/run", json={"adapter_url": url})
    assert response.status_code == 422


@pytest.mark.parametrize("mode", ["bad_json", "timeout"])
def test_guardrail_adapter_errors_are_recorded_as_inconclusive(client, adapter_responses, mode):
    state, url = adapter_responses
    state["mode"] = mode
    response = client.post("/v1/guardrail/run", json={"adapter_url": url})
    assert response.status_code == 201
    body = response.json()
    assert body["errored"] > 0
    assert body["passed"] is not None
    assert all(result["passed"] is None for result in body["results"])


@pytest.mark.xfail(strict=True, reason="BUG-4 SECURITY: private link-local adapter target is accepted")
def test_guardrail_rejects_link_local_adapter_target(client):
    response = client.post(
        "/v1/guardrail/run", json={"adapter_url": "http://169.254.169.254/"}
    )
    assert response.status_code == 422
