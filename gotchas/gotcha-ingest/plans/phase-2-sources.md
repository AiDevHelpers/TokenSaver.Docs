# Phase 2 — Hand-authored source modules

Goal: grow gotcha-db via curated modules (no scraping yet). Read
`hints/source-module.md` first.

## Steps

1. **Test harness first**: `tests/conftest.py` with a fixture that copies a gotcha-db
   checkout (path from env var `GOTCHA_DB` or `../gotcha-db`) into `tmp_path`, and
   `tests/test_sources.py` that, for every discoverable source module, calls
   `collect()` and asserts `write_batch(tmp_db, records)` succeeds. This single
   parametrized test covers all future modules automatically.
2. `sources/python/gotchas/asyncio_pitfalls.py` — forgotten await, blocking call in
   event loop, `asyncio.run` inside running loop.
3. `sources/python/gotchas/stdlib_pitfalls.py` — mutable default args, `is` vs `==`.
4. `sources/node/gotchas/express_migration.py` — Express 4→5 removed/renamed APIs,
   ids under `dependencies/node/express/<major>/`.
5. `sources/csharp/gotchas/dotnet_pitfalls.py` — HttpClient socket exhaustion, EF
   Core tracking; ids under `dependencies/dotnet/<package>/<major>/`.
6. `sources/python/patterns/` + snippets — `fetch-parse-store` pattern (mirror the
   csharp fetch-parse-bind structure; snippets must ship in the same batch).

## Acceptance

- `pytest` green; `gotcha-ingest run <lang> gotchas --db <checkout>` writes and
  validates for each new module.
- Coordinate with gotcha-db `plans/phase-2-coverage.md` — same backlog, this repo is
  the preferred way to author it.
