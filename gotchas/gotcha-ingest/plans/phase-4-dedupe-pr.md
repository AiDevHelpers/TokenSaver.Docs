# Phase 4 — Dedupe + PR automation

Only start when Phase 3 scrapers produce real volume.

## Dedupe (pre-write check in writer.py)

- Exact: same `id` already exists with different content → update vs skip decision
  via `--on-conflict {skip,update,fail}` CLI flag (default fail).
- Fuzzy: before adding a NEW gotcha, compare `title` + `bad_pattern` against existing
  records for the same language/dependency using difflib ratio > 0.85 → report as
  probable duplicate, require `--force` to write. No embeddings — difflib is enough
  at this scale.

## PR automation

- `gotcha-ingest pr --db <checkout>`: git checkout -b `ingest/<date>-<source>`,
  commit written files, push, open PR via `gh pr create` with a body listing record
  ids + sources. Requires `gh` authenticated; fail with clear message otherwise.
- Never push to main. Never amend existing branches.
