# gotcha-ingest plan (index)

Python repo that builds gotcha-db records. Master design:
`mcp/TokenSaver/plans/nosql.md` §4.3.

**Lazy loading rule:** read this file, then ONLY the active phase file. Read a hint
file only when its trigger matches. Phase files are self-contained.

| Phase | File | Status |
|---|---|---|
| 1. Core (records/writer/cli) | `phase-1-core.md` | DONE |
| 2. Hand-authored source modules | `phase-2-sources.md` | ready |
| 3. Doc scrapers | `phase-3-scrapers.md` | after 2 |
| 4. Dedupe + PR automation | `phase-4-dedupe-pr.md` | after 3 |

Hints:

- `hints/source-module.md` — trigger: creating any new source module.
- `hints/scraping.md` — trigger: any code that fetches remote docs.

Hard rules (apply always):

1. Source modules NEVER construct file paths — return records; `core/writer.py`
   owns placement and runs gotcha-db's `validate.py` (batch rolls back on failure).
2. Every generated record sets `source` to the URL/doc it came from.
3. Output goes to a gotcha-db checkout as a PR, never a direct push to main.
4. Run `pytest` before commit; new source modules need a test asserting their
   records pass a real `write_batch` against a temp copy of gotcha-db.
