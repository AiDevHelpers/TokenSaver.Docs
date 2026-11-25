# gotcha-ingest

Python tooling that pulls documentation (changelogs, migration guides, pitfall docs,
release notes) and builds sharded record files for the
[gotcha-db](../gotcha-db/) data repo.

Three-repo split:

| Repo | Language | Role |
|---|---|---|
| `gotcha-ingest` (this) | Python | Pull docs → generate/normalize records → write into gotcha-db checkout |
| `gotcha-db` | JSON | Data only. Schemas + `validate.py` CI. The contract between the other two. |
| `gotcha-mcp` | C# | Compile snapshot, serve MCP tools. Never imports ingest code — reads data only. |

## Layout

Sources are sharded the same way the DB is: **by language, then by record kind**.
Each source module produces records for exactly one (language, kind) pair, so
contributions and reruns stay independent.

```
src/gotcha_ingest/
  core/
    records.py     dataclasses mirroring gotcha-db schemas (single source: the schemas)
    writer.py      id<->path enforcement, sharded file output into a gotcha-db checkout
    validate.py    thin wrapper that runs gotcha-db's own validate.py after a write
  sources/
    csharp/    gotchas/  snippets/  patterns/
    python/    gotchas/  snippets/  patterns/
    powershell/ gotchas/  snippets/  patterns/
    node/      gotchas/  snippets/  patterns/
  cli.py           `gotcha-ingest run <language> <kind> [--source ...] --db <path>`
```

A source module implements one function: `collect() -> list[Record]`. The writer owns
all file placement and formatting, so source modules never touch paths — this is what
keeps the sharding rules enforced in one place.

## Rules

- Output must pass `gotcha-db/validate.py` — the writer runs it automatically; a
  failing batch writes nothing.
- Scraped/derived records must set `source` to the URL or doc they came from.
- Generated records land as a PR against gotcha-db, never a direct push, so every
  ingested batch gets a human diff review.
