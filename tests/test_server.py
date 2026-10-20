from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote

from app.server import build_identity


ROOT = Path(__file__).resolve().parent.parent


def request(port, path, method="GET", body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request(method, path, body=body)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()
    finally:
        connection.close()


@contextmanager
def running_service(candidate=None, snapshot=False, database=None):
    with tempfile.TemporaryDirectory(prefix="skeleton-test-", dir=ROOT) as directory:
        state = Path(directory)
        checkout = ROOT
        if snapshot:
            checkout = state / "snapshot"
            shutil.copytree(
                ROOT / "app", checkout / "app",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        env = os.environ.copy()
        env.pop("FACTORY_RUNTIME_CANDIDATE", None)
        env["APP_DATABASE"] = str(database or state / "snippets.sqlite")
        if candidate is not None:
            env["FACTORY_RUNTIME_CANDIDATE"] = candidate
        if snapshot:
            # The snapshot must start without either Git metadata or Git itself.
            env["PATH"] = ""
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with (state / "server.log").open("w+", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.server", "--port", str(port)],
                cwd=checkout, env=env, stdout=log, stderr=log,
            )
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        if request(port, "/health")[0] == 200:
                            yield port
                            return
                    except OSError:
                        pass
                    time.sleep(0.05)
                log.seek(0)
                raise AssertionError("Service did not become healthy:\n" + log.read())
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


class ServiceTests(unittest.TestCase):
    def test_health_is_exact_json_without_redirect(self):
        with running_service() as port:
            status, headers, body = request(port, "/health")
            self.assertEqual(status, 200)
            self.assertNotIn("Location", headers)
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
            self.assertEqual(json.loads(body), {"ok": True})

    def test_build_id_is_checkout_commit(self):
        expected = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10,
        ).strip()
        with running_service() as port:
            status, _, body = request(port, "/build-id")
            self.assertEqual(status, 200)
            self.assertRegex(body, r"^[0-9a-f]{40}$")
            self.assertEqual(body, expected)

    def test_candidate_overrides_checkout_commit(self):
        with running_service(candidate="runtime-probe-123") as port:
            status, _, body = request(port, "/build-id")
            self.assertEqual(status, 200)
            self.assertEqual(body, "runtime-probe-123")

    def test_candidate_works_in_snapshot_without_git(self):
        with running_service(candidate="runtime-probe-123", snapshot=True) as port:
            self.assertEqual(request(port, "/build-id")[::2], (200, "runtime-probe-123"))
            self.assertEqual(json.loads(request(port, "/health")[2]), {"ok": True})

    def test_candidate_is_preserved_exactly_even_when_empty(self):
        for candidate in ("", " candidate with whitespace \n", "candidate-\u2603"):
            with self.subTest(candidate=candidate):
                with patch.dict(os.environ, {"FACTORY_RUNTIME_CANDIDATE": candidate}):
                    self.assertEqual(build_identity(), candidate)

    def test_git_identity_is_independent_of_working_directory(self):
        with patch.dict(os.environ):
            os.environ.pop("FACTORY_RUNTIME_CANDIDATE", None)
            with patch("app.server.subprocess.run") as run:
                run.return_value.stdout = "a" * 40 + "\n"
                self.assertEqual(build_identity(), "a" * 40)
                self.assertEqual(run.call_args.kwargs["cwd"], ROOT)

    def test_unknown_routes_return_404(self):
        with running_service() as port:
            for method, path in (
                ("POST", "/missing"), ("GET", "/missing"),
            ):
                with self.subTest(method=method, path=path):
                    self.assertEqual(request(port, path, method)[0], 404)

    def create_snippet(self, port, title, body):
        status, headers, response = request(
            port, "/snippets", "POST", json.dumps({"title": title, "body": body}),
        )
        self.assertEqual(status, 201)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        result = json.loads(response)
        self.assertEqual(set(result), {"id"})
        self.assertIs(type(result["id"]), int)
        return {"id": result["id"], "title": title, "body": body}

    def assert_search(self, port, query, expected):
        status, headers, body = request(port, "/search?q=" + quote(query))
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body), expected)

    def test_creation_search_and_restart_durability(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "snippets.sqlite"
            with running_service(database=database) as port:
                lighthouse = self.create_snippet(port, "Lighthouse", "keeper lights the lamp")
                harbor = self.create_snippet(port, "Harbor", "boats rest at night")
                self.assertNotEqual(lighthouse["id"], harbor["id"])
                for query, expected in (
                    ("lamp", [lighthouse]),
                    ("LIGHTHOUSE LAMP", [lighthouse]),
                    ("lamp boats", []),
                    ("missingword", []),
                    ("h", [harbor, lighthouse]),
                    ("\tLIGHTHOUSE\n lamp  ", [lighthouse]),
                ):
                    with self.subTest(query=query):
                        self.assert_search(port, query, expected)
            with running_service(database=database) as port:
                self.assert_search(port, "h", [harbor, lighthouse])
                third = self.create_snippet(port, "Third", "another lamp")
                self.assertGreater(third["id"], max(harbor["id"], lighthouse["id"]))
                self.assert_search(port, "lamp", [third, lighthouse])

    def test_search_requires_nonblank_query(self):
        with running_service() as port:
            for path in ("/search", "/search?q=", "/search?q=%20%20", "/search?q=%09%0A"):
                with self.subTest(path=path):
                    self.assertEqual(request(port, path)[0], 400)

    def test_repeated_titles_preserve_both_snippets_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "snippets.sqlite"
            with running_service(database=database) as port:
                first = self.create_snippet(port, "Notes", "lamp first")
                second = self.create_snippet(port, "Notes", "lamp second")
                self.assertNotEqual(first["id"], second["id"])
                self.assert_search(port, "Notes lamp", [second, first])
            with running_service(database=database) as port:
                self.assert_search(port, "Notes lamp", [second, first])

    def test_creation_rejects_unpaired_surrogates_in_either_field(self):
        with running_service() as port:
            for field in ("title", "body"):
                for surrogate in ("\ud800", "\udfff"):
                    with self.subTest(field=field, surrogate=repr(surrogate)):
                        payload = {"title": "Notes", "body": "lamp"}
                        payload[field] += surrogate
                        status, headers, body = request(
                            port, "/snippets", "POST", json.dumps(payload),
                        )
                        self.assertEqual(status, 400)
                        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
                        self.assertIn("error", json.loads(body))
            self.assert_search(port, "Notes", [])
            self.assert_search(port, "lamp", [])
            snippet = self.create_snippet(port, "Notes \U0001f4a1", "lamp \U0001f4a1")
            self.assert_search(port, "\U0001f4a1", [snippet])

    def test_search_matches_literal_substrings_and_unicode_case(self):
        with running_service() as port:
            self.assert_search(port, "anything", [])
            literal = self.create_snippet(port, "100%_done", "Straße 'quoted'")
            self.create_snippet(port, "100xxdone", "unrelated")
            for query in ("%", "_", "'quoted'", "STRASSE", "DONE strasse"):
                with self.subTest(query=query):
                    self.assert_search(port, query, [literal])
            self.assert_search(port, "' OR 1=1 --", [])

    def test_creation_requires_json_object_with_string_fields(self):
        with running_service() as port:
            for payload in (
                None, "{", "null", "[]", "42", "{}",
                '{"title": "title"}', '{"title": null, "body": "body"}',
                '{"title": "title", "body": 12}',
            ):
                with self.subTest(payload=payload):
                    self.assertEqual(request(port, "/snippets", "POST", payload)[0], 400)
            self.assert_search(port, "title", [])
            self.create_snippet(port, "", "")
            long_body = "lamp " * 20000
            snippet = self.create_snippet(port, "Long", long_body)
            self.assert_search(port, "lamp", [snippet])


if __name__ == "__main__":
    unittest.main()
