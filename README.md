# port-factory-smoke

Throwaway repo for testing the AI Software Factory (on Codex) together with Port. Built from `docs/prd.md` by the factory.

Run with Python 3.12: `python -m app.server --port 8000`. Set `APP_DATABASE`
to the SQLite file to retain across restarts (defaults to `snippets.sqlite` in
the working directory).

`POST /snippets` accepts a JSON object with string `title` and `body` fields
and returns `201` with `{"id": <integer>}` after committing the write.
`GET /search?q=<words>` returns objects with `id`, `title`, and `body`,
newest first. Every whitespace-separated word must occur in either field,
using case-insensitive literal substring matching. Missing or blank queries
and invalid snippet payloads return `400`.

Run the ordinary checks with `python harness/ci.py`. Runtime scenarios are
defined in `harness/END-TO-END.md`.
