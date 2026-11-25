# Reindex optimization plan

Status: draft, not approved. Scope: `TokenSaver/src` (submodule). Orchestration repo only holds this file.

## Problem (verified in code)

- Three walkers each enumerate and read the workspace independently: `WorkspaceIndexService` (full bootstrap walk, `WorkspaceIndexService.cs:116`), `RepoIndexer` (`RepoIndexer.cs:43`, reads every file at `:69`), and background triggers (`SymbolScanBackgroundTrigger.cs:55`, `SemanticIndexBackgroundTrigger.cs:188,226`). `RebuildReferencesAsync` re-reads every `.cs` file on any change (`WorkspaceIndexService.cs:204-255`).
- Mtime-only gate (`WorkspaceIndexService.cs:280-282, 378-380`). `Files.ContentHash` is written (`:463`) but never compared before parsing.
- AI summary runs before the hash (`:415` before `:417`). An mtime-only change (touch, branch switch with identical content) still costs an LLM call.
- No git hook. Git diff runs only through `GitStalenessChecker.CheckAsync` (`Utilities/Services/GitStalenessChecker.cs:99-141`). First run or unresolvable SHA forces a full walk.
- 10-minute prune sweep loads every `Files` row and calls `File.Exists` per row (`:137-143, :315-362`).
- `RepoIndexer` uses a private ignore list (`:31-32`), not `WorkspaceIgnoreFilter`.

## Decisions (answered)

- Git trigger: FileSystemWatcher on `.git/HEAD` and `.git/index`. No hooks installed in user repos.
- Codegen feed: new MCP tool `index_files_changed(paths[])`. `EditFile` also enqueues.
- `RepoIndexer` merges into the single `WorkspaceIndexService` pipeline.

## Phases

### Phase 1: Shared change set and hash gate
1. New `ChangeDetector` in `TokenSaver.CodeHelper.Indexing`. Produces one `ChangeSet` per index cycle (added / modified / deleted paths).
2. Gate order per file: size+mtime match stored row → skip. Else SHA256 of bytes vs `Files.ContentHash` → skip if equal. Else changed.
3. Hash bytes before the summary call, so identical content never reaches the model.
4. Tests: touch-only file produces zero summary calls; content edit produces one; empty file hashes stably.
- Risk: current `ContentHash` is text-based (`:417`). Changing its input changes every row once. Decide: keep text hash, or migrate (see open question A).

### Phase 2: Single pipeline (fold in RepoIndexer)
1. `RepoIndexer` consumes the `ChangeSet` instead of walking. Reads each file once; shares the content buffer with the symbol parser and the reference graph.
2. Route all walks through `WorkspaceIgnoreFilter`. Removes the private `IgnoredSegments` list.
3. Chunk-level hashes stay (`RepoIndexer.cs:82-89`), but only for files already in the change set.
4. Prune driven by `ChangeSet.Deleted`, not the 10-minute `Files` scan. Keep a low-frequency full reconcile as a safety net.
5. `RebuildReferencesAsync` rebuilds edges only for changed files plus their dependents.

### Phase 3: Git watcher
1. Watch `.git/HEAD` and `.git/index` (debounced, 1s like `GitignoreWatcherService.cs:36`). On event, run `git diff --name-status <lastSha> HEAD` plus `status --porcelain` and feed the `ChangeSet`.
2. Use `A/M/D/R` to drive add, update, delete, and rename. Renames stop being delete+add.
3. Worktrees and submodules: `.git` is a file there. Resolve the real git dir with `git rev-parse --git-dir` before watching.
4. Ignore-flip events still need the full walk (see `WorkspaceIndexService.cs:161`). Keep `ReconcileIgnoreChangeAsync`.

### Phase 4: Codegen and agent push
1. New MCP tool `index_files_changed(paths[])` in `Tools/`. Validates paths, applies `WorkspaceIgnoreFilter`, enqueues.
2. `EditFile` enqueues its target automatically.
3. Bounded `Channel<ChangeEvent>`, deduplicated and debounced, drains into the same `ChangeSet` as Phases 1 to 3.
4. Watcher and periodic reconcile stay as the safety net: pushed events can be lost.
5. Update the tool contract doc and tests in the same change (per `TokenSaver/CLAUDE.md`).

### Phase 5: Background triggers
1. `SymbolScanBackgroundTrigger` and `SemanticIndexBackgroundTrigger` consume the shared queue. No independent walks.

## Ranking (Sonnet review, agent `a57c4688140d55386`)
1. Hash gate with shared list: largest win (skips LLM calls and double reads).
2. Git-event reindex: removes full walks on large repos.
3. Push queue for codegen: O(changed) latency for agent edits.

Sonnet also flagged `RebuildReferencesAsync` as an uncounted fourth full-read path. It is in Phase 2.

## Decisions (answered)
- A. Hash: raw-byte SHA256 of file bytes. All rows re-index once.
- B. Schema: no migration. Project is in beta: delete the existing `.tokensaver/index.db` and rebuild from scratch.
- C. Ship: full plan in one change set, all five phases. Not phase 1 alone.

- D. Ignore set: one shared list in `WorkspaceIgnoreFilter`. Replaces RepoIndexer `IgnoredSegments`, `GitStalenessService.AlwaysSkipDirs` (:18-19), `GitStalenessChecker.SkipWalk` (:36-37). Files under build/, venv/ etc. stop being chunked everywhere.
- E. DB delete: delete `.tokensaver/index.db` plus WAL/SHM. Stop the MCP server first. Savings data in the same file is lost (accepted).
- F. ChangeSet type lives in `Common/TokenSaver.Common.Contracts`.
- A is moot under B/E: no per-row re-index migration needed, the DB is rebuilt.

## Review corrections (Haiku review, read-only)
- Plan is a draft until Unit 1 starts; the duplicate `plans/reindex-optimization.plan.md` is removed.
- Phase 4.2: `EditFile` already reindexes synchronously via `PatchEngine` to `IFileReindexer.IndexFileAsync` (`CodeHelper/Patching/PatchEngine.cs:120-127`, `Host/TokenSaver.MCP/Tools/CodeHelperTools.cs:271,355-478`). Replace that call with the queue; do not add a second path.
- Phase 3.1: current code runs `git diff --name-only` (`GitStalenessChecker.cs:126`). Switching to `--name-status` is part of U8.
- Ignore-flip path is `ReconcileIgnoreChangeAsync` at `WorkspaceIndexService.cs:165` (not :161).
- Phase 2.1: RepoIndexer only chunks (`RepoIndexer.cs:76`). Symbols and references live in `WorkspaceIndexService`; do not claim shared buffers with them.
- Phase 4.5: no tool-contract doc names index tools; `TokenSaver/CLAUDE.md:90-92` lists only health and token-economy contracts. Add a contract note only if one is created.
- Benchmark "0 files read" holds for git roots only. Non-git workspaces full-walk every call (`WorkspaceIndexService.cs:113-118`); state this in the benchmark.
- Missing walkers to add to the plan: `FolderTreeManager.EnsureFoldersAsync` (`FolderTreeManager.cs:313`, called at `WorkspaceIndexService.cs:115,170`); `ContextPipelineService.GetStaleFilesAsync` (`ContextPipelineService.cs:239`, `GitStalenessService.cs:139-169`), full Files scan per `BuildConciseContext`; directory expansion (`ContextPipelineService.cs:372`).
- Keep the `NeedsReindexAsync` heal path (`WorkspaceIndexService.cs:533-543`) so zero-symbol files still reparse after a hash gate.
- Git baseline advances before indexing (`GitStalenessChecker.cs:156-158`). Advance only after a successful index, or failed files are lost.
- Single-flight `IndexWorkspaceAsync`: concurrent callers at `ContextPipelineService.cs:210`, `WorkspaceRootSessionResolver.cs:225`, `SymbolScanBackgroundTrigger.cs:55`.
- "Dependents" (Phase 2.5) needs a reverse-edge query that does not exist yet; define it in U7.
- Git watcher: `git status` may write `.git/index` and retrigger the watcher; try `--no-optional-locks` (unverified).
- Pushed plus watcher events can double-count; dedupe must be idempotent.

## Units (implement-plan order)
- U1 ChangeSet (in Common contracts) and raw-byte SHA256 gate in `IndexOneFileAsync`. Test: touch-only file makes 0 summary calls (`WorkspaceIndexServiceTests.cs:282-291, 415`).
- U2 Gate keeps `NeedsReindexAsync` heal path. Test: matching hash with zero symbols is reparsed.
- U3 Advance git baseline only after success. Test: summary throws for one file; next run reindexes it.
- U4 Single-flight `IndexWorkspaceAsync`. Test: two concurrent calls make one pass.
- U5 RepoIndexer consumes ChangeSet. Test in `TokenEconomy.Tests/Indexing/RepoIndexerTests.cs`: second run reads 0 files.
- U6 Shared ignore list (decision D). Test: `build/` not chunked.
- U7 Incremental references with reverse edges. Test: editing a type updates dependent edges.
- U8 Git watcher, `--name-status`, rename handling, worktree `.git` file resolves gitdir. Test: rename reports R, not D+A.
- U9 `index_files_changed` tool; `EditFile` routed through the queue (replaces the synchronous reindex call). Test in CodeHelper tools tests.
- U10 Triggers consume the queue; retire `GetStaleFilesAsync`.
- U11 Stop MCP, delete `.tokensaver/index.db` + WAL/SHM, rebuild, benchmark on the user's machine.

## Status
- U1 done: commit `5c78be1` on `TokenSaver` branch `feat/reindex-optimization` (pushed). Raw-byte hash before summary. `ContentHashGateTests` red then green; CodeHelper suite 51/51 pass.
  - Deviation: ChangeSet type (decision F) is not introduced in U1; it lands with U5 when RepoIndexer consumes it.
  - U2 heal path is preserved by the `!NeedsReindexAsync` check, but has no dedicated test yet.
- U2 done (uncommitted test added in `254be85`): heal path test `MatchingHash_ZeroSymbols_IsReparsed` passes.
- U3 done: `254be85`. Baseline advances only after success (`CheckAsync` takes `commitBaseline`; `PlanTargetFilesAsync` + `CommitBaselinesAsync`; any per-file failure keeps the old baseline). Red test `GitBaselineTests` first (expected 2, got 1).
- U4 done: `6587aeb`. Per-root single-flight gate in `IndexWorkspaceAsync`. Red test `IndexConcurrencyTests` first (expected 3 summaries, got 6).
- CodeHelper suite: 54/54 passing on the branch.
- U5 done: `5305bf1`. RepoIndexer skips unchanged files without reading them. Each Chunks row carries its file stamp (mtime, size, raw-byte hash). Red test `IndexRepoAsync_UnchangedSecondRun_ReadsNoFiles` first. TokenEconomy suite 84/84; CodeHelper 54/54.
  - Deviation from plan: the ChangeSet type (decision F) is not introduced here. The per-file stamp gate gives "read 0 files" without it. ChangeSet is deferred to U8/U9, where a watcher or tool needs a shared list.
- U6 done: `935e073`. One always-skip list in `TokenSaver.Utilities/Services/AlwaysSkipDirectories.cs` replaces three private lists. `WorkspaceIgnoreFilter` honors it, and bypass can still re-include. Red test `IgnoreSetTests` first (expected 1, got 2). CodeHelper 55/55, TokenEconomy 84/84.
  - Deviation from decision D: the list lives in Utilities, not `WorkspaceIgnoreFilter`. Config references Utilities, so the reverse would be a cycle. The filter reads the list.
  - Behaviour change: `build/`, `out/`, and `venv/` are now skipped by every walker, not only RepoIndexer.
  - Gotcha: the first split used the `Split(char, char, options)` overload, which failed on backslash paths. Fixed with an explicit `char[]`.
- U7 done: `86053c7`. Incremental SymbolReferences rebuild. Full rebuild on bootstrap and once per PruneInterval. Otherwise re-read only changed C# files plus dependents (sources whose edge targets no longer exist). `IndexStats.ReferenceFilesRead` reports the re-read count. Red test `ChangedFile_RereadsOnlyItselfNotUnchangedSiblings` first (expected 1, got 0). Rename guard test passed before and after. CodeHelper 57/57.
  - Known gap: a new reference from an unchanged file to a new type is picked up at the next full rebuild, not the incremental pass.
- U8 done: `beb1d55`.
  - `git diff --name-status -M`: a rename drops the old path at once (red test `GitRenameTests` first, old path still indexed). Renames and copies contribute both paths.
  - `status` runs with `--no-optional-locks`, so it cannot rewrite `.git/index` and retrigger the watcher.
  - `GitRepoWatcherService` (MCP host): watches the resolved git dir (`rev-parse --absolute-git-dir`, worktree and submodule safe) for `HEAD` and `index`, debounces 1s, then runs `IndexWorkspaceAsync`.
  - Not covered by an automated test: FileSystemWatcher timing. Verify by hand on the user's machine.
  - Git-written `refs/heads/*` changes without touching `index` (e.g. `git update-ref`) are not watched; the next tool call still picks them up through the baseline check.
- U9 done: `e63ed31`. `WorkspaceIndexService.IndexPathsAsync` indexes exactly the listed paths (deleted ones removed) on the same per-root gate. `IndexFileAsync` (the `EditFile` route via `PatchEngine`) delegates to it. `IndexChangeQueue` collects pushed paths and flushes them. The MCP tool `index_files_changed` (`IndexChangeTools`) exposes it. Red tests `IndexPathsTests` first (compile error).
  - Deviation: `EditFile` stays synchronous; it reaches the same entry point and no background drain exists. The plan asked for a queue-fed `EditFile`.
- U10 done in part: `GetStaleFilesAsync` (full Files scan on every context build) is removed. `ContextPipelineService` reports the per-root failed-path set kept by the index pass. Its three tests are removed.
  - Not done: the whole-root triggers (`SymbolScanBackgroundTrigger`, `SemanticIndexBackgroundTrigger`) still call `IndexWorkspaceAsync`. They are single-flight but do not drain the queue.
  - Test gap: no test forces a per-file failure, so `GetFailedPaths` has no direct coverage.
- U11 partly done: regression test `IdleReindexTests` (second pass on an unchanged repo: 0 files, 0 model calls, 0 reference reads).
  - DB: deleted `F:\source\mcp\TokenSaver\.tokensaver\index.db` plus WAL/SHM with the server stopped (service `TokenSaverMCP` stopped, no process). Savings data in that file is lost. Left in place: `F:\source\mcp\.tokensaver\index.db`, `docs\.tokensaver\index.db`, `instructions\.tokensaver\index.db`. The new Chunks columns need a rebuilt DB in any workspace that still has an old one.
  - Benchmark: covered by the regression test on this machine, not timed on your machine.
- Suites on this machine: CodeHelper 58/58, TokenEconomy 84/84, MCP host 363/363.
- Still open: superproject `mcp` pointer and plan doc are not committed on a matching branch.
- Superproject `mcp` pointer and plan doc not yet committed on a matching branch.
- Not yet run on the user's machine (`dotnet test TokenSaver.slnx` there).

## Verification
- `dotnet test` on `TokenSaver/TokenSaver.slnx` (run on the user's machine per `.claude/rules/build.md`).
- Benchmark: second `IndexWorkspaceAsync` on an unchanged repo should read 0 files and make 0 model calls.
