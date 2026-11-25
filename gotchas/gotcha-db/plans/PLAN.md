# gotcha-db plan (index)

Data-only repo: sharded JSON records. No application code except `validate.py`.
Master design: `mcp/TokenSaver/plans/nosql.md`. This repo's job: correct, validated,
well-linked records.

**Lazy loading rule:** read this file, then ONLY the phase file you're working on.
Read a hint file only when its trigger line matches your task. Do not read other
phases for context — each phase file is self-contained.

| Phase | File | Status |
|---|---|---|
| 1. Foundation (schemas, seed, CI) | `phase-1-foundation.md` | DONE |
| 2. Coverage growth | `phase-2-coverage.md` | ready |
| 3. Test-vector growth | `phase-3-test-vectors.md` | ready, do alongside 2 |
| 4. Contribution security | not yet written — see `mcp/docs/plans/gotcha-system.md` OPEN WORKSTREAM | BLOCKS public contrib |

Hints:

- `hints/authoring.md` — trigger: writing or editing ANY record file.

Hard rules (apply always):

1. Every change must pass `python3 validate.py` before commit.
2. One record per file; `id` == repo-relative path without extension.
3. Snippets are the only place code lives. Never inline code in patterns/gotchas.
4. Never edit `metadata/schema/*.schema.json` casually — schema changes need a
   matching change to BOTH validators (validate.py here, Gotcha.Core in gotcha-mcp)
   plus new test vectors.
