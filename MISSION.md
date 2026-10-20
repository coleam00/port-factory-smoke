# Mission

**Derived from:** docs/prd.md
**Last reconciled with it:** 2026-10-20

## What Snippet Search is

Snippet Search is a tiny HTTP service that stores short text snippets and finds them by keyword. It exists to prove the AI Software Factory end to end, so it stays small.

It assumes one process, one SQLite database (path from `APP_DATABASE`) and no authentication.

## Who it is for

- a developer testing that the factory can take a PRD to merged, verified code

Snippet Search is not a search engine, a notes app, or a knowledge base.

## Core capabilities (in scope)

**Service**
- `GET /health` and `GET /build-id`
- unit tests and a GitHub Actions CI workflow (job `tests`)

**Snippets**
- store a snippet (title + body) with `POST /snippets`
- keyword search with `GET /search?q=` (every word must match, case-insensitive, newest first)

## Out of scope -- the factory must never build this

**People**
- accounts, sign-in, API keys or any authentication
- more than one user or tenant

**Search**
- fuzzy, semantic, vector or ranked relevance search
- pagination, filters or sorting options

**Content**
- editing or deleting snippets
- tags, folders or attachments

**Platform**
- any third-party package, web UI, or network call to another service

## Hard invariants -- not tunable by any issue

1. **Standard library only.** The runtime check runs the app with a plain interpreter.
2. **Every write is persisted before it is acknowledged.** A snippet that returned 201 is still searchable after a restart.
3. **The factory cannot modify governance files.** `MISSION.md`, `FACTORY_RULES.md` and the conventions file are the constitution. A PR touching any of them is an automatic reject.
4. **The factory cannot modify its own judge.** `harness/` and `.factory/` define what "working" means here. Adding an assertion is always welcome; removing or loosening one is a human decision, always.

## Allowed evolutions

- internal structure of the `app/` package and its tests

## Definition of done

**Gate 1 -- static checks and tests pass.** `python -m compileall -q app tests` and `python -m unittest discover -s tests`, and the `tests` CI job is green on the PR.

**Gate 2 -- the API matches docs/prd.md exactly** (paths, status codes, JSON shapes).

**Gate 3 -- the end-to-end path passes as a real user.**

1. start the app on a fresh database
2. `GET /health` answers 200
3. add two snippets, search a word only one contains
4. exactly that snippet comes back

## Open questions -- decisions nobody has made yet

These are undecided, not forbidden. The factory may propose an answer to any of them, build against it, and record what it assumed.

- **Q1** Maximum snippet length, if any.

## Decisions

- 2026-10-20 **Stack** Python 3.12 standard library only.

## What the factory does NOT own -- permanently human

- whether this smoke test proved what Cole needed it to prove
