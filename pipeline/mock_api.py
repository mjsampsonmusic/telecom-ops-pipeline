"""Mock ticketing REST API, standing in for a third-party SaaS platform.

GET /api/v1/tickets?page=N&page_size=M   -> {"data": [...], "next_page": N+1 | null}
Requires header  Authorization: Bearer <token>.
Set FAIL_RATE > 0 to inject HTTP 503s so client retry logic gets exercised.
"""
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TOKEN = "dev-token"


def make_handler(tickets: list, fail_rate: float, seed: int = 7):
    rng = random.Random(seed)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output quiet
            pass

        def _send(self, code: int, body: dict):
            payload = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path != "/api/v1/tickets":
                return self._send(404, {"error": "not found"})
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                return self._send(401, {"error": "unauthorized"})
            if rng.random() < fail_rate:
                return self._send(503, {"error": "temporarily unavailable"})
            qs = parse_qs(url.query)
            page = int(qs.get("page", ["1"])[0])
            size = min(int(qs.get("page_size", ["100"])[0]), 250)
            chunk = tickets[(page - 1) * size: page * size]
            nxt = page + 1 if page * size < len(tickets) else None
            return self._send(200, {"data": chunk, "next_page": nxt})

    return Handler


def serve_in_background(tickets_path: Path, port: int = 0, fail_rate: float = 0.0):
    tickets = json.loads(Path(tickets_path).read_text())
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(tickets, fail_rate))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"
