"""Run the service with ``python -m app.server --port <port>``."""

import argparse
import os
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def build_identity():
    """Resolve identity once at startup, relative to the installed application."""
    if "FACTORY_RUNTIME_CANDIDATE" in os.environ:
        return os.environ["FACTORY_RUNTIME_CANDIDATE"]
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parent.parent,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


class Service(ThreadingHTTPServer):
    def __init__(self, address):
        self.build_id = build_identity()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self.respond(200, b'{"ok": true}', "application/json")
        elif path == "/build-id":
            self.respond(200, self.server.build_id.encode("utf-8"), "text/plain")
        else:
            self.respond(404, b'{"error": "not found"}', "application/json")

    def do_POST(self):
        self.respond(404, b'{"error": "not found"}', "application/json")

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    with Service(("127.0.0.1", args.port)) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
