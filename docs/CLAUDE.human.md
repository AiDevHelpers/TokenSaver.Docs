# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`TokenSaver.MCP` is an ASP.NET Core MCP server (net10.0) that exposes workspace indexing, code
search, context building, file editing, and Ollama calls as MCP tools to Claude and other AI
clients. Ships with a VS Code extension (`TokenSaver.VsCodeExt`) and per-agent context-formatting
adapters (`TokenSaver.AgentHelpers.*`).

This is its own git repo, usually vendored as a submodule under the `mcp` orchestration repo. Work
here, not at the parent, when touching TokenSaver code.

## Environment

When working from a cloud/remote Claude session with the desktop device bridge connected (device
`dragonfire`), `mcp__remote-devices__Windows-MCP__PowerShell` (and the rest of the Windows-MCP
tool family — `Process`, `App`, `FileSystem`, etc.) runs commands directly on the user's Windows
machine. **Use it to actually run commands** instead of asking the user to run them and report back
— this repo has no .NET SDK in the cloud container, but the user's machine does. Load the tool via
`ToolSearch` if it's deferred (`select:mcp__remote-devices__Windows-MCP__PowerShell`).

Build/test/versioning and packaging guidance live in `.claude/rules/` (`commands.md`,
`packaging.md`) as path-scoped rules — they load automatically only when you touch the relevant
project, test, script, or installer files, so they stay out of context otherwise.

Subagent model default (haiku, retry once on sonnet if a result looks confused/wrong) lives in
global `~/.claude/CLAUDE.md` -- applies here too, no repo-local override needed.

## Dev Environment Startup

**Port allocation** (fixed by convention): Ollama 11434, SimpleModelServer 11435, TokenSaver.MCP 11436.

**Dev server startup**:
1. Run `.\scripts\run-dev-server.ps1` in a visible PowerShell terminal (reuse across stop/start, 
   never leave prod service as the thing under test).
2. Script checks if the port is in use: if yes and the process is `TokenSaver.MCP.exe` from 
   `C:\Program Files\TokenSaver` (prod service), it stops the service. If yes and it's something 
   else (stale dev instance), pass `-Force` to kill it.
3. Once the dev server is running, open IDE instances via the MCP `LaunchIde` tool 
   (`type: "VsCode" | "VisualStudio2026"`, `workspaceRoot: "F:\\mcp\\TokenSaver"`).

See `.claude/rules/commands.md` for detailed command reference.

## Architecture

Project dependency chain:

```
TokenSaver.MCP → TokenSaver.CodeHelper → TokenSaver.Library → TokenSaver.ContextHelper
```

`TokenSaver.MCP` also references `TokenSaver.AgentHelpers.Core` + every adapter (Anthropic, Qwen,
DeepSeek, OpenSource) and `TokenSaver.Database.Context`. Code-indexing logic lives in
`TokenSaver.CodeHelper`; the EF Core schema (`WorkspaceIndexContext`) lives in
`TokenSaver.Library.Data` / `TokenSaver.Database.Context`. `TokenSaver.Config` (Core, sits between
CodeHelper and Library) owns behavior config + the unified ignore filter — see below.

### Behavior config & ignore overrides (`TokenSaver.Config`)

`BehaviorConfigService` merges `.tokensaver/config.json` (local) with
`%ProgramData%\TokenSaver\config.json` (global) — **local wins per-property** — and live-reloads
both via `FileSystemWatcher`. `WorkspaceIgnoreFilter` is the single ignore decision used by all
three indexing walkers (`WorkspaceIndexService`, `FolderTreeManager`, `GitStalenessService`),
composing `.gitignore` + `.tokensaver/.ignore-additional` (extra excludes) +
`.tokensaver/.ignore-bypass` (force-include gitignored paths) + `context-exclusions.json`:
`ignored = (gitignore ∨ additional ∨ exclusions) ∧ ¬bypass`. The `ManageConfig` MCP tool edits all
of these; `BuildConciseContext` surfaces a one-time "add `.tokensaver/` to .gitignore?" prompt when
unanswered. Full contract: `docs/config-behavior-contract.md`.

**External dependency, no build coupling**: `TokenSaver.MCP` reaches Ollama *only* through the
SimpleModelServer router over HTTP (`OllamaUrl`, default `http://localhost:11435`, separate
[rsperry79/SimpleModelServer](https://github.com/rsperry79/SimpleModelServer) repo). That router owns the Ollama
process, model loading, and GPU detection — none of that lives here. Ports: Ollama 11434,
SimpleModelServer router 11435, TokenSaver.MCP 11436.

### Configuration

`TokenSaverConfig` — appsettings section `"TokenSaver"`, env prefix `TOKENSAVER_`. Key knobs:
`OllamaUrl`, `OllamaModel` (default `HelperModel`), `ContextSizeLimit` (default 120,000),
`ServerPort` (11436), `WorkspaceRoot` (auto-detected from nearest `.git`/solution),
`SimpleModelServerServiceInstalled` (reads `SimpleModelServer.config.json` from ProgramData to auto-discover the
router host/port), `AutoRegisterProviders`.

### Unified workspace index

A single EF-Core-backed SQLite index at `.tokensaver/index.db` (WAL mode) replaces the old
two-database `context.db` + `code-index.db` pattern. Tables: `Folders` (+ `folder_overview` SQL
view), `Files`, `Symbols`, `SymbolReferences` (reserved, not yet populated), `RepoStaleness`
(HEAD sha + dirty state for git-aware staleness). `WorkspaceIndexService`
(`TokenSaver.CodeHelper.Indexing`) is the unified entry point. `GitStalenessChecker` uses git as
staleness truth (mtime fallback for non-git folders).

**Threading**: CPU-bound symbol parsing runs at `ProcessorCount - 2`. AI-summary calls are
throttled by a `SemaphoreSlim` sized from `SimpleModelServerCapacityClient` (queries the router's
`GET /api/capacity`) — 1 concurrent without a capable GPU, up to 3 with ≥24GB VRAM — so background
indexing never starves interactive draft-pair generation.

### MCP tools

Tool classes live in `src/Host/TokenSaver.MCP/Tools/*.cs`, registered in `Program.cs`. Surface
includes `CleanAndChat`, `BuildConciseContext`, `ContextHygiene`, `ContextDiag`, `CodeIndex`,
`EditFile`, `ManagePlan`, `RegisterMcpProviders`, `SetAgentPreference`. **IDE & Debugging**:
`LaunchIde` / `QueryIDEStatus` / `StopIDE` (open/control IDEs), `GetDebugOutput` / `SearchDebugOutput` 
(capture process output), **`StartDebugger` / `StopDebugger`** (quick-start debugging with default 
config), `StartDebugSession` (advanced: custom debug configs), `SetBreakpoint` / `RemoveBreakpoint` / 
`ListBreakpoints` (manage breakpoints), `ExecuteStep` / `GetDebugState` (step through code and 
inspect state). **Test Execution**: **`RunTests`** (single command with optional overloads for 
specific test, namespace, project, or re-run failed), `GetLastTestResult` (retrieve cached results). 
`/health` and `/health/ready` follow `docs/tokensaver-mcp-health-contract.md`; 
token-economy tools follow `docs/token-economy-tools-contract.md`. These are public contracts — 
changes must update the contract doc + tests in the same change.

**Library contract rule**: Anything invoked *from outside a library* (i.e., called by a host or 
another library) must have:
  1. An interface/contract in `TokenSaver.Common.Core`
  2. A corresponding doc in `docs/` describing the public contract
  3. Unit tests in the library's test project covering the contract's public surface
  
This keeps cross-library coupling explicit, documented, and testable. Internal-only services 
(only used within their own library) don't need contracts or tests.

## Gotchas

- **Transport auto-detection** (`Program.cs` top): the server adds stdio transport only when
  `Console.IsInputRedirected` is true, *not* a Windows Service, and `TOKENSAVER_HTTP_ONLY != "1"`.
  Both the VS Code extension and the SCM launch with a redirected/absent stdin that would
  false-positive as stdio, read immediate EOF, and shut the server down — hence the explicit
  guards. The extension sets `TOKENSAVER_HTTP_ONLY=1`; the SCM is forced HTTP-only unconditionally.
  In stdio mode stdout is the protocol channel, so it's redirected to stderr.
- **Build output is redirected**: `Directory.Build.props` routes every .NET project's bin/obj into
  `build/staging/<ProjectName>/` (not per-project folders). `.esproj` is excluded. Don't look for
  `bin/obj` under project dirs.
- **WiX build race**: `TokenSaver.slnx` carries explicit `BuildDependency` ordering on
  `VsCodeExt.esproj` and `TokenSaver.Setup.wixproj` to prevent concurrent nested `dotnet publish`
  of `TokenSaver.MCP` into a shared obj folder (surfaces as MSB4018 missing `.deps.json` or CS0006
  missing metadata file). Preserve that ordering if editing the solution.
- A transitive `SQLitePCLRaw.lib.e_sqlite3` advisory (NU1903 / GHSA-2m69-gcr7-jv3q) is suppressed
  in `Directory.Build.props` — it's never loaded at runtime (we use `bundle_winsqlite3`). Remove
  the suppression once a patched version ships.

## Versioning

Nerdbank.GitVersioning derives all versions from `version.json` + git height. No manual per-release
bumps outside `version.json`. See `docs/versioning.md`.
