import pytest


def event(**overrides):
    body = {"approver": "qa reviewer", "action": "review transfer", "decision": "approve", "seconds": 2}
    body.update(overrides)
    return body


@pytest.mark.parametrize("seconds", [-0.001, -1, -10**9])
def test_negative_seconds_are_rejected(client, seconds):
    response = client.post("/v1/approvals", json=event(seconds=seconds))
    assert response.status_code == 422


@pytest.mark.parametrize("seconds", [0, 10**100])
def test_zero_and_very_large_seconds_are_accepted(client, seconds):
    response = client.post("/v1/approvals", json=event(seconds=seconds))
    assert response.status_code == 201


def test_decided_before_shown_is_rejected(client):
    response = client.post("/v1/approvals", json=event(shown_at=200, decided_at=199))
    assert response.status_code == 422


@pytest.mark.parametrize("risk", ["urgent", "", -1, 4, 1.5])
def test_invalid_risk_is_rejected(client, risk):
    assert client.post("/v1/approvals", json=event(risk=risk)).status_code == 422


def test_unicode_and_maximum_length_strings_are_accepted(client):
    response = client.post("/v1/approvals", json=event(approver="审核者" * 66, action="💸" * 166))
    assert response.status_code == 201


@pytest.mark.parametrize("field,value", [("approver", "a" * 201), ("action", "a" * 501),
                                           ("approver", ""), ("action", "")])
def test_strings_outside_spec_lengths_are_rejected(client, field, value):
    assert client.post("/v1/approvals", json=event(**{field: value})).status_code == 422


def test_batch_of_1000_is_accepted(client):
    events = [event(event_id=f"batch-{i}") for i in range(1000)]
    response = client.post("/v1/approvals/batch", json={"events": events})
    assert response.status_code == 201
    assert response.json()["received"] == response.json()["created"] == 1000


def test_batch_of_1001_is_rejected(client):
    events = [event(event_id=f"batch-{i}") for i in range(1001)]
    assert client.post("/v1/approvals/batch", json={"events": events}).status_code == 422


def test_repeated_event_id_is_deduplicated_across_single_requests(client):
    body = event(event_id="same-single")
    first = client.post("/v1/approvals", json=body)
    second = client.post("/v1/approvals", json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


def test_repeated_event_id_is_deduplicated_within_batch(client):
    repeated = event(event_id="same-batch")
    response = client.post("/v1/approvals/batch", json={"events": [repeated, repeated]})
    assert response.status_code == 201
    assert response.json()["received"] == 2
    assert response.json()["created"] == 1


@pytest.mark.parametrize("shown,decided", [
    (1_800_000_000, 1_800_000_003),
    ("1800000000", "1800000003"),
    ("2027-01-15T10:00:00Z", "2027-01-15T10:00:03Z"),
    ("2027-01-15T10:00:00", "2027-01-15T10:00:03"),
])
def test_epoch_iso_and_naive_timestamps_are_accepted(client, shown, decided):
    response = client.post("/v1/approvals", json=event(shown_at=shown, decided_at=decided))
    assert response.status_code == 201


@pytest.mark.parametrize("shown,decided", [
    (1_800_000_000, "2027-01-15T10:00:03Z"),
    ("2027-01-15T10:00:00", 1_800_007_203),
])
def test_mixed_timestamp_formats_are_accepted(client, shown, decided):
    response = client.post("/v1/approvals", json=event(shown_at=shown, decided_at=decided))
    assert response.status_code == 201
