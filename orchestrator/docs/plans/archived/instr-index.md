# Plan: instruction maintenance + folder/file index (mcp repo)

## Context
Adapt the pasted VideoForensics plan to `F:\source\mcp`. Goal: a small, generated folder/file table
(metadata only: path, title, one-line summary) over folders, `docs/` and instruction files, cross-linked
to the code index and semantic index; kept in sync with the repo `CLAUDE.md`; every chat function (MCP
tool) tested; `instruction-placement` skill updated. Tests live in `TokenSaver/src/Host/TokenSaver.MCP.Tests`
(xUnit, `Subject_Condition_Expected`). Designed for two users: the maintenance loop (keeping indexes and
instructions true) and a chat session (planning, writing code, briefing subagents).

## Findings (Haiku Explore)
- `Folders`/`Files` tables already have a `Description` column plus the `folder_overview` view
  (`TokenSaver.Database.Context`). Reuse them; no parallel store.
- `ChunkExtractor.ChunkMarkdown` returns full section bodies; frontmatter parsing exists only as private
  `InstructionStoreService.ParseFrontmatter`. A metadata-only extractor is new.
- 69 tool methods / 20 tool classes; ~59 untested; no reflection test exists.
- `get_instruction` reads `TOKENSAVER_INSTRUCTIONS_DIR` or `%USERPROFILE%\.tokensaver\instructions\skills`,
  not the repo. Repo `TokenSaver/instructions/skills/` is the shipped default the installer copies.
- Existing watchers/staleness: `GitStalenessService`, `BehaviorConfigService` (FileSystemWatcher),
  `code_index scan` is incremental. `build_concise_context` runs every session start.
- Superproject remote has only `wip`; PRs go to `wip`.

## End-to-end design

### 0. Layers: read the globals, tailor to this repo
Effective instructions = globals + repo layer; repo overrides globals (user rule). Layers found:
- **Global source:** `C:\Users\rsper\claude_rules` (`CLAUDE.md`, `rules/`, `skills/`, `install.ps1`).
- **Global installed:** `~/.claude` (`CLAUDE.md`, `rules/`, `skills/` stubs that point to `get_instruction`).
- **Global skill bodies:** `%USERPROFILE%\.tokensaver\instructions\skills` (the live store); repo default
  at `TokenSaver/instructions/skills`.
- **Repo layer (new work):** `F:\source\mcp\CLAUDE.md` (pointer + top-level folder list), a new
  path-scoped rule `.claude/rules/instructions.md` (loads when touching `CLAUDE.md`, `.claude/**`, `docs/**`,
  `instructions/**`) holding the repo-specific procedure: where the table is, the sync/drift commands, test
  home (`TokenSaver.MCP.Tests`), submodule pairing, `wip` base. Same rule pair in `TokenSaver/.claude/rules`
  for its own scope. The global skill stays generic and defers to it ("repo rules override").
- **Table is scope-aware:** rows tagged `scope: global | repo`, so a session sees the effective set; global
  rows are read-only metadata (title, summary, source path) and are never edited from here. Reuse
  `InstructionSyncResolver` (already maps global CLAUDE.md into workspace instruction files).

### Checking the globals (read-only, new `instructions-check`)
Run at gate and on demand; reports, never edits globals. Checks:
1. Source `claude_rules` vs installed `~/.claude` (hash drift; says run `install.ps1`).
2. Every stub in `~/.claude/skills` names a `get_instruction` entry that exists in the store; each store
   entry has valid frontmatter (`name`, `description`) and name matches folder.
3. Store vs repo default hash drift (which side is newer, exact sync command).
4. Size targets from `instruction-placement` (global CLAUDE.md ~60 lines; repo CLAUDE.md < ~200).
5. Placement test 1: globals must not name a repo/product/path (heuristic grep for known repo names/paths).
6. One home per fact: flag identical headings or near-duplicate lines across global and repo layers.
7. Conflict hints: same-topic headings in global vs repo, listed for human review (not auto-resolved).
Implemented as a `code_index`-adjacent check inside `TokenSaver.MCP` (service + tests), surfaced via the
`build_concise_context` one-liner and `/health`; no new tool unless the contract requires one.

### A. Maintenance loop (keeping it true)
1. **Source of truth.** The index DB (`Folders`/`Files`, deterministic scan) is the source. The table is a
   generated view of it, never hand-edited. `CLAUDE.md` holds only a pointer and the top-level folder list.
2. **Metadata rule.** title = frontmatter `name` or first H1; summary = frontmatter `description`, else first
   non-empty line under the title, capped ~120 chars. Deterministic: no Ollama, so it works offline and
   tests are stable. Bodies are never stored in the table.
3. **Cross-links.** Each row has `code:<relpath>` (code index) and `sem:<relpath>#<heading>` (semantic
   index). If the semantic index has not run, the row shows `sem:pending`; the table never depends on
   Ollama being up.
4. **Refresh trigger.** Regenerate as the last step of `code_index scan` (already incremental and
   git-aware). No new watcher. Gate and `/health` run the sync check, so drift is caught even if a scan was missed.
5. **Drift checks (all in the gate).** (a) `CLAUDE.md` folder list vs table; (b) table vs fresh scan
   (stale); (c) instruction store drift: hash of repo default skills vs `%USERPROFILE%\.tokensaver` store,
   reporting which side is newer and the exact sync command.
6. **Contracts.** Any tool surface change updates the contract doc and tests in the same change (TokenSaver
   rule). To keep the surface small, add a `table` action to existing `code_index` instead of a new tool.
7. **Tests as maintenance.** The coverage test (reflection over `[McpServerTool]`) fails when a tool lacks a
   test, so new chat functions can't land untested.

### B. Chat session (planning, coding)
1. **Start.** `build_concise_context` (already run at session start) adds one line: table path, row count,
   and `STALE` plus the fix command when the check fails.
2. **Navigate.** Agent reads the table (cheap metadata), then `code_index find` or `semantic_grep` from the
   row's keys, then reads only the files the task needs. `docs/` and `archive/` bodies are read only on request.
3. **Plan.** `list_instructions` already gives name + description, so the plan step picks instructions by
   metadata and calls `get_instruction` only for those it needs. Table gets a "governing rule" column
   (matching `.claude/rules/*.md` `paths:` glob) so the agent knows which rule to read before editing a file.
4. **Code.** Test-first (`tdd`); `edit_file`; after edits, `code_index scan` refreshes the table. Adding or
   changing a tool requires its test (coverage test) and contract doc.
5. **Subagents.** Haiku briefs carry table keys and the governing rule, not file bodies; each brief demands
   the red run first.
6. **Failure handling.** Stale table, missing semantic index, or store drift each produce a one-line message
   with the command to run; none blocks reading or editing.

## Setup (before any edit)
- Superproject worktree: `git worktree add F:/mcp-worktrees/instr-index -b instr-index wip`.
- Submodule `TokenSaver`: own worktree, branch `instr-index` from pointer commit `a2d9e1c`. Leave the main
  checkout's uncommitted SemanticQuality WIP untouched.
- Push submodule branch first, then superproject; PRs to `wip`.
- Save this plan to `docs/plans/instr-index.md`; Sonnet read-only review (standing approval); fold findings in.
- Read `.claude/rules/build.md`, `pitfalls.md` and TokenSaver rules before editing.

## Units (test first; record each red run)
1. Metadata extractor (shared frontmatter parser). Tests: no body text leaks; cap length; H1/frontmatter fallback.
2. Table generator from `Folders`/`Files`; cross-link keys; governing-rule column; writes `docs/` table;
   hooked into end of `code_index scan` (new `table` action, contract doc updated).
3. Sync + drift checks (CLAUDE.md vs table, table vs scan); wired into gate and `/health`.
3b. Global/layer check (section "Checking the globals"): service + tests with temp-dir fixtures for
   source/installed/store layouts; read-only.
4. `build_concise_context` one-liner: table state + global-check result with fix commands.
4b. Repo layer: `.claude/rules/instructions.md` in `F:\source\mcp` (and TokenSaver); update repo `CLAUDE.md`
   pointer + folder list. Follow `instruction-placement` for placement and size.
5. Coverage test: 4a reflection test (red: ~59 fail); 4b one Haiku batch per untested tool class (Wsl,
   DevLoop, DebuggerControl, DebugOutput, IDELauncher, DebuggerAnalysis, AdaptiveContextLoader, Session,
   AutoWorkflow, Instruction, Help, LanguageHelper, AccuracyTest, CodeHelper, TestExecution, gaps in
   TokenEconomy/LocalModelHelper/SemanticIndex). External-process tools use fakes or assert the
   unavailable/error path. "Covered" = a test invokes the tool method by name.
6. Global skill text, generic (no repo names), in BOTH the repo default and the user-profile store: define
   "test" to include chat functions; metadata-only indexing; "if a repo keeps a folder/file table, keep its
   CLAUDE.md in sync; repo rules override"; point to the global check. Repo-specific detail lives only in
   unit 4b. Verify with `get_instruction`. Also update `claude_rules` source copy so install.ps1 does not
   revert it (confirm with user if edits there are wanted).
7. Gate, push, PR to `wip`, archive the plan.

## Verification
- `dotnet test` on `TokenSaver.MCP.Tests` (+ `TokenEconomy.Tests`, `CodeHelper.Tests` if touched) green.
- Generate the table on `F:\source\mcp`, run the sync check green, then break `CLAUDE.md` and see it fail.
- `get_instruction instruction-placement` returns the new text; store-drift check clean.
- New chat session: `build_concise_context` shows the table line; navigate using only table + `code_index`.

## Choices to redirect
- `table` is an action on `code_index`, not a new tool.
- Regenerate on scan, not via a new file watcher.
- Deterministic summaries (no LLM), semantic link marked `pending` until indexed.
- Scope is large (units 5 especially); unit 5 can be split to a follow-up PR if you prefer.
