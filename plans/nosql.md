# Gotcha System — Master Plan

*Version: July 2026 (rev 2 — restructured into phased plan)*

> **Execution plans live in the repos.** This document is the design record
> (decisions, data model, rationale). To do work, open the target repo's
> `plans/PLAN.md` — `gotcha-db/plans/`, `gotcha-ingest/plans/`,
> `gotcha-mcp/plans/` — which are broken into lazy-load phase files with hint
> docs sized for a low-thinking executor. Read only the active phase + matching
> hints, not this whole document.

## 1. Goal

A local-first, version-aware knowledge base of coding pitfalls ("gotchas"), fix
snippets, and **code patterns**, served to AI clients through a standalone MCP server.
It answers two questions:

1. *Given this language, dependency set, and runtime, what mistakes apply and what does
   the correct code look like here?* (gotcha lookup)
2. *"I need to build a function that parses weather data and updates the MAUI page" —
   what's the best common shape for that?* (pattern scaffolding: a skeleton frame with
   helper functions sketched out and named placeholders for each step; each placeholder
   can then be expanded into a starting-point snippet plus its relevant gotchas)

Non-goals (for now): community submissions, multi-user trust scoring, hosted services.
See §8 Deferred.

## 2. Decisions

| Question | Decision | Rationale |
|---|---|---|
| Standalone vs. inside TokenSaver.MCP | **Standalone `gotcha-mcp` server** | Independent release cadence; DB updates shouldn't require TokenSaver releases. Reuses TokenSaver patterns (health contract, NB.GV versioning). |
| Audience | **Local-first, contribution-enabled** (revised 2026-07-07; was solo-only) | MCP machines get a write path: draft records are validated and staged locally (`.gotcha/drafts/`), usable immediately via a load-time overlay, and upstreamed as PRs against gotcha-db. Human PR review replaces the merge bot; trust scoring stays deferred. |
| Validation | **Same rules, two runtimes** | The JSON Schemas in gotcha-db are the single contract. `validate.py` gates gotcha-db CI; `Gotcha.Core` implements identical checks in C# for the MCP write path. A shared test-vector set (valid + invalid records in gotcha-db) keeps the two implementations honest. |
| Storage | **Sharded JSON files in a git repo (`gotcha-db`), compiled to a single snapshot** | Git is the backup, GC, release, and provenance mechanism — no bespoke ops tooling needed. |
| Three-repo split | **`gotcha-ingest` (Python) → `gotcha-db` (JSON) → `gotcha-mcp` (C#)** | Ingestion is scrape/parse-heavy — Python's strength; serving matches TokenSaver's C# patterns. The two never share code: the JSON schemas are the contract. |
| Ingestion language | **Python** | Scraping/parsing ecosystem, jsonschema tooling already in use, iterate-heavy work. |
| Snapshot format | **zstd-compressed JSON pack, loaded into in-memory indexes** | Benchmarked 2026-07-07 (`gotcha-ingest/tests/bench_snapshot.py`): pack is 2.7× smaller than SQLite and lookups are 100–1000× faster once loaded (0.2µs vs 38µs by id; 0.1µs vs 0.6ms filtered). Cold load is 34ms @5k records, ~1s @50k — paid once per start/reload in a long-running server; hot reload builds new indexes on a background thread and swaps atomically. Revisit only if the DB approaches ~500k records. |
| Snippets | **Templates with style/dependency variables, not static code** | One snippet serves multiple projects; resolution order in §5.3. |
| `gotcha_check` input | **Unified diff + dependency manifest** | Cheapest for MCP clients; fits the pre-commit/PR-review use case. Workspace-path mode added later for CI. |
| Repo placement | **`gotcha-mcp` becomes a third submodule of the `mcp` orchestration repo** | Matches the SimpleModelServer/TokenSaver pattern; `gotcha-db` is a submodule inside `gotcha-mcp` (`data/`). |

Per repo policy: every MCP tool this server exposes ships with a contract doc and
automated tests **in the same change** — this is the public-facing surface.

## 3. Data Model (the core artifact)

Everything else in this plan exists to produce, validate, or serve these three record
types. Schemas are versioned via a `schema_version` field on every record.

### 3.1 Gotcha record

One JSON file per gotcha.

```json
{
  "schema_version": 1,
  "id": "python/deps/pydantic/v1/dict-vs-model-dump",
  "title": "Pydantic v1 has no model_dump()",
  "language": "python",
  "applies_to": {
    "dependency": "pydantic",
    "version_range": ">=1.0 <2.0"
  },
  "bad_pattern": "model.model_dump()",
  "good_pattern": "model.dict()",
  "detection": {
    "kind": "regex",
    "pattern": "\\.model_dump\\("
  },
  "error_signatures": ["AttributeError: .* has no attribute 'model_dump'"],
  "fix_snippet": "python/pydantic_v1_dump",
  "severity": "error",
  "explanation": "model_dump() was introduced in pydantic v2; on v1 use .dict().",
  "source": "https://docs.pydantic.dev/latest/migration/"
}
```

Notes:
- `id` is the shard path (see §4), so file location and identity never diverge.
- `applies_to` may target a language version, dependency range, or runtime instead.
- `detection.kind` starts with `regex` only; `ast`/`semantic` are schema-compatible
  later additions.
- **Validated against real data** — schemas and 15 seed records extracted from
  `mcp/docs/pitfalls.md` live in `gotcha-db/` at the `mcp` repo root (the future
  gotcha-db repo). Key finding: most real
  pitfalls are environment/build gotchas, not source patterns, so the schema gained a
  `kind` field plus `symptoms`/`diagnosis`, and `bad_pattern`/`detection` are optional.
  See that directory's README for details.

### 3.2 Snippet template

One `.tpl` file plus a sidecar `.json` declaring its variables.

```
# python/pydantic_v1_dump.tpl
{{var_style:data}} = {{model}}.dict()
```

Variables resolve in this order (first hit wins):
project `.gotcha/styles.json` → user config → EditorConfig → language defaults →
global defaults.

### 3.3 Error mapping

Maps an observed error string/signature to one or more gotcha ids. One file per mapping.

```json
{
  "schema_version": 1,
  "match": "AttributeError: .* has no attribute 'model_dump'",
  "language": "python",
  "gotchas": ["python/deps/pydantic/v1/dict-vs-model-dump"]
}
```

### 3.4 Pattern record

One JSON file per pattern. A pattern is the *shape* of a solution — components, helper
functions, and ordered steps — not the code itself.

```json
{
  "schema_version": 1,
  "id": "patterns/csharp/net/fetch-parse-bind",
  "title": "Fetch external data, parse it, update the UI",
  "language": "csharp",
  "intent_tags": ["http", "fetch", "parse", "json", "update ui", "maui", "api client"],
  "applies_to": { "dependency": "maui", "version_range": ">=8.0" },
  "summary": "Typed service does fetch+parse; viewmodel owns state; page binds. Keeps parsing testable and off the UI thread.",
  "components": [
    {
      "role": "service",
      "name_hint": "{{domain}}Service",
      "description": "Typed HttpClient service: fetch, deserialize, map to domain model.",
      "skeleton": "snippets/csharp/typed_httpclient_service",
      "steps": [
        {
          "placeholder": "fetch",
          "description": "GET the endpoint with cancellation + timeout",
          "starting_point": "snippets/csharp/httpclient_get_json",
          "gotchas": ["languages/csharp/gotchas/json/jsonc-strict-parse"]
        },
        { "placeholder": "map", "description": "DTO → domain model mapping" }
      ]
    },
    {
      "role": "viewmodel",
      "uses": "patterns/csharp/mvvm/observable-viewmodel"
    }
  ],
  "gotchas": ["languages/csharp/gotchas/nullability/null-forgiving-habit"],
  "related": []
}
```

**Interlinking rules (the anti-duplication design):**

- A pattern contains **no literal code** — snippets are the single source of code.
  `skeleton` and `starting_point` are snippet ids; the same snippet serves many
  patterns.
- `uses` composes sub-patterns by id, so cross-cutting shapes (observable viewmodel,
  retry wrapper, typed client) are authored once and referenced everywhere.
- Gotchas attach at two levels: pattern-wide and per-placeholder. The validator rejects
  dangling refs in either direction, same as today.
- Rendered skeletons mark each step with a stable comment marker, e.g.
  `// TODO(gotcha:fetch): GET the endpoint with cancellation + timeout` — the marker
  name is the `placeholder` key the client passes back to `gotcha_expand`.

Workflow the tools support:

```
AI: gotcha_scaffold("parse weather data and update the MAUI page", deps)
 →  matched pattern + rendered skeleton (helpers stubbed, TODO(gotcha:...) markers)
AI: gotcha_expand("patterns/csharp/net/fetch-parse-bind", "fetch", context)
 →  rendered starting snippet + gotchas for that step
```

## 4. Repositories & Layout

### 4.1 `gotcha-db` (data)

```
gotcha-db/
  languages/<lang>/gotchas/<topic>/<name>.json
  languages/<lang>/errors/<name>.json
  dependencies/<ecosystem>/<package>/<major>/<name>.json
  snippets/<lang>/<name>.tpl + <name>.json
  patterns/<lang>/<domain>/<name>.json
  migrations/<lang>/<name>.json
  metadata/schema/*.schema.json        ← JSON Schema for each record type
```

Sharding rule: one record per file. Prevents merge conflicts, keeps diffs reviewable.

### 4.2 `gotcha-mcp` (code)

```
gotcha-mcp/
  src/Gotcha.Mcp/          ← MCP server (mirror TokenSaver.MCP host layout)
  src/Gotcha.Core/         ← compiler, validator, scanners, template renderer
  src/Gotcha.Cli/          ← `gotcha` CLI
  data/                    ← git submodule → gotcha-db
  docs/                    ← contract docs per MCP tool
```

### 4.3 `gotcha-ingest` (builders — Python)

Pulls docs (changelogs, migration guides, pitfall docs) and writes records into a
gotcha-db checkout. Sources are sharded like the DB: by language, then record kind —
one module per (language, kind, topic), each implementing `collect() -> list[Record]`.

```
gotcha-ingest/
  src/gotcha_ingest/
    core/records.py      dataclasses mirroring the schemas
    core/writer.py       only code that places files; runs gotcha-db validate.py,
                         rolls back the whole batch on failure
    sources/<lang>/<kind>/<topic>.py   e.g. sources/python/gotchas/pydantic_migration.py
    cli.py               gotcha-ingest run <language> <kind> --db <checkout>
  tests/
```

Generated records land as PRs against gotcha-db (human diff review), never direct
pushes. Reference example: `sources/python/gotchas/pydantic_migration.py`.

### 4.4 Project-local overrides (`.gotcha/`)

```
.gotcha/
  gotchas.json    styles.json    deps.json    overrides.json    snippets/
  drafts/         ← contribution staging: records authored on this machine, same
                    sharded layout as gotcha-db, validated on write
```

Local entries shadow global ones by `id`. Created by `gotcha bootstrap`.

Load order: snapshot → `.gotcha/` overrides → `.gotcha/drafts/` overlay. Drafts are
usable the moment they validate; `gotcha contribute` turns them into a PR against
gotcha-db (`gh` CLI when available, exportable bundle otherwise) and removes them
locally once the PR merges and the record arrives via a DB update.

## 5. Phase 1 — MVP

Build order. Each step is usable on its own; stop-and-evaluate points between steps.

1. **Schemas + validator** — JSON Schema for the four record types (gotcha, snippet,
   error mapping, pattern);
   `gotcha validate` checks schema, template syntax, dangling snippet/gotcha refs,
   version-range syntax. Seed the DB with ~20 real gotchas (pull from
   TokenSaver/mcp `docs/pitfalls.md` — C#, PowerShell, WiX entries already exist) and
   2–3 hand-authored patterns with their snippets, to prove the interlinking rules.
2. **Compiler + snapshot** — `gotcha snapshot` merges shards + `.gotcha/` overrides
   into one zstd-compressed JSON pack, loaded fully into in-memory indexes at server
   start (benchmarked decision — see §2). MCP server and CI consume only the
   snapshot; only dev machines compile.
3. **Dependency scanner** — parse `package.json`/lockfile, `pyproject.toml`,
   `Cargo.toml`, `.csproj`, `go.mod` → normalized `{ecosystem, package, version}` list.
   Other ecosystems later.
4. **Snippet renderer** — template + variable resolution chain (§3.2).
5. **MCP server with 5 tools** (each with contract doc + tests):
   - `gotcha_check(diff, deps)` → applicable gotchas + rendered fixes
   - `gotcha_error(error_text)` → matching gotchas + fixes
   - `gotcha_snippet(id, context)` → rendered template
   - `gotcha_scaffold(intent, deps)` → matched pattern + rendered skeleton with
     `TODO(gotcha:...)` placeholder markers. Phase 1 matching is `intent_tags`
     keyword scoring only — good enough because the caller is an AI that can rephrase;
     semantic matching is deferred (§8).
   - `gotcha_expand(pattern_id, placeholder, context)` → starting-point snippet +
     gotchas for that step
   - `gotcha_draft(record_json)` → validate against schemas + ref checks (C#
     validator in Gotcha.Core), stage into `.gotcha/drafts/`, immediately loadable.
     This is the write path — the AI that just hit an undocumented pitfall records
     it on the spot.
6. **`gotcha bootstrap`** — scan project languages + dependencies, write `.gotcha/`,
   compile local snapshot.

Exit criteria: running `gotcha_check` against TokenSaver/SimpleModelServer surfaces at least
one real, previously documented pitfall with a correct rendered fix.

## 6. Phase 2 — Depth

Only after Phase 1 is in daily use.

- **Runtime detection** — OS, container/WSL, .NET TFM, venv, Node version; gotchas may
  add `applies_to.runtime`.
- **Dependency diff / migration engine** — given `pydantic 1.x → 2.x`, emit the
  migration gotcha set; `gotcha_migration` MCP tool; migration records in the DB.
- **CI integration** — `gotcha check` in CI consuming a pinned snapshot (never
  bootstraps); exit codes for merge blocking; optional PR comment output.
- **Hot reload** — MCP server watches the snapshot file and `.gotcha/drafts/` and
  reloads without restart (background rebuild, atomic index swap).
- **`gotcha contribute`** — bundle validated drafts into a PR against gotcha-db;
  clean up local drafts when the upstream record lands.
- **Query CLI** — `gotcha query <lang|deps|errors|migrations> <term>` (substring/fuzzy
  only; no semantic search yet).
- **DB releases** — tag `gotcha-db` (e.g. `v2026.07`), attach compiled snapshot +
  changelog as release artifacts. Git handles backup/rollback.

## 7. Phase 3 — Ecosystem (speculative)

- Style engine beyond snippet variables (project policy enforcement, `gotcha_policies`
  tool).
- VS Code extension surfacing gotchas inline.
- Autoscraper ingestion of changelogs/release notes into candidate gotchas (needs a
  concrete design — currently hand-waved; treat as research spike first).
- Plugin system for third-party language/ecosystem packs.

## 8. Deferred (out of scope until multi-user demand exists)

Merge bot and trust scoring (human PR review covers contribution quality for now),
hosted submission API (PRs are the submission API), provenance chain beyond git
history, signed releases/encryption, metrics dashboard, semantic search/embeddings,
sandbox mode, documentation generator, bespoke backup/GC tooling. Design constraint
kept: record schemas include `source` and `schema_version` so provenance and trust
fields can be added without a breaking migration. Revisit the merge bot when PR
review volume actually hurts.

## 9. Open Questions

- Detection engine: how far can regex `bad_pattern` matching go before false positives
  force AST-based detection (per-language parsers = big cost)?
- Pattern matching quality: how far do `intent_tags` + keyword scoring get before
  wrong-pattern matches erode trust? Measure against a set of real intents before
  investing in embeddings.
- Skeleton assembly for `uses` composition: inline the sub-pattern's skeleton into one
  rendered output, or return component skeletons separately? Prototype both in step 5.
- Versioning/range syntax: adopt semver ranges everywhere, or per-ecosystem native
  ranges (PEP 440, NuGet)? Leaning: normalize to semver at scan time, record native
  string in `source_range`.

Resolved 2026-07-07 (moved to §2): `gotcha_check` input = diff + dependency manifest;
`gotcha-mcp` = third submodule of the `mcp` orchestration repo.
