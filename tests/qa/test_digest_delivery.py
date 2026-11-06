import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _smtp_server():
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 localhost ready\r\n")
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                command = line.decode("ascii", errors="replace").strip().upper()
                if command.startswith("EHLO") or command.startswith("HELO"):
                    self.wfile.write(b"250 localhost\r\n")
                elif command.startswith("MAIL FROM") or command.startswith("RCPT TO"):
                    self.wfile.write(b"250 ok\r\n")
                elif command == "DATA":
                    self.wfile.write(b"354 end with dot\r\n")
                    while self.rfile.readline().strip() != b".":
                        pass
                    self.wfile.write(b"250 queued\r\n")
                elif command == "QUIT":
                    self.wfile.write(b"221 bye\r\n")
                    return
                else:
                    self.wfile.write(b"250 ok\r\n")

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_digest_send_with_no_channels_configured_is_disabled(client, monkeypatch):
    for name in (
        "DRIFTLINE_SLACK_WEBHOOK_URL",
        "DRIFTLINE_SMTP_HOST",
        "DRIFTLINE_SMTP_TO",
        "DRIFTLINE_SMTP_USER",
        "DRIFTLINE_SMTP_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    response = client.post("/v1/digest/send")

    assert response.status_code == 200
    assert response.json()["delivery"] == {"slack": "disabled", "email": "disabled"}


def test_digest_send_posts_to_local_slack_webhook(client, monkeypatch):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("DRIFTLINE_SLACK_WEBHOOK_URL", f"http://127.0.0.1:{server.server_port}/hook")
    monkeypatch.delenv("DRIFTLINE_SMTP_HOST", raising=False)
    monkeypatch.delenv("DRIFTLINE_SMTP_TO", raising=False)
    try:
        response = client.post("/v1/digest/send")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.status_code == 200
    assert response.json()["delivery"] == {"slack": "sent", "email": "disabled"}
    assert len(received) == 1
    assert isinstance(received[0].get("text"), str)


def test_failed_slack_does_not_block_smtp_delivery(client, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(500)
            self.end_headers()

        def log_message(self, *_args):
            pass

    http_server = HTTPServer(("127.0.0.1", 0), Handler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    smtp_server, smtp_thread = _smtp_server()
    monkeypatch.setenv("DRIFTLINE_SLACK_WEBHOOK_URL", f"http://127.0.0.1:{http_server.server_port}/hook")
    monkeypatch.setenv("DRIFTLINE_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("DRIFTLINE_SMTP_PORT", str(smtp_server.server_address[1]))
    monkeypatch.setenv("DRIFTLINE_SMTP_TO", "qa@example.test")
    monkeypatch.setenv("DRIFTLINE_SMTP_TLS", "false")
    monkeypatch.delenv("DRIFTLINE_SMTP_USER", raising=False)
    monkeypatch.delenv("DRIFTLINE_SMTP_PASSWORD", raising=False)
    try:
        response = client.post("/v1/digest/send")
    finally:
        http_server.shutdown()
        http_server.server_close()
        http_thread.join(timeout=2)
        smtp_server.shutdown()
        smtp_server.server_close()
        smtp_thread.join(timeout=2)

    assert response.status_code == 200
    delivery = response.json()["delivery"]
    assert delivery["slack"].startswith("error:")
    assert delivery["email"] == "sent"


def test_smtp_requires_both_host_and_recipients(client, monkeypatch):
    monkeypatch.delenv("DRIFTLINE_SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DRIFTLINE_SMTP_HOST", "127.0.0.1")
    monkeypatch.delenv("DRIFTLINE_SMTP_TO", raising=False)

    missing_recipients = client.post("/v1/digest/send")

    monkeypatch.delenv("DRIFTLINE_SMTP_HOST", raising=False)
    monkeypatch.setenv("DRIFTLINE_SMTP_TO", "qa@example.test")
    missing_host = client.post("/v1/digest/send")

    assert missing_recipients.status_code == 200
    assert missing_recipients.json()["delivery"]["email"] == "disabled"
    assert missing_host.status_code == 200
    assert missing_host.json()["delivery"]["email"] == "disabled"
