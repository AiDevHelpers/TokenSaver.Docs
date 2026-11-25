# gotcha-db seed

Draft schemas + seed data for the Gotcha System (see `../nosql.md`). This directory is
the future `gotcha-db` repo's initial content — move it there when the repo is created.

Contents: 4 JSON Schemas (`metadata/schema/`), 15 gotchas extracted from
`mcp/docs/pitfalls.md`, 4 snippet templates, 2 patterns, 2 error mappings. Run
`python3 validate.py` (requires `jsonschema`) — it checks schema conformance, id↔path
consistency, dangling refs in every direction, regex syntax, tpl-variable declarations,
and pattern-step ↔ skeleton `TODO(gotcha:...)` marker consistency. It is the executable
spec for `gotcha validate` (plan Phase 1, step 1).

## Patterns (the scaffolding layer)

`patterns/csharp/net/fetch-parse-bind.json` is the worked example for the plan's
scaffolding workflow ("build a function to parse weather data and update the MAUI
page"): 3 components (service skeleton, composed viewmodel sub-pattern via `uses`,
binding-only page), placeholders `fetch`/`parse`/`map`/`load`, each expandable into a
starting snippet + gotchas. Anti-duplication rules that validation enforces: patterns
contain no literal code (snippet ids only), sub-patterns compose by id, and skeleton
TODO markers must exactly match declared steps.

## What converting real pitfalls taught us (changes vs. plan §3 draft)

1. **`kind` field added** (`code-pattern | environment | build | runtime | config`).
   Most real pitfalls (10 of 15) are NOT source-detectable patterns — they're
   environment/build issues (SCM vs. interactive, http.sys URL ACLs, MSBuild races).
   `bad_pattern`/`good_pattern`/`detection` are therefore **optional**.
2. **`diagnosis` field added** — for environment gotchas the "how to confirm this is
   the cause" step (netsh commands, Get-WinEvent) is as valuable as the fix and needs
   its own field, not a paragraph buried in `explanation`.
3. **`symptoms` array added** — matches how developers search ("no UAC appeared",
   "503 from health check"), distinct from machine-matchable `error_signatures`.
4. **`platforms/` top-level shard** added alongside `languages/` — Windows
   service/installer gotchas have no language.
5. **`id` = shard path** works well and is mechanically checkable.

## Not yet extracted

Project-specific pitfalls (TreatWarningsAsErrors env var, $PSScriptRoot conventions,
SimpleModelServer restart workaround) belong in each repo's `.gotcha/` overrides, not the
global DB — that's the first real test case for the override mechanism.
