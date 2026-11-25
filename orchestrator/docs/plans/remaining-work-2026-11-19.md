# Remaining work (mcp orchestrator), 2026-11-19

Status as of 2026-11-19. Source: the open items in docs/plans/ide-bridge-split.md and codebase-review-fix-plan.md, plus the current branch state.

## IDE bridge
- Moved to SperryDev.Ide-Bridge: docs/plans/remaining-work-2026-11-19.md (the bridge split, the VS 2026 and VS Code bridge items, and the docs).


## SperryDev.Docs (not started)

- [ ] Create the repo layout and move the SimpleModelServer and Common docs into it, one folder per repo. TokenSaver docs stay.
- [ ] Replace moved docs with README links in those repos.
- [ ] Regenerate docs/folder-index.md with code_index(action: 'table').

## Codebase review fix plan (partly done)

- [ ] Q8: fresh-clone build-vsix check.
- [ ] Q9: VSEXT0010 is suppressed; verify VS extension load on VS 18.
- [ ] Q10: agent.md still has the F:\mcp path and snake_case names. Confirm /health folder-index, and the root .gitignore [Bb]uild/ entry.
- [ ] R1: MSI install and uninstall not run; VS Users card and VS Code picker not exercised in a real IDE; service still LocalSystem.
- [ ] R2: container_exec, wsl_run and wsl_do are not covered by the path confinement.
- [ ] R3: BehaviorConfigOverlay still last-resolved-wins; SIMPLEMODELSERVER_WORKSPACE is process-wide; not run against a real client.
- [ ] R5: LogHelper keeps its own runner; TestRunnerService and IdeTestRunService result models are not unified.
- [ ] R6: debug state has no file/line, call stack or variables; not run against a live IDE; npm audit high advisories open; not verified against real clients after a write.
- [ ] R7: per-root lock not done; the two accessors not merged.
- [ ] R8, R9, R10: not started.

## Carried from other mcp plans (open items)

From additons.md (TokenSaver tools; confirm Node.js vs Python first):
- [ ] lib/distill.js and lib/ollama.js (build step 1); terse-mode retrofit onto ContainerLogs; lib/savingsTracker.js and verdict().
- [ ] TokenBudget, ModelRoute, ContainerLogs (phases 1–2); RunTests, LintFix, BuildWatch (phase 3); SessionSnapshot/Restore, DiffSummarize; EmbedCache, IndexRepo, SemanticGrep; TokenSavingsReport, WorthKeeping.
- [ ] DependencyAudit: not in the build order; status unclear.

From gotcha-system.md (contribution security):
- [ ] Items 1–4 of the contribution security workstream; CI malicious-content scanning (AV, snippet deny-patterns, regex DoS, URL allowlist); provenance minimum (signed commits or verified accounts); blast-radius controls (staging branch, release-only snapshots).
- [ ] Write phase-4-contrib-security.md (not written).
- [ ] gotcha-mcp Phase 1 C# validator; git init, push and submodule wiring. The gotcha contribute release is blocked until the three security items exist.

From inherited-forging-crab.md (gotcha/lessons system):
- [ ] U1–U7 schema change and single rebuild; U8 docs scanner provider; U9 context queries and checks; U10 ask action and evidence pack.
- [ ] U11a summary cache and staged loader; U11b acceptance and stage enablement; U12 refresh skill and hooks; U13 structured pitfalls.md migration.
- [ ] U14 gotchas, global.db unit, promotion (global.db unit not written); U15 hooks, spool, lessons-check gate (hook p95 unmeasured).
- [ ] Dry run (code_index plan); golden set (30 items) and eight-query test; review round 3 mechanical edits.
- [ ] Confirm the index DB location and owning project in TokenSaver (blocks U1).

From instr-index.md (instruction index):
- [ ] Setup: superproject worktree and TokenSaver branch instr-index; Sonnet read-only plan review and fold-in.
- [ ] Units 1, 2, 3, 3b, 4, 4b (check .claude/rules/instructions.md against the unit), 5 (coverage test, split decision open), 6 (global skill text; user confirmation needed), 7 (gate, push, PR, archive).
- [ ] Verification steps; the "choices to redirect" table, regenerate-on-scan, deterministic summaries and unit-5 split need the user's confirmation.

From model-eval.md (embedding and summary models):
- [ ] Raw-text vs summary embedding comparison; qwen3-embedding:0.6b vs nomic-embed-text.
- [ ] Score all eight queries (only four tested; JammingIncident missed); widen the gemma3:1b summary check beyond a three-snippet sample.
- [ ] Rebuild the full VideoForensics index with the chosen models (paused).

From reindex-optimization.md:
- [ ] U10 triggers still call IndexWorkspaceAsync and do not drain the queue; GetFailedPaths has no test.
- [ ] U11 DB rebuild, benchmark and dotnet test on the user's machine (machine-side steps open).
- [ ] Rebuild old workspace DBs under mcp, docs and instructions.
- [ ] ChangeSet type in Common contracts (decision F, deferred); EditFile still synchronous, not queue-fed.
- [ ] Walkers not covered by any unit: FolderTreeManager.EnsureFoldersAsync, ContextPipelineService, directory expansion.
- [ ] Known gap: new reference from an unchanged file found only at full rebuild; git-written refs/heads changes not watched; FileSystemWatcher timing verified by hand only.
- [ ] Superproject mcp pointer and plan doc not committed on a matching branch.

From settings-scope.md (each change needs your yes before it is applied):
- [ ] Move machine facts from global CLAUDE.md to ToolIncompat; split permissions.allow (about 240 entries) into global and local; move RomRaider, PsScripts and ECU-Toolkit entries, and their additionalDirectories, to local.
- [ ] Move autoMode to local; move ProgramData context.debug to local; move repoHelper.autoSplitOversizedInstructions to local; set tokenEconomy.modelRoutes.embed EmbedModel per project.
- [ ] install.ps1 is missing skills\implement-plan; submodule count in build.md and mcp CLAUDE.md (two stated, three in .gitmodules); server default root F:\mcp is stale.

From single-point-db-access.md:
- [ ] Architecture gate tests (no DB references in clients); unit 1: prune removed or ignored files from the index.
- [ ] Per-unit DTO, mapping, server repo, remote class, DI (units not enumerated); Common contracts replace entity types with DTOs; AgentHelpers and VS Code client HTTP remote classes.
- [ ] Route versioning under /api/v1 (decided, not implemented); branch feat/single-point-db in each submodule (not created); check SimpleModelServer for database use; superproject pointer updated last.

## User-level plans (C:\Users\rsper\.claude\plans), open items

From inherited-forging-crab.md (pending unless noted):
- [ ] U1–U4 schema, version gate, context and operational tables; U5 stable keys and upsert; U6 RepoIndexer on FileId; U7 provider manifest, typed sink, conformance kit.
- [ ] U8 docs scanner; U9 context queries and checks; U10 ask action and evidence pack; U11a summary cache and staged loader; U11b acceptance and dry run.
- [ ] U12 refresh skill and hooks; U13 migrate both pitfalls.md files; U14–U15 gotchas, promotion, hooks, gate.
- [ ] Review round 3 "still to apply" list (partly done). Index DB location and owning project (unconfirmed). Sonnet rule conflict (decision 4, open).

From open-work.md:
- [ ] Decisions 1–5: Ring zone_settings type; InternalsVisibleTo key; MAUI Evidence page; NETSDK1152 exclusion; global rules open decisions.
- [ ] A1 NETSDK1152 publish fix (blocked on decision 4); A2 debug-launch and deploy script fixes; A3 Windows service x64 runtime; A4 Vitest baseline import fix.
- [ ] B5 KeyStorageFactoryTests; B6 Ring salt tests injectable path; B7 AccountLinkedWiringTests timeout; B8–B9 reason-lists recurrence check and watch-list flakes.
- [ ] C10–C13 environment cleanup (needs you); D14 about 420 logger calls sweep; D15 plan-update script steps; D16 VS debug launch profile test.
- [ ] E18–E19 local main fast-forward and new session.

From service-interval-settings.md:
- [ ] Sonnet standing review (not run).

From settings-scope.md (each change needs your yes before it is applied):
- [ ] Global CLAUDE.md machine facts to ToolIncompat; split the settings.json permissions.allow (about 240 entries); move autoMode, additionalDirectories, ProgramData context.debug, repoHelper.autoSplitOversizedInstructions and the RomRaider/PsScripts/ECU-Toolkit entries to local.
- [ ] tokenEconomy.modelRoutes.embed EmbedModel record; install.ps1 missing skills\implement-plan; build.md and mcp CLAUDE.md submodule count; server default root F:\mcp.

From shimmering-hopping-haven.md (gap planner):
- [ ] 1 GapPlanner (pure planner and tests); 2 horizon computation; 3 repository queries; 4 settings rename (settings-page UI committed as 52a22481; partly done).
- [ ] 5 remove per-account roll-up interval and migration; 6 per-segment builder entry point; 7 ScheduledSyncService changes; 8 coverage changes (TimeLapseCoverage, thinning, fallback); 9 config DTO fields and mapping.
- [ ] 10 one-off cleanup (dry run, then delete, manual); 11 deploy and backfill; verification (build, scoped tests, crash check, manual gap check).

From single-point-db-access.md:
- [ ] Confirm index DB location and owning project in TokenSaver (blocks unit 1); check SimpleModelServer database use.
- [ ] Unit 1 prune removed or ignored files; architecture gate tests (fail before, pass after); per-unit DTO, server, remote class, DI and consumer work.
- [ ] Create feat/single-point-db in each submodule from feat/reindex-optimization; done-when criteria.

From we-need-to-make-immutable-candy.md (log helper; not started):
- [ ] U0.1 branch, plan file, U0.2 read-only Sonnet plan review (next unit).
- [ ] U1.1–U1.14 Phase 1 vertical slice (incl. IdeTools and ManagedProcessTools registration); U2.1–U2.3 run snapshots and LogMarkRun.
- [ ] U3.0, U3.0b, U3.1–U3.5 Phase 3 VS Code (spike U3.3); U4.1–U4.3 Phase 4 Visual Studio; U5.1–U5.3 trace flagging, ignored view, watch.
- [ ] U6.1–U6.4 Phase 6 syslog and Event Log sources; U7.1–U7.4 Phase 7 skills and docs; U8.1–U8.5 Phase 8 hardening and smoke.
- [ ] Verification: tests, size comparison, full gate before PR.

From we-should-then-add-magical-scroll.md (pull queue):
- [ ] Confirm the attempt cap of 3; confirm whether "terminal unavailable" needs its own enum value; confirm manual Sync Now shows the held reason and does not run a partial pull.
- [ ] Approaches 1–5: queue as data (DownloadAttempts, NextAttemptAtUtc migration); attempts cap to terminal state; batch backfill pass; pull gate in EventPullService, AccountSyncRunner and ScheduledSyncService; Sync page queue depth and sync log.
- [ ] Five failing tests written first; lite gate build and test; one-time backfill run against a test database.

## Worktree copies (new items only; the rest duplicate items above)

- [ ] reindex-optimization: approval still says "draft, not approved"; stale index.db under mcp\.tokensaver, docs\.tokensaver and instructions\.tokensaver to rebuild; U11 benchmark and dotnet test on your machine.
- [ ] inherited-forging-crab: review round 3 mechanical fixes and additions (not applied); remove the auto-proposed Workaround from the spec; split the SimpleModelServer Inno entry; hook p95 budget; U11b dry run before any stage is enabled.
- [ ] codebase-review R6: dead surfaces, including the uncalled TryInterceptAsync.
- [ ] additons: confirm the server language (the design assumes Node.js; TokenSaver is C#); record phase status (none recorded).
- [ ] instr-index: confirm whether the setup worktree (F:\mcp-worktrees\instr-index) completed setup.
- [ ] TokenSaver ci-standalone-installer: status header says "in progress" though U1–U4 are checked; fix the header.
- [ ] TokenSaver common-as-nuget risks: version collision, PAT scope, %VAR% expansion on the runner.
- [ ] TokenSaver wt-standard-session (older worktree snapshot): U7 TerminalControl tests, commit and push feat/wt-standard-session; package tokensaver-tab.ps1 into the MCP host.

## Housekeeping

- [ ] Remove worktrees F:\source\TokenSaver-wt-work and F:\source\mcp-wt-root after their merges.
- [ ] Local wip is ahead of origin/wip. Decide what gets pushed; wip itself is never pushed (per memory rules).
- [ ] Stray file C:\Users\rsper\AppData\Local\Temp\new.slnx: delete after confirming it is not used.
- [ ] Decide whether to revert TokenSaver PR #28 and root PR #20 (open question).
- [ ] CI has had no runner since about 19:00 on the root repo; check it.

## Verification

- Root: build and test the repos that changed; confirm the pointers match pushed commits.
