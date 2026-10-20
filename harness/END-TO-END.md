# Runtime scenarios

## The service is up

1. Start the app on a fresh database.
2. `GET /health` returns 200 with `{"ok": true}`.
3. `GET /build-id` returns the 40-character commit of the checkout.

**What would make this fail:** a non-200 health, or a build id that is not the running checkout's commit.

## A user finds the right snippet

1. `POST /snippets` with `{"title": "Lighthouse", "body": "keeper lights the lamp"}`, then `{"title": "Harbor", "body": "boats rest at night"}`.
2. `GET /search?q=lamp` returns exactly the Lighthouse snippet.
3. `GET /search?q=` returns 400.

**What would make this fail:** both snippets returned, neither returned, or an empty query accepted.
