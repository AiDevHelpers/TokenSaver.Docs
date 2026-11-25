# Phase 2 — Snapshot compiler + loader

Goal: `gotcha snapshot` compiles the DB into one zstd-JSON pack; Gotcha.Core loads it
into immutable in-memory indexes. Format decision + benchmark:
`gotcha-ingest/tests/bench_snapshot.py` (pack beat SQLite; do not relitigate).

Read `hints/snapshot-loading.md` first.

## Steps

1. NuGet: `ZstdSharp.Port`.
2. `SnapshotCompiler`: walk dbRoot shards → validate (Phase 1 code) → merge
   `.gotcha/` overrides by id (project > global) → serialize
   `{"format_version":1,"created":...,"records":[...]}` → zstd level 9 →
   `gotcha-snapshot.bin`. Refuse to compile if validation fails.
3. `SnapshotStore` (the load side):
   - `Load(path)` → decompress → deserialize → build indexes → return immutable
     `Snapshot` object: `ById` (Dictionary), `ByLanguageDependency` (lookup),
     `ErrorSignatures` (list of compiled Regex + gotcha id), `PatternsByTag`
     (tag → pattern ids).
   - Overlay: `Snapshot.With(overlayRecords)` returns a NEW snapshot with drafts/
     overrides merged (used by Phase 5 drafts; design the immutability now).
4. `gotcha snapshot <db-path> [-o file]` CLI verb.
5. Tests: round-trip (compile → load → every record retrievable by id, equal to
   source JSON); override shadowing (project record with same id wins); corrupt/
   truncated file → clean `SnapshotFormatException`, not a crash.

## Acceptance

- Round-trip test green on the real `data/` content.
- Compile of current DB < 1s; load < 100ms (assert loosely in a test, 10x margin).
