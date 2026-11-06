import json
import logging
import urllib.error

import pytest

import driftline


def make_client(monkeypatch, *, batch_size=50):
    # Keep the background worker idle; each test triggers sends explicitly.
    client = driftline.Client(
        api_key="dl_test", base_url="http://driftline.invalid",
        batch_size=batch_size, flush_interval=3600, enabled=True,
    )
    monkeypatch.setattr(client, "_run", lambda: None)
    client._thread.join(timeout=1)
    return client


def test_network_failure_requeues_event_with_same_id(monkeypatch):
    client = make_client(monkeypatch)
    try:
        client.log_approval("reviewer", "transfer", "approve", seconds=1)
        original = client._q.queue[0]
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))

        client._send(client._drain())

        assert client._q.qsize() == 1
        assert client._q.queue[0]["event_id"] == original["event_id"]
    finally:
        client.close()


def test_five_xx_retries_without_changing_event_id(monkeypatch):
    client = make_client(monkeypatch)
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b""

    def urlopen(req, timeout):
        payload = json.loads(req.data)
        calls.extend(payload["events"])
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)
        return Response()

    try:
        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        client.log_approval("reviewer", "transfer", "approve", seconds=1)
        event_id = client._q.queue[0]["event_id"]
        client._send(client._drain())
        assert client._q.qsize() == 1
        client._send(client._drain())
        assert [event["event_id"] for event in calls] == [event_id, event_id]
        assert client._q.empty()
    finally:
        client.close()


def test_queue_full_drops_event_without_raising(monkeypatch, caplog):
    client = make_client(monkeypatch)
    try:
        client._q.maxsize = 1
        client.log_approval("reviewer", "first", "approve", seconds=1)
        with caplog.at_level(logging.WARNING, logger="driftline"):
            assert client.log_approval("reviewer", "second", "reject", seconds=1) is None
        assert client._q.qsize() == 1
        assert "queue full" in caplog.text
    finally:
        client.close()


@pytest.mark.parametrize("first,second", [("approve", "reject"), ("reject", "approve")])
def test_review_only_records_first_decision(monkeypatch, first, second):
    client = make_client(monkeypatch)
    recorded = []
    monkeypatch.setattr(client, "log_approval", lambda **kwargs: recorded.append(kwargs))
    try:
        review = client.present("reviewer", "transfer")
        getattr(review, first)()
        getattr(review, second)()
        assert len(recorded) == 1
        assert recorded[0]["decision"] == first
    finally:
        client.close()


def test_public_logging_calls_do_not_raise_for_network_error(monkeypatch):
    client = make_client(monkeypatch)
    try:
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
        client.log_approval("reviewer", "transfer", "approve", seconds=1)
        client.flush(timeout=0)
        review = client.present("reviewer", "transfer")
        review.approve()
        review.reject()
    finally:
        client.close()
