# PRD: Snippet Search (smoke test)

## What it is
A tiny HTTP service that stores short text snippets and finds them by keyword. It exists to prove the factory end to end, so it stays small.

## Stack
Python 3.12 standard library only (http.server, sqlite3, unittest). No third-party packages. Entry point `python -m app.server --port <n>`; `APP_DATABASE` env var is the SQLite path.

## Build order
1. **Skeleton:** runnable server with `GET /health` (200, `{"ok": true}`) and `GET /build-id` (the 40-char git commit of the running checkout), unit tests, and a GitHub Actions CI workflow `.github/workflows/ci.yml` (job name `tests`) that runs `python -m compileall -q app tests` and `python -m unittest discover -s tests` on push to main and on pull requests.
2. **Snippets:** `POST /snippets` with JSON `{"title": str, "body": str}` stores a snippet (201, returns its id); `GET /search?q=<words>` returns snippets whose title or body contains every word (case-insensitive), newest first, as JSON `[{"id", "title", "body"}]`. Empty or missing `q` returns 400. Data persists in the SQLite file across restarts.

## Journeys
1. A user checks the service is up: `/health` answers 200.
2. A user adds two snippets and searches a word only one contains: exactly that one comes back.

## Out of scope
Auth, a web UI, fuzzy or semantic search, pagination, deleting or editing snippets, any third-party package.
