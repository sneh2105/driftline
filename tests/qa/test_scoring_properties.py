import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from uuid import uuid4


def log_event(client, approver, seconds, decision="approve"):
    response = client.post(
        "/v1/approvals",
        json={
            "approver": approver,
            "action": "review transfer",
            "decision": decision,
            "seconds": seconds,
        },
    )
    assert response.status_code == 201


def approver_components(client, name):
    response = client.get(f"/v1/approvers/{name}")
    assert response.status_code == 200
    return response.json()


@given(st.integers(min_value=0, max_value=10_000), st.integers(min_value=0, max_value=10_000))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_slower_median_never_lowers_speed_component(client, faster, slower):
    suffix = uuid4().hex
    faster_name, slower_name = f"faster-{suffix}", f"slower-{suffix}"
    low, high = sorted((faster, slower))
    log_event(client, faster_name, low)
    log_event(client, slower_name, high)

    faster_detail = approver_components(client, faster_name)
    slower_detail = approver_components(client, slower_name)

    assert slower_detail["median_seconds"] >= faster_detail["median_seconds"]
    assert slower_detail["components"]["speed"] >= faster_detail["components"]["speed"]


@given(st.integers(min_value=0, max_value=10_000))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_adding_a_reject_never_lowers_reject_component(client, seconds):
    reviewer = f"reviewer-{uuid4().hex}"
    for _ in range(3):
        log_event(client, reviewer, seconds)
    before = approver_components(client, reviewer)["components"]["rejects"]

    log_event(client, reviewer, seconds, decision="reject")
    after = approver_components(client, reviewer)["components"]["rejects"]

    assert after >= before


@given(st.lists(st.tuples(st.integers(min_value=0, max_value=10_000), st.sampled_from(["approve", "reject"])), min_size=1, max_size=12))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_score_always_stays_in_spec_range(client, events):
    reviewer = f"reviewer-{uuid4().hex}"
    for seconds, decision in events:
        log_event(client, reviewer, seconds, decision)

    score = approver_components(client, reviewer)["score"]
    assert 0 <= score <= 100


def test_small_samples_never_flag(client):
    log_event(client, "reviewer", 0)

    detail = approver_components(client, "reviewer")
    assert detail["n"] == 1
    assert detail["flags"] == []


def test_empty_input_is_safe(client):
    response = client.get("/v1/overview")

    assert response.status_code == 200
    assert response.json()["org"]["n"] == 0
    assert response.json()["org"]["score"] is None
    assert response.json()["org"]["label"] == "no_data"
