import json

import pytest


def approval(event_id):
    return {
        "approver": "rate reviewer",
        "action": "review transfer",
        "decision": "approve",
        "seconds": 2,
        "event_id": event_id,
    }


def test_rate_limit_rejects_request_301_with_retry_after(client):
    for index in range(300):
        response = client.post("/v1/approvals", json=approval(f"limited-{index}"))
        assert response.status_code == 201

    limited = client.post("/v1/approvals", json=approval("limited-301"))
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_batch_counts_as_one_rate_limited_request(client):
    events = [approval(f"batch-{index}") for index in range(1000)]
    response = client.post("/v1/approvals/batch", json={"events": events})
    assert response.status_code == 201
    assert response.json()["created"] == 1000


def test_rate_limit_is_isolated_between_projects(client):
    created = client.post(
        "/v1/admin/projects",
        json={"name": "rate isolated"},
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert created.status_code == 201
    other_key = created.json()["api_key"]

    for index in range(300):
        response = client.post("/v1/approvals", json=approval(f"flood-{index}"))
        assert response.status_code == 201

    assert client.post("/v1/approvals", json=approval("flood-extra")).status_code == 429
    other = client.post(
        "/v1/approvals",
        json=approval("other-project"),
        headers={"X-Driftline-Key": other_key},
    )
    assert other.status_code == 201


@pytest.mark.xfail(strict=True, reason="BUG-1: exactly 1 MiB approval body is rejected with 413")
def test_body_exactly_one_megabyte_is_accepted(client):
    prefix = b'{"approver":"r","action":"a","decision":"approve","seconds":2,"meta":{"padding":"'
    suffix = b'"}}'
    body = prefix + (b"x" * (1024 * 1024 - len(prefix) - len(suffix))) + suffix
    assert len(body) == 1024 * 1024
    response = client.post("/v1/approvals", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 201


def test_body_over_one_megabyte_is_rejected(client):
    body = json.dumps(approval("large"), separators=(",", ":"))[:-1]
    body += ',"meta":{"padding":"' + ("x" * (1024 * 1024)) + '"}}'
    response = client.post("/v1/approvals", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 413


@pytest.mark.xfail(strict=True, reason="BUG-2: over-limit chunked approval body returns 400 instead of 413")
def test_chunked_body_over_one_megabyte_is_rejected(client):
    prefix = b'{"approver":"r","action":"a","decision":"approve","seconds":2,"meta":{"padding":"'
    suffix = b'"}}'
    padding_size = 1024 * 1024 - len(prefix) - len(suffix) + 1

    def chunks():
        yield prefix
        yield b"x" * padding_size
        yield suffix

    response = client.post(
        "/v1/approvals",
        content=chunks(),
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    assert response.status_code == 413
