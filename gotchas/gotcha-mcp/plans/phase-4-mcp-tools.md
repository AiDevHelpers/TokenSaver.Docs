# Phase 4 — MCP server + 6 tools

Goal: Gotcha.Mcp serves the tool surface. Mirror TokenSaver.MCP's host layout,
health-contract pattern, and test style — do not invent new hosting patterns.
Read `hints/mcp-tool-safety.md` first. EVERY tool: contract doc in `docs/` + tests,
same change.

## Tools (build in this order — each uses the previous)

1. `gotcha_snippet(id, context?)` → render template with context vars. Simplest;
   proves host + snapshot wiring.
2. `gotcha_error(error_text)` → run compiled `ErrorSignatures` regexes over input,
   return matched gotchas (mapping order = confidence order). Cap input at 32KB.
3. `gotcha_check(diff, deps)` → parse unified diff ADDED lines only; run each
   applicable gotcha's `detection` regex (filter: language via file extension +
   `file_glob`, dependency via `deps` + `VersionRange.Satisfies`); return gotcha +
   rendered fix per hit with file/line.
4. `gotcha_scaffold(intent, deps)` → tokenize intent (lowercase, split non-alpha),
   score patterns by tag overlap (+1 exact tag token match, +0.5 tag substring),
   filter by deps when pattern has `applies_to`, return best pattern: summary +
   each component's rendered skeleton (or sub-pattern reference for `uses`) +
   step list. Return top-1 plus up-to-2 alternatives (id + title only).
5. `gotcha_expand(pattern_id, placeholder, context?)` → find step, render
   `starting_point` snippet, attach step + pattern gotchas.
6. `gotcha_draft(record_json)` → validate via RecordValidator (schema by id prefix,
   ref checks against current snapshot), write to `.gotcha/drafts/<id>.json`,
   trigger overlay reload. See safety hint — this tool writes to disk from
   AI-supplied input.

## Server

- Ports: pick config default that doesn't collide with 11434/11435/11436 → 11437.
- `/health` + `/health/ready` per TokenSaver's health contract pattern.
- Hot reload: FileSystemWatcher on snapshot + drafts dir → debounce 500ms → rebuild
  snapshot on background task → atomic swap (see hints/snapshot-loading.md).

## Acceptance

- Contract doc + tests per tool (in-process endpoint self-tests like
  TokenSaver.MCP.Tests).
- End-to-end test: scaffold "parse weather data and update the MAUI page" with a
  maui dep → returns `patterns/csharp/net/fetch-parse-bind`; expand `fetch` →
  returns the httpclient snippet + its gotchas.
