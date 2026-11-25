# Log Helper (VS Code / VS now, standalone later)

## Context
Debugging and log refinement burns tokens on raw log dumps. Add a log helper so an AI pulls only what matters: filtered, template-deduplicated, run-to-run diffed, with flagged stack traces. Lives in the `TokenSaver` submodule (branch it from the repo's base branch, keep the `mcp` pointer in sync, push submodule first). Two reviews (Sonnet, Fable) are folded in.

## Process (implement-plan skill)
Save to `TokenSaver/docs/plans/log-helper.md`, work phases in order, tests first, commit/push work branch per unit, archive when done. Stronger-than-Haiku model for phases 3-5 only with user's yes.

## Decisions (from user)
- VS Code: debug-session output + extension log files on disk + owned-channel capture.
- Core: new library `TokenSaver.LogHelper` + MCP tools; standalone host reuses it later.
- State: JSON files (see run snapshots).
- Also in scope: Windows Event Log and syslog sources (sequenced last), and three skills: level advisor, sink prune, sink elevate.

## Layering
- `src/Core/TokenSaver.LogHelper` (net10.0, no ASP.NET/IDE refs): `ILogSource`/cursor, LogEntry, parser, filter, normalizer, trace flagging, run snapshots/diff, `FileLogSource`, later `SyslogSource` and `EventLogSource` (`System.Diagnostics.EventLog` works on plain net10.0 behind `OperatingSystem.IsWindows()`; no separate assembly).
- `src/Host/TokenSaver.MCP/Tools/LogTools.cs` (thin).
- Skills in `instructions/skills/`: `log-level-advisor`, `log-sink-prune`, `log-sink-elevate`. No library "advisor" classes: sink config lives in repo code, not logs, so the tool returns data (template counts by level, flagged traces, system-sink templates) and the skills grep call sites and propose edits. Skills only suggest; nothing writes to Event Log/syslog.
- Relationship to existing code: LogHelper is the deterministic pre-pass. Existing `DistillRole.LogErrors` (`DevLoopTools.cs`), `02_LogStrippingStage`/`01_DeduplicationStage`, `IdeGetOutput`/`IdeSearchOutput` stay; cross-reference tool descriptions, evaluate routing `DevLoopTools` through LogHelper later.

## Remote standalone readiness (build now, ship later)
Goal: the same library runs as a standalone agent/MCP host on a deployed server, queried remotely. Constraints applied now so it is a packaging step later:
- **Transport-agnostic core**: `LogTools` stays a thin adapter over a `ILogService` facade (query/channels/markRun/sinkCompare) taking and returning plain DTOs. Any host (in-proc MCP, standalone MCP over HTTP, CLI) calls the facade.
- **Sources are local to wherever the service runs**: a remote deployment runs the helper on the server, so `FileLogSource`/`SyslogSource`/`EventLogSource` read locally there; no IDE-bridge types in Core. IDE sources live in the IDE-facing host only.
- **Pre-reduction on the server**: filtering, templating, and `maxTokens` capping happen server-side, so only the small summary crosses the network.
- **Channel ids are host-qualified-ready**: `<host>/<source>:<name>` form reserved (local host implicit now), so a client can address multiple servers later.
- **Config-driven, no workspace assumptions**: allow-listed roots, state dir, redaction, channel allow-list come from a config object (file/env), not `WorkspaceRootResolver` baked into Core (the MCP host supplies the workspace default). State dir default overridable for services.
- **Auth/security hooks defined now, implemented later**: request context (caller identity, read-only scope) passed into the facade; allow-list + redaction already mandatory; remote host will add TLS + token auth, per-caller channel scopes, rate and response-size limits, audit log of queries. Default bind is loopback only.
- **Stateless-friendly**: cursors and run ids are self-contained tokens, so any instance/HTTP request can resume; run snapshots stored per service state dir.
- **Cross-platform**: Core builds for Linux (no Windows-only types outside `EventLogSource` guard); CI builds/tests Core on Linux too.
- **Packaging (later plan)**: `TokenSaver.LogHelper.Host` (console/service, Windows service + systemd unit + container image), reuses ModelContextProtocol HTTP transport pattern from `ProgramRegistration.cs`. Out of scope now except the constraints above.

## Tool surface (4 tools, not 9)
Channel ids carry the source: `file:<path>`, `vscode:<name>`, `vsout:<pane>`, `debug:<session>`, `eventlog:<name>`, `syslog:<src>`.
- `LogChannels(filter?)` — list available channels.
- `LogQuery(channel, filter?, view=summary|entries|traces|ignored, since=cursor|lastRun|<runId>, waitSeconds?, maxTokens=1500)`.
  - `summary` (default): templates = normalized message, count, level, first/last time, one sample; compact text lines, not JSON per entry.
  - `ignored`: what the filter dropped (as templates), to verify the filter hides nothing important.
  - `traces`: flagged stack traces grouped by top-frame hash, `confidence: low|medium|high` + `reason`.
  - `since=lastRun`: diff vs previous run snapshot. `waitSeconds` (cap ~25) = bounded live watch returning `nextCursor`.
- `LogMarkRun(channel)` — explicit run boundary (auto-delimited by debug-session/process start where available).
- `LogSinkCompare(appChannel, sinkChannel)` — template counts by level for app log vs system sink, input for the prune/elevate skills.
Filter (4 fields): `match` (regex), `exclude` (regex), `minLevel`, `category`. Savings recorded via `ISavingsTracker.RecordAsync`.

## Core specs
- **Normalizer (phase 1, versioned)**: mask timestamps, GUIDs, hex, numbers, durations, paths, ANSI codes. On version bump the diff returns "baseline reset", not everything-new.
- **Parser**: new level detection (do not reuse private substring-based `ClassifySeverity`). Formats: bracketed/plain, Microsoft.Extensions.Logging console (`info: Category[0]` + indented message), JSON-lines (Serilog compact, pino numeric levels), Python `Traceback`, Java `Caused by`, UTF-8/BOM/UTF-16. Multi-line folding, size capped. VS "Exception thrown: ... in X.dll" = first-chance, negative marker.
- **Trace flagging**: markers .NET `Unhandled exception.`/`AppDomain.UnhandledException`, Node `unhandledRejection`/`uncaughtException`, Java `Exception in thread`, trace logged at Info/Debug. No "same-site handled" heuristic.
- **Run snapshots (replace seen-hash LRU and commit flag)**: per run store template->count map; keep last 3-5 runs; diff is a pure function of two snapshots (new, gone, count changed). Idempotent, little locking. State in `.tokensaver/logs/` (gitignored, via `WorkspaceRootResolver`), key = (source, channel id, workspace), sanitized names, schema+normalizer version, atomic write via temp + `File.Move(overwrite: true)` (not `File.Replace`, which throws on first write), per-key lock, corrupt file tolerated. State holds hashes, counts, one redacted sample, never raw lines.
- **ILogSource cursors**: opaque; file = id + offset + hash of N bytes before cursor (verified on resume; file ID not creation time; head fingerprint alone is insufficient); EventLog = bookmark; journald = cursor. Partial trailing line skipped; commit only at entry boundaries; `FileShare.ReadWrite|Delete`.
- **Security (server runs as LocalSystem, `Service.wxs`)**: file source canonicalizes (`GetFullPath`, resolve junctions/symlinks), rejects UNC, `\\?\`, `::$DATA`, applies to rotation siblings; allow-list roots come from bridge/config (not `%APPDATA%` of SYSTEM). Event Log channel allow-list, Security denied by default. Redaction on by default (tokens, emails, connection strings), opt-out. `journalctl`/WSL args passed as array, names validated. Regex: always `NonBacktracking`, reject unsupported patterns (lookarounds, backrefs) with clear error, length cap.
- **Watch**: bounded poll, CancellationToken, per-watch dedup, `nextCursor`.

## IDE side
- MCP host reads on-disk log files itself via `FileLogSource`; bridge only reports roots/channel paths (avoid bulk over the one-line named pipe).
- **VS Code**: (1) add `registerDebugAdapterTrackerFactory` capturing DAP `output` events per session (debugged app output, not on disk; gives run boundaries); (2) 30-minute spike: verify `output_logging_<ts>\` contains other extensions' output channels (if so, plain-channel limitation drops and owned-channel capture shrinks); (3) log root from `context.logUri` (not wired today), handle Insiders/VSCodium/portable/remote-WSL; (4) fix `appendOutput` buffer first: carry partial lines across stdout chunks, keep empty lines, per-line sequence numbers, `dropped` count when cursor older than buffer head.
- **VS**: `listOutputPanes`; `getOutput` gains `fromOffset`/`maxChars` (currently re-reads whole pane); use the same before-cursor hash anchor so clear-and-refill is detected; UI-thread rules.
- Rebuild/bump: `scripts\update-vs-extension.ps1`, TS lint per `lint` skill, MCPB check.

## Wiring
`LogHelper(+.Tests)` in `TokenSaver.slnx` (folder + BuildDependency), `ProjectReference` in `TokenSaver.MCP.csproj`, `.WithTools<LogTools>()` in `ProgramRegistration.cs`, 2 rows in `McpContextService.Registry` (curated list, no count test), test csproj from `TokenSaver.TerminalControl.Tests` (net10.0, xunit 2.9.3, Test.Sdk 18.12.0, runner 3.1.5). `install-instructions.ps1` copies all skill folders, no change needed.

## Phases (vertical slice first; tests first)
1. Parser, versioned normalizer, filter, basic `FileLogSource`, `ILogService` facade + DTOs, `LogChannels` + `LogQuery` summary view, wiring, golden test. Define `ILogSource`, `LogHelperOptions` (config object), request context. Add Linux CI build/test for Core.
2. Run snapshots/diff, `LogMarkRun`, `since=lastRun`.
3. VS Code: buffer fix, debug adapter tracker, log-root discovery, channel spike, `vscode:`/`debug:` sources.
4. VS panes + `vsout:` source.
5. Trace flagging (`traces` view), `ignored` view, `waitSeconds` watch.
6. `SyslogSource` + `EventLogSource` + `LogSinkCompare`.
7. Three skills + docs.
8. Hardening: rotation edge cases, redaction tuning, security tests, routing `DevLoopTools`.

## Tests
xunit; `TimeProvider` injected (RFC3164 year, watch). Golden test asserts **recall and reduction**: one unique error seeded in 10k noisy lines must survive. Chunk-split property test (any split == one-shot read). Rotation/truncation/partial-line/BOM/concurrent-writer fixtures. Parallel state tests, corrupt state. Path traversal cases (`..`, junction, UNC, ADS). Regex rejection/timeouts. Response-size cap on every view. Event Log via saved `.evtx` fixtures asserting raw-data fallback (provider DLLs vary on CI), Windows-gated. Syslog fixtures (yearless 3164, 5424, journald JSON). MCP tool tests in `TokenSaver.MCP.Tests\Tools`. TS/VS bridge tests. Scripted smoke against a real VS Code session.

# IMPLEMENTATION PLAN (by Fable; saves to TokenSaver/docs/plans/log-helper.md)
**Status:** Phase 5 done (U5.1 traces view, U5.2 ignored view, U5.3 bounded watch via waitSeconds, max 25; LogHelper 125 green, MCP 565 green). Phases 1–4 done except U4.3 (VSIX reinstall and live smoke, awaiting approval to run `scripts/update-vs-extension.ps1`). Phase 4 added U4.1 (98786a5) and U4.2 (f54abcc). Phases 1–3 done (U1.1–U1.14, U2.1–U2.3, U3.0–U3.5; TDD red/green per unit). Last code commit 23a43b1 plus a parser follow-up; LogHelper 109 tests green, MCP suite 559 green, extension gate green (22 tests). U3.3 spike: channel files are on disk (`output_logging_<ts>/N-<channel>.log`), so vscode: covers other extensions' channels. Unverified: U1.13 Linux CI job (first PR run); IdeTools DI at runtime; VS Code live smoke for debug and log roots; the vscode:/debug: sources have not run inside VS Code. Not started: phase 4 (Visual Studio: vsout: source). Parent `mcp` pointer bump pending.

## Corrections to the design (verified in repo)
1. Live VS Code ext is `src/Tooling/TokenSaver.VsCodeExt/` (`src/extension.ts`, `ideActions.ts`, `ideBridge.ts`; `scripts/build-vsix.ps1`). `TokenSaver.slnx` points at the stale `TokenSaver.VsCode/TokenSaver.VsCode.Extension`. All TS work targets `TokenSaver.VsCodeExt`.
2. `IdeTools`/`ManagedProcessTools` are NOT registered via `.WithTools<>()` in `ProgramRegistration.cs` (16 registrations), so `IdeGetOutput` may not be exposed over MCP. `LogTools` must be registered explicitly. History: commit 8bc2d80 added `WithTools<IdeTools>`; find where it was dropped (`git log -S"WithTools<IdeTools>" --all`) before U1.14. Existing tests: `src/Host/TokenSaver.MCP.Tests/Tools/IdeToolsCallTests.cs`.
3. `WorkspaceRootResolver` is `internal static` in MCP; Core uses `LogHelperOptions` supplied by the host.
4. No TS test/lint infra: `eslint.config.js` is a CommonJS stub (`module.exports`) inside an ESM package (`"type": "module"`), and package.json has no lint/check/test scripts; needs U3.0 (vitest) and U3.0b (eslint fix). The `package:vsix` script points at a nonexistent `..\..\.\build\scripts\build-vsix.ps1`; the real script is `scripts/build-vsix.ps1` (fix in U3.0b or U4.3).
5. `ToolCoverageTests.Every_McpServerTool_HasATestThatCallsIt` (`src/Host/TokenSaver.MCP.Tests/Tools/ToolCoverageTests.cs`) requires each public instance `[McpServerTool]` method to appear as `.Name(` (whitespace allowed before the paren) in some MCP.Tests `*.cs` file other than ToolCoverageTests.cs; add it in the same commit as the tool. `commands.md` test-coverage paragraph is stale (it names nonexistent `TokenSaver.Library.Tests`).

## Conventions
- Namespaces/folders `TokenSaver.LogHelper.{Contracts,Models,Parsing,Normalization,Filtering,Security,Sources,State,Services}`; tests mirror folders in `src/Core/TokenSaver.LogHelper.Tests/`.
- Test style (from `WslControlToolsTests.cs`): `public sealed class XTests`, hand-written fakes, `Assert.*` with `StringComparison.Ordinal`, temp dirs cleaned in `Dispose`, inject `TimeProvider`.
- Tool style (from `WslControlTools.cs`): `[McpServerToolType] internal sealed class`, `[McpServerTool]`+`[Description]`, `Task<string>`, `CancellationToken ct = default`, `CultureInfo.InvariantCulture`.
- Build output `build/staging/<Project>/`. Unit tests: `dotnet test src/Core/TokenSaver.LogHelper.Tests/... --filter "FullyQualifiedName~<Class>"`. Host: `dotnet test src/Host/TokenSaver.MCP.Tests/... --filter "FullyQualifiedName~LogToolsTests|FullyQualifiedName~ToolCoverageTests"`. Phase end: `$env:ENFORCE_CODE_QUALITY='true'; dotnet build TokenSaver.slnx` then `dotnet test TokenSaver.slnx`.
- Record the red run on the unit line. One commit per unit, push `feat/log-helper`; never push `wip`/`main`. Haiku default; **Sonnet**-marked units need user's yes (Q1).

## Units
**U0.1** Done: branch `feat/log-helper` from `origin/wip` created and pushed; plan saved and committed. Remaining: parent pointer bump per phase (submodule pushed first). **U0.2** Done: read-only Sonnet review folded into this file.

### Phase 1 vertical slice
- **U1.1 Scaffold**: create `src/Core/TokenSaver.LogHelper/` and `src/Core/TokenSaver.LogHelper.Tests/`. Model the test csproj on `TokenSaver.TerminalControl.Tests.csproj` (net10.0, Nullable, ImplicitUsings, bin/obj excludes, xunit 2.9.3, Test.Sdk 18.12.0, runner 3.1.5, NBGV `Update` 3.10.94) but do NOT copy its `TokenSaver.Common.Core` ProjectReference. LogHelper.csproj: net10.0, MEL.Abstractions 10.0.9, NBGV `Update` only. Add `InternalsVisibleTo` for LogHelper.Tests (decided now; affects U1.2+). No Fixtures folder to copy; create `Fixtures/` in the test project when first needed. slnx: folder `/Core/LogHelper/` with both projects; `BuildDependency` for LogHelper in the `TokenSaver.Setup.wixproj` and `TokenSaver.VsCode.Extension.esproj` lists (Core non-test projects only, matching existing lists). Do NOT touch MCP in this unit. Test: `ScaffoldTests` reflects over `GetReferencedAssemblies()` and asserts no AspNetCore/EnvDTE/TokenSaver.MCP refs. Record first `dotnet build` and `dotnet test` (analyzers are `latest-all`).
- **U1.2 Contracts/models**: LogSeverity (not LogLevel), LogEntry, ChannelId (`file:C:\x`, `srv1/syslog:auth`; parse splits on the first `:` after the optional `host/` prefix so drive colons survive; add that case to tests), LogCursor, LogFilterSpec, LogRequestContext, LogQueryRequest/Result (RawChars/ReturnedChars/NextCursor), LogChannelInfo, LogHelperOptions; ILogSource, ILogSourceProvider, ILogService. Tests: ChannelId parse/round-trip/errors; cursor encode/decode, garbage -> invalid not throw.
- **U1.3 Normalizer** (expose `NormalizerVersion` const, stored in snapshot schema for U2.1; hash = SHA-256 of the UTF-8 template, hex prefix; `string.GetHashCode` forbidden): masks timestamps, GUIDs, hex, numbers, durations, paths, ANSI. Tests per mask, same/different template, cross-process stable hash.
- **U1.4 Parser/level detection/folding**: bracketed, MEL console, stack-trace/Python/Java folding, entry-size cap, VS first-chance marker. Tests incl. "0 errors" not Error.
- **U1.5 JSON-lines**: Serilog compact (`@t/@l/@mt/@x`), pino numeric, generic; malformed falls back to plain.
- **U1.6 SafeRegex + LogFilter (Sonnet)**: always NonBacktracking, length cap, reject lookaround/backref with clear error; filter match/exclude/minLevel/category, returns dropped. Catastrophic pattern completes <1s.
- **U1.7 PathGuard (Sonnet)**: GetFullPath, final link target, reject UNC/`\\?\`/ADS/sibling-prefix/`..`/junction escape, no roots = reject all.
- **U1.8 FileLogSource (Sonnet)**: FileShare.ReadWrite|Delete, partial trailing line skipped, cursor only at entry boundary, anchor hash of bytes before cursor -> reset on mismatch, UTF-8/BOM/UTF-16, chunk-split property test (every split == one-shot), concurrent writer, outside-root throws.
- **U1.9 Redactor** (default on): bearer/JWT, key/password, emails, connection strings.
- **U1.10 Template aggregator + SummaryFormatter**: counts, severity ordering (errors survive cap), `maxTokens` (chars/4 unless TokenEconomy estimator found), compact lines, redacted sample.
- **U1.11 LogService facade + golden test**: 1 unique error in 10k noisy lines survives and `Returned < Raw/20`; `AddLogHelper(options)`.
- **U1.12 MCP tools**: `LogTools` (`LogChannels`, `LogQuery`), `.WithTools<LogTools>()` after `InstructionTools`, `AddLogHelperServices` (roots = workspace, state `<ws>\.tokensaver\logs`), 2 `Registry` rows ("Diagnostics"), `ISavingsTracker.RecordAsync`; descriptions cross-ref IdeGetOutput/IdeSearchOutput; fake-based tests.
- **U1.13 Linux CI job** (runs right after U1.1, parallel with U1.2+): new job `loghelper-linux` in `.github/workflows/ci.yml` on ubuntu-latest, `fetch-depth: 0` (NBGV), setup-dotnet 10.0.x; restore/build/test the two LogHelper projects **by path**, never `TokenSaver.slnx` (it includes WiX/esproj). No GitHub feed step: nuget.config lists nuget.org only, and LogHelper must not reference Common.Core or SperryDev.Logger. Existing jobs: `build-and-test` (windows-latest), `installer`, `release`.

### Phase 2 runs
- **U2.1** RunSnapshot + pure RunDiffer (new/gone/count-changed, normalizer-version mismatch = baseline reset, idempotent).
- **U2.2 Snapshot store (Sonnet)**: temp + `File.Move(overwrite:true)` (first write works), per-key SemaphoreSlim, keep last 5, corrupt -> `.corrupt`, sanitized names, parallel writes, no raw lines in state.
- **U2.3** `LogMarkRun`, `since=lastRun|<runId>`.

### Phase 3 VS Code (`TokenSaver.VsCodeExt`)
- **U3.0** Vitest harness (Q4). **U3.1 OutputBuffer (Sonnet)**: partial lines across chunks, keep empty lines, CRLF split, seq numbers, `dropped`; replace `outputLines` in `ideActions.ts`. **U3.2 Debug adapter tracker (Sonnet)**: DAP `output` events per session, session start/end = run boundary, actions `listLogChannels`, `getDebugOutput`. **U3.3 Spike (30 min)**: do other extensions' channels appear in `exthost\output_logging_<ts>\`? **U3.4 Log roots**: manifest `logRoots` from `context.logUri` (Stable/Insiders/VSCodium/portable; remote flagged), `VsInstanceRegistry` reads it. **U3.5 Host sources (Sonnet)** `vscode:`/`debug:` via new `IIdeLogBridge` (does not exist yet); roots validated against known VS Code log patterns; manual smoke.

### Phase 4 Visual Studio
- **U4.1 (Sonnet)** `OutputPaneSlice` (pure, anchored, resets on clear/refill), `listOutputPanes`, ranged `GetOutput` via `EditPoint`. **U4.2** `vsout:` provider (fallback for old extension). **U4.3** rebuild VSIX after commit (NBGV height), smoke.

### Phase 5
- **U5.1 TraceFlagger (Sonnet)** markers + confidence/reason + top-frame grouping + `traces` view. **U5.2** `ignored` view. **U5.3 (Sonnet)** bounded watch `waitSeconds` (cap 25, FakeTimeProvider, cancellation, per-watch dedup).

### Phase 6
- **U6.1 (Sonnet)** SyslogParser (3164 yearless w/ Dec->Jan rollover, 5424 PRI&7, journald JSON). **U6.2 (Sonnet)** SyslogSource: ProcessRunner with `ArgumentList` only, unit names `^[A-Za-z0-9@._-]+$`, journal cursor, not listed on Windows. **U6.3 (Sonnet)** EventLogSource: `System.Diagnostics.EventLog` pkg (must restore and build on the U1.13 Linux job), `[SupportedOSPlatform("windows")]`, bookmark cursor, allow-list (Application, System; Security denied), raw fallback, `.evtx` fixture (scrub names). **U6.4** SinkComparer + `LogSinkCompare` (prune/elevate candidate flags).

### Phase 7
- **U7.1-3** three skills (parallel, `instruction-placement` first; propose-only). **U7.4** docs: `docs/Core/log-helper-contract.md`, CLAUDE.md paragraph, fix `commands.md`, slnx docs entry, CHANGELOG, IdeTools descriptions.

### Phase 8
- **U8.1 (Sonnet)** rotation (rename, copy-truncate, sibling outside root, deleted-while-open). **U8.2** redaction tuning/false-positive corpus. **U8.3 (Sonnet)** response-size cap theory over all views (50 MB input) + regex abuse. **U8.4** route `DevLoopTools` through LogHelper (follow-up by default, Q5). **U8.5** scripted smoke, `build-mcpb.ps1`, `full-gate`, `npm run check`, archive plan, parent pointer, PR per `pr-promotion`.

## Dependencies / parallelism
U1.2 -> {U1.3, U1.4, U1.6, U1.7, U1.9} parallel; U1.5 after U1.4; U1.8 after U1.4+U1.7; U1.10 after U1.3+U1.9; U1.11 after U1.5/1.6/1.8/1.10; U1.13 runs right after U1.1. U2.1 after U1.2+U1.3; U2.2 after U2.1 (+U1.9); U2.3 after U1.11+U1.12+U2.2. U1.12 and U1.14 are serial (both edit `ProgramRegistration.cs`). TS track (U3.0->U3.0b->U3.1->U3.2->U3.4->U3.5), VS track (U4.1), Core track (U2.1-U2.2) independent; U3.5 also needs U2.3; U4.2 needs U3.5. U5.x after U1.11 (serial: shared files). U6.1 after U1.4, U6.3 after U1.2 (touches LogHelper csproj, nothing else concurrently). U6.4 after U6.2|6.3 + U2.3. U7.x after tools. Serial hot files: `LogTools.cs`, `LogService.cs`, `ServiceRegistrationExtensions.cs`, `ProgramRegistration.cs`, `McpContextService.cs`, `ideActions.ts`, `ideBridge.ts`, `TokenSaver.slnx`.

## Risks
Unregistered IdeTools; `ToolCoverageTests`; LocalSystem service (per-user paths wrong, SYSTEM reads anything so PathGuard is the only barrier); bridge manifest in `%ProgramData%` may be user-writable (forged `logRoots`: validate patterns + ACLs); one-line pipe needs response caps; subagents editing the wrong ext folder (name `TokenSaver.VsCodeExt` in every TS brief); Linux restore needs nuget source; NonBacktracking rejects lookarounds (clear errors for IdeSearchOutput users); `.evtx` fixture binary/PII; analyzers `latest-all` (budget fix time); VSIX no-op reinstall without new commit; spike U3.3 may change U3.5; ~17 units Sonnet-tier.

## Answers recorded
- Q1: Sonnet approved for all Sonnet-marked units (parent reviews every diff).
- Q3: branch `feat/log-helper` from `origin/wip`.
- Q4: add vitest **and fix the eslint config** -> new unit **U3.0b** (valid flat `eslint.config.js` for the TS ext, ESM-compatible, `npm run check` runs tsc + eslint + vitest; follow the `lint` skill; Haiku).
- Q2: register `IdeTools` and `ManagedProcessTools` in this plan -> new unit **U1.14** (after U1.12; modifies `ProgramRegistration.cs` and adds/updates tests so `ToolCoverageTests` passes; confirm first why they were unregistered by checking git log/blame, Sonnet for the review of exposure/security since IdeTools drives IDE actions; add `Registry` rows as needed). U1.14 also edits the LogTools descriptions to cross-reference `IdeGetOutput`/`IdeSearchOutput`.
- Defaults kept: Q5 U8.4 is a documented follow-up (not implemented); Q6 stale esproj in slnx left alone.

## Verification
Tests above, raw-vs-returned size comparison, build/gate per TokenSaver `.claude/rules/commands.md` and `packaging.md`, full-gate before PR.
