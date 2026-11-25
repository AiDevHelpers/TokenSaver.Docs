# Contributing to gotcha-db

Rules the validator enforces (`python3 validate.py`, runs in CI on every PR):

## Sharding

One record per file. A record's `id` **is** its repo-relative path without `.json` —
if you move a file, update its `id`. Layout:

```
languages/<lang>/gotchas/<topic>/<name>.json
languages/<lang>/errors/<name>.json
platforms/<platform>/gotchas/<topic>/<name>.json
dependencies/<ecosystem>/<package>/<major>/<name>.json
snippets/<lang>/<name>.tpl + <name>.json   (sidecar declares every {{variable}})
patterns/<lang>/<domain>/<name>.json
migrations/<lang>/<name>.json
metadata/schema/*.schema.json
```

## Record conventions

- Schemas live in `metadata/schema/`; every record carries `schema_version`.
- Gotchas: pick the right `kind` (`code-pattern | environment | build | runtime |
  config`). `bad_pattern`/`detection` only apply to source-detectable gotchas; for
  environment/build gotchas put the "how to confirm" steps in `diagnosis` and what the
  developer observes in `symptoms`. Always cite `source`.
- Snippets are the **only** place code lives. Patterns and gotchas reference snippet
  ids; never inline code blocks in a pattern.
- Patterns: `intent_tags` should include synonyms a caller might actually say
  ("weather", "display data", not just "http"). Compose shared shapes via `uses`
  instead of repeating components. Every step's `placeholder` must have a matching
  `TODO(gotcha:<placeholder>)` marker in the referenced skeleton, and vice versa.
- Cross-link liberally (`related`, per-step `gotchas`) — dangling refs fail CI, so
  links are always trustworthy.

## Project-specific entries

Entries that only apply to one project (its env vars, conventions, workarounds) belong
in that project's `.gotcha/` overrides, not this global DB.
