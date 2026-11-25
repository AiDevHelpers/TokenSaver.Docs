# Architecture Overview

This repo exposes workspace indexing, code search, context building, and Ollama calls as an MCP
server for Claude and other AI clients, plus a VS Code extension and per-agent context-formatting
adapters (`TokenSaver.AgentHelpers.*`).

## Project Dependency Graph

```text
TokenSaver.MCP → TokenSaver.CodeHelper → TokenSaver.ContextHelper
```

`TokenSaver.MCP` also depends on `TokenSaver.AgentHelpers.Core` and each `TokenSaver.AgentHelpers.*` adapter
(Anthropic, Qwen, DeepSeek, OpenSource) — see `src/Host/TokenSaver.MCP/TokenSaver.MCP.csproj`.

The `TokenSaver` stack's projects are arranged so that code-indexing logic lives in
`TokenSaver.CodeHelper`, while the core data schema (EF Core entities, `WorkspaceIndexContext`,
`WorkspaceIndexContextFactory`) lives in `TokenSaver.Database.Context`.

## TokenSaver Stack (net10.0)

**`TokenSaver.MCP`** is an ASP.NET MCP server (port 11436 by default via `TokenSaverConfig.ServerPort`) that exposes Ollama calls as MCP tools to Claude and other AI clients.

**`TokenSaverConfig`** (section name `"TokenSaver"`, env prefix `TOKENSAVER_`) configures:
- `OllamaUrl` — where to reach the SimpleModelServer router (default `http://localhost:11435`, see the separate rsperry79/SimpleModelServer repo)
- `OllamaModel` — model name used for router calls (default `"HelperModel"`)
- `ContextSizeLimit` — max tokens for context operations (default 120,000)
- `SimpleModelServerServiceInstalled` — when true, reads SimpleModelServer.config.json from ProgramData to auto-discover router host/port
- `AutoRegisterProviders` — reserved; nothing writes client configs at startup. Use `register_mcp_providers` / `POST /api/register-providers` (see `docs/Host-MCP/provider-config-reliability.md`)
- `ServerPort` — MCP server listen port (default 11436)
- `WorkspaceRoot` — workspace root for .tokensaver storage; empty at startup unless already known
  via config/env, resolved lazily when a session connects (MCP roots capability, falling back to
  the nearest .git/solution file from cwd) — see `WorkspaceRootSessionResolver`

### Unified Workspace Index

The old two-database pattern (`context.db` with `files`/`sections`/`summaries`/`folder_indices` tables, plus `code-index.db` with `file_manifest`/`symbols`/`references_` tables) has been replaced by a single normalized, EF-Core-backed SQLite index at `.tokensaver/index.db`. See `plans/TokenSaver.UnifiedIndex.plan.md`.

**Schema** (`WorkspaceIndexContext` in `TokenSaver.Database.Context`):
- `Folders` — one row per workspace directory, normalized (no JSON blobs); `FolderOverview` keyless entity backed by the `folder_overview` SQL view for aggregated file/symbol counts per folder
- `Files` — one row per indexed file; absorbs both the old `files`/`sections` metadata and the old `file_manifest` table
- `Symbols` — one row per function/type; uses the same stable-hash `Id` scheme as the old `CodeIndexService`
- `SymbolReferences` — reserved for cross-file reference edges (not yet populated by any parser)
- `RepoStaleness` — one row per git repo root under the workspace; tracks `HEAD` sha + dirty state for git-aware staleness detection

**Key services**:
- `WorkspaceIndexService` (in `TokenSaver.CodeHelper.Indexing`) — unified replacement for both `LocalContextService` and `CodeIndexService`. Handles indexing, symbol search, context building, and folder-index queries.
- `GitStalenessChecker` — detects which files changed since the last index run using git as the staleness source of truth; falls back to mtime comparison for non-git folders
- `SimpleModelServerCapacityClient` — queries the SimpleModelServer router's `GET /api/capacity` (separate rsperry79/SimpleModelServer repo) to size AI-summary concurrency from real machine hardware, preventing background indexing from starving interactive draft-pair generation
- `ContextCleanerService` (unchanged from before) — prompt-cleaning pipeline (dedup, log-stripping, semantic filtering, token budgeting)
- `GitignoreFilter` — controls which files are indexed (every non-excluded file gets a `File` row, not just `IndexedExtensions`)
- `WorkspaceIgnoreFilter` (in `TokenSaver.Config`) — the unified ignore decision used by all three indexing walkers. Composes `.gitignore`, `.tokensaver/.ignore-additional` (extra excludes), and `.tokensaver/.ignore-bypass` (force-include gitignored paths): `ignored = (gitignore ∨ additional) ∧ ¬bypass`. See `docs/Host-MCP/config-behavior-contract.md`.
- `BehaviorConfigService` (in `TokenSaver.Config`) — loads/merges `.tokensaver/config.json` (local) and `%ProgramData%\TokenSaver\config.json` (global), local-over-global per property, live-reloaded via `FileSystemWatcher`. Backs the `ManageConfig` MCP tool and the "add `.tokensaver/` to .gitignore?" pending prompt surfaced by `BuildConciseContext`.

**Threading model**: CPU-bound symbol parsing uses `Environment.ProcessorCount - 2` parallelism. AI-summary calls (file/folder descriptions via Ollama) are throttled through a `SemaphoreSlim` sized from `SimpleModelServerCapacity.MaxConcurrentSummaryRequests` — conservatively 1 without a capable GPU, up to 3 with ≥24GB VRAM. This keeps interactive requests responsive while background indexing runs.

**MCP tools exposed by `TokenSaver.MCP`**:
- `CleanAndChat` — context-cleans a prompt then calls the Ollama model
- `BuildConciseContext` — builds a token-efficient workspace summary into `.tokensaver/index.db` and returns it adapted for the calling AI
- `ContextHygiene` — inspects and reports on the `.tokensaver/` context cache
- `ContextDiag` — inspect pipeline state, fetch indexed file content or folder index JSON, manage `.gitignore` and context exclusions
- `CodeIndex` — symbol search, dependency graph queries, on-demand workspace re-scan, `table` (regenerates `docs/folder-index.md`)
- `EditFile` — apply or roll back file edits with automatic backup
- `ManagePlan` — create and execute step-by-step code task plans
- `RegisterMcpProviders` — on request, add the MCP server (with the endpoint token) to every installed AI client config
- `SetAgentPreference` — save per-agent workspace preferences to `.tokensaver/preferences.json`
- `ManageConfig` — read/update behavior config (`config.json`, local+global) and the `.ignore-additional`/`.ignore-bypass` override files; records the gitignore-preference answer. See `docs/Host-MCP/config-behavior-contract.md`.

## Ports and Boundaries

| Component | Port | Role |
| --- | --- | --- |
| TokenSaver.MCP | 11436 (config) | MCP server for AI clients, auto-detected from SimpleModelServer service config |

**Dependency**: TokenSaver.MCP points its `OllamaUrl` at the SimpleModelServer router (11435,
separate rsperry79/SimpleModelServer repo), which manages Ollama and all model loading. Model creation,
GPU detection, and lifecycle management live entirely in SimpleModelServer. The unified index
replaces both old SQLite caches with a single `index.db` per workspace, using WAL mode for
reader/writer concurrency and git-aware staleness for fast incremental updates.
