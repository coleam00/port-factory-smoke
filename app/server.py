"""Run the service with ``python -m app.server --port <port>``."""

import argparse
import json
import os
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from app.snippets import Snippets


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
        self.snippets = Snippets(os.environ.get("APP_DATABASE", "snippets.sqlite"))
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        if path == "/health":
            self.respond(200, b'{"ok": true}', "application/json")
        elif path == "/build-id":
            self.respond(200, self.server.build_id.encode("utf-8"), "text/plain")
        elif path == "/search":
            query = parse_qs(url.query, keep_blank_values=True).get("q", [""])[0]
            words = query.casefold().split()
            if not words:
                self.respond_json(400, {"error": "q must contain search words"})
                return
            self.respond_json(200, self.server.snippets.search(words))
        else:
            self.respond(404, b'{"error": "not found"}', "application/json")

    def do_POST(self):
        if urlsplit(self.path).path != "/snippets":
            self.respond_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            self.respond_json(400, {"error": "expected a JSON object"})
            return
        if not isinstance(payload, dict) or not all(
            isinstance(payload.get(field), str) for field in ("title", "body")
        ):
            self.respond_json(400, {"error": "title and body must be strings"})
            return
        try:
            payload["title"].encode("utf-8")
            payload["body"].encode("utf-8")
        except UnicodeEncodeError:
            self.respond_json(400, {"error": "title and body must be valid Unicode"})
            return
        snippet_id = self.server.snippets.create(payload["title"], payload["body"])
        self.respond_json(201, {"id": snippet_id})

    def respond_json(self, status, payload):
        self.respond(status, json.dumps(payload).encode("utf-8"), "application/json")

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
