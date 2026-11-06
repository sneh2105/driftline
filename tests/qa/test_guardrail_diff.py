import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def adapter():
    state = {"mode": "refuse", "target": None, "prompts": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            prompt = request["prompt"]
            state["prompts"].append(prompt)
            if state["mode"] == "error" and prompt == state["target"]:
                self.send_response(503)
                self.end_headers()
                return
            response = "I cannot help with that request."
            if state["mode"] == "fail" and prompt == state["target"]:
                response = "Here are the requested instructions."
            payload = json.dumps({"response": response}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield state
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _run(client, adapter):
    return client.post("/v1/guardrail/run", json={"adapter_url": adapter["url"]})


def test_guardrail_diff_reports_only_new_pass_to_fail_regressions(client, adapter):
    first = _run(client, adapter)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["n"] > 0
    assert first_body["regressions"] == []

    adapter["target"] = adapter["prompts"][0]
    adapter["mode"] = "fail"
    second = _run(client, adapter)
    assert second.status_code == 201
    second_body = second.json()
    target_index = adapter["prompts"][:first_body["n"]].index(adapter["target"])
    target_result = second_body["results"][target_index]
    assert target_result["passed"] is False
    assert len(second_body["regressions"]) == 1
    regression = second_body["regressions"][0]
    assert regression.get("probe_id", regression.get("id")) == target_result.get("id", target_result.get("probe_id"))

    # A failure already present in the immediately previous run is not new.
    third = _run(client, adapter)
    assert third.status_code == 201
    assert third.json()["regressions"] == []


def test_guardrail_diff_excludes_improvements_and_adapter_errors(client, adapter):
    first = _run(client, adapter)
    assert first.status_code == 201
    adapter["target"] = adapter["prompts"][0]
    adapter["mode"] = "fail"
    failing = _run(client, adapter)
    assert failing.status_code == 201
    assert len(failing.json()["regressions"]) == 1

    # The formerly failing probe improves; another probe errors and is excluded.
    prompts_from_failing_run = adapter["prompts"][-failing.json()["n"]:]
    adapter["mode"] = "error"
    adapter["target"] = next(prompt for prompt in prompts_from_failing_run if prompt != adapter["target"])
    improved = _run(client, adapter)
    assert improved.status_code == 201
    body = improved.json()
    assert body["errored"] == 1
    assert body["regressions"] == []
