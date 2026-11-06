"""Digest delivery: Slack webhook + SMTP email. Off by default (SPEC.md ยง11).

Each channel activates only when its env vars are set; with none set,
deliver_digest() is a no-op that reports both channels as "disabled".
"""
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from typing import Optional


def slack_webhook_url() -> Optional[str]:
    return os.environ.get("DRIFTLINE_SLACK_WEBHOOK_URL") or None


def smtp_config() -> Optional[dict]:
    host = os.environ.get("DRIFTLINE_SMTP_HOST")
    to_addr = os.environ.get("DRIFTLINE_SMTP_TO")
    if not host or not to_addr:
        return None
    user = os.environ.get("DRIFTLINE_SMTP_USER")
    return {
        "host": host,
        "port": int(os.environ.get("DRIFTLINE_SMTP_PORT", "587")),
        "user": user,
        "password": os.environ.get("DRIFTLINE_SMTP_PASSWORD"),
        "use_tls": os.environ.get("DRIFTLINE_SMTP_TLS", "true").lower() != "false",
        "from_addr": os.environ.get("DRIFTLINE_SMTP_FROM") or user,
        "to": [a.strip() for a in to_addr.split(",") if a.strip()],
    }


def send_slack(webhook_url: str, text: str) -> None:
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Slack webhook returned HTTP {resp.status}")


def send_email(cfg: dict, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = ", ".join(cfg["to"])
    msg.set_content(body)
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as s:
        if cfg["use_tls"]:
            s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"] or "")
        s.send_message(msg)


def deliver_digest(subject: str, text: str) -> dict:
    """Send digest text to every configured channel; unconfigured channels report "disabled"."""
    result = {}

    webhook = slack_webhook_url()
    if webhook:
        try:
            send_slack(webhook, text)
            result["slack"] = "sent"
        except Exception as exc:
            result["slack"] = f"error: {exc}"
    else:
        result["slack"] = "disabled"

    cfg = smtp_config()
    if cfg:
        try:
            send_email(cfg, subject, text)
            result["email"] = "sent"
        except Exception as exc:
            result["email"] = f"error: {exc}"
    else:
        result["email"] = "disabled"

    return result
