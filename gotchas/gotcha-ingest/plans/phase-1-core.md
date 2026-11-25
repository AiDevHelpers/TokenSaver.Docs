# Phase 1 — Core (DONE 2026-07-07)

What exists; do not redo. Reference only.

- `core/records.py` — dataclasses (Gotcha, Snippet, Pattern, ErrorMapping) mirroring
  gotcha-db schemas. `to_json()` strips empty fields. Schemas remain source of truth.
- `core/writer.py` — `write_batch(db_root, records)`: derives path from `rec.id`,
  writes JSON (+ `.tpl` for snippets), runs gotcha-db's `validate.py`, restores all
  touched files on any failure.
- `cli.py` — `gotcha-ingest run <language> <kind> --db <checkout> [--source name]`;
  discovers modules under `sources/<language>/<kind>/`, calls `collect()`.
- Reference source module: `sources/python/gotchas/pydantic_migration.py` (ran for
  real; produced the 2 pydantic records now in gotcha-db).
- `tests/bench_snapshot.py` — snapshot format benchmark (decision record; keep).

Gap carried into Phase 2: no pytest suite yet — first new module adds the test
harness (see phase-2-sources.md step 1).
