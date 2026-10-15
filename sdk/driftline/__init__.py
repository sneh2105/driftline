"""Driftline SDK. Stdlib only.

    import driftline
    dl = driftline.Client(api_key="dl_...", base_url="https://your-driftline")

    # 1. Timestamps you already have
    dl.log_approval(approver="maria@acme.com", action="wire_transfer", risk="critical",
                    decision="approve", shown_at=t0, decided_at=t1, amount=50_000)

    # 2. Or wrap the moment the request is shown to the human
    review = dl.present(approver="maria@acme.com", action="send_email", risk="low")
    ...  # human looks at it
    review.approve()   # or review.reject(reason="wrong recipient")

Logging never blocks or raises in your approval flow. Events go on a background
queue and are sent in batches. Call dl.flush() before process exit if you care.
"""
from __future__ import annotations

import atexit
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional, Union

__all__ = ["Client", "Review"]
log = logging.getLogger("driftline")

Num = Union[int, float]


class Review:
    """Started when an approval request is shown to a human."""

    def __init__(self, client: "Client", approver: str, action: str, risk: Union[str, int],
                 agent: Optional[str], amount: Optional[float], meta: Optional[dict]):
        self._c = client
        self._kw = dict(approver=approver, action=action, risk=risk, agent=agent, amount=amount, meta=meta)
        self.shown_at = time.time()
        self._done = False

    def _finish(self, decision: str, reason: Optional[str]):
        if self._done:
            return
        self._done = True
        meta = dict(self._kw["meta"] or {})
        if reason:
            meta["reason"] = reason
        kw = dict(self._kw, meta=meta or None)
        self._c.log_approval(decision=decision, shown_at=self.shown_at, decided_at=time.time(), **kw)

    def approve(self, reason: Optional[str] = None):
        self._finish("approve", reason)

    def reject(self, reason: Optional[str] = None):
        self._finish("reject", reason)


class Client:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000",
                 batch_size: int = 50, flush_interval: float = 2.0, timeout: float = 5.0,
                 enabled: bool = True):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.timeout = timeout
        self.enabled = enabled
        self._q: "queue.Queue[dict]" = queue.Queue(maxsize=10_000)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if enabled:
            self._thread = threading.Thread(target=self._run, name="driftline-sender", daemon=True)
            self._thread.start()
            atexit.register(self.close)

    # ---- public ----
    def present(self, approver: str, action: str, risk: Union[str, int] = "medium",
                agent: Optional[str] = None, amount: Optional[float] = None,
                meta: Optional[dict] = None) -> Review:
        return Review(self, approver, action, risk, agent, amount, meta)

    def log_approval(self, approver: str, action: str, decision: str, risk: Union[str, int] = "medium",
                     shown_at: Optional[Num] = None, decided_at: Optional[Num] = None,
                     seconds: Optional[float] = None, agent: Optional[str] = None,
                     amount: Optional[float] = None, event_id: Optional[str] = None,
                     meta: Optional[dict] = None) -> None:
        if not self.enabled:
            return
        ev: dict[str, Any] = {"approver": approver, "action": action, "decision": decision, "risk": risk,
                              "event_id": event_id or uuid.uuid4().hex}
        for k, v in (("shown_at", shown_at), ("decided_at", decided_at), ("seconds", seconds),
                     ("agent", agent), ("amount", amount), ("meta", meta)):
            if v is not None:
                ev[k] = v
        try:
            self._q.put_nowait(ev)
        except queue.Full:
            log.warning("driftline: queue full, dropping event")

    def flush(self, timeout: float = 10.0) -> None:
        """Block until queued events are sent (or timeout)."""
        deadline = time.time() + timeout
        while not self._q.empty() and time.time() < deadline:
            self._send(self._drain())
        # anything the worker is mid-send on
        time.sleep(0.05)

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        try:
            self.flush(3.0)
        except Exception:  # never break shutdown
            pass

    # ---- internals ----
    def _drain(self) -> list[dict]:
        out = []
        while len(out) < self.batch_size:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        return out

    def _run(self):
        while not self._stop.is_set():
            time.sleep(self.flush_interval)
            batch = self._drain()
            while batch:
                self._send(batch)
                batch = self._drain()

    def _send(self, events: list[dict]) -> None:
        if not events:
            return
        body = json.dumps({"events": events}).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/approvals/batch", data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Driftline-Key": self.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                r.read()
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600:
                self._requeue(events)
            else:
                log.warning("driftline: server rejected batch (%s): %s", e.code, e.read()[:200])
        except Exception as e:  # network down etc.
            log.warning("driftline: send failed (%s), will retry", e)
            self._requeue(events)

    def _requeue(self, events: list[dict]) -> None:
        for ev in events:  # event_id keeps retries idempotent
            try:
                self._q.put_nowait(ev)
            except queue.Full:
                break
