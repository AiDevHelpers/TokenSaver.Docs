# Codebase review and fix plan

Date: 2026-11-16. Reviewed at: `mcp` @ `a0685a4` (branch `wip`), `TokenSaver` @ `60b38c5`.

## Scope and method

- Reviewed: the `mcp` root repo (config, CI, scripts, docs, `gotcha-*`) and the `TokenSaver` submodule
  (`TokenSaver.MCP` host, Core libraries, Database, AgentHelpers wiring, VS Code extension layout, CI, build props).
- Read in full: `Program.cs`, `ProgramRegistration.cs`, `ServiceRegistrationExtensions.cs`,
  `WorkspaceRootSessionResolver.cs`, `DevLoopTools.cs`, `ContextInterceptMiddleware.cs`, `ManagedProcessRegistry.cs`,
  `DebuggerEndpoints.cs`, both CI workflows, `Directory.Build.props`, `TokenSaver.slnx`.
- Read in part: `PatchEngine.cs`, `TestRunnerService.cs`, `SessionTools.cs`, `CodeHelperTools.cs`,
  `SimpleModelServerInterceptorService.cs`, `DebuggerControlService.cs`, `WorkspaceIndexContextFactory.cs`, both DB
  accessors, `GitStalenessChecker.cs`, `GitRepoWatcherService.cs`, `IdeTestRunService.cs`, `OllamaService.cs`,
  WslControl runners, `AiProviderConfigService.cs`.
- Not reviewed: the `Common` and `SimpleModelServer` submodules, the Visual Studio extension
  (`TokenSaver.Vs.Extension`) beyond grep sampling, `extension.ts` beyond a diff and a grep, the PowerShell scripts'
  bodies, `TokenSaverBehaviorConfig.cs`, LogHelper, TerminalControl, TokenEconomy internals.
- Nothing was built or run. Every finding below was checked by reading the cited source. Where a claim rests on
  behavior I did not execute, it says so.

Severity: **High** = security exposure, data loss, or a default-on wrong result. **Med** = real bug or design
problem with a bounded blast radius. **Low** = hygiene or drift.

---

## Findings

### A. Security

**A1. High. Unauthenticated HTTP server on all interfaces, running as LocalSystem, exposing command execution.**
- `src/Host/TokenSaver.MCP/ProgramRegistration.cs:284`: `app.Run($"http://*:{config.ServerPort}")`. Binds every
  interface. There is no authentication, no Origin or Host check, and no CORS policy anywhere in the host (grep for
  `Authoriz`, `Authentication`, `ApiKey`, `Origin`, `AllowedHosts`, `UseCors` in `src/Host/TokenSaver.MCP` finds
  nothing).
- `src/Installers/TokenSaver.Setup/Service.wxs:47`: the installed service runs as `Account="LocalSystem"`.
- Tools reachable over that endpoint run caller-supplied commands:
  - `Tools/DevLoopTools.cs:339-343` (`run_tests`) and `:383-387` (`lint_fix`): `testCommand` / `lintCommand` are split
    on the first space and executed as-is in a caller-supplied working directory.
  - `Tools/DevLoopTools.cs:152` (`container_exec`): arbitrary `/bin/sh -c` in any container.
  - `Tools/WslControlTools.cs` (`wsl_run`, `wsl_do`): `Core/TokenSaver.WslControl/Core/SessionProcessRunner.cs`
    uses `WTSQueryUserToken` + `CreateProcessAsUserW` to run in the logged-on user's session.
- Impact: any local process, including one running as an unprivileged user, can execute commands as LocalSystem by
  calling `run_tests`. Any network peer can do the same wherever the port is reachable. The WiX project references
  the Firewall extension (`Product.wxs:17`, `TokenSaver.Setup.wixproj:90`) but declares no `fire:` rule, so on a
  default Windows Firewall the service port is probably not reachable from other machines; the dev-loop instance
  and any machine with the firewall off are. The local privilege escalation does not depend on the firewall.
- The code and plans disagree with the behavior: `Middleware/ContextInterceptMiddleware.cs:62` says "this server
  only listens on localhost", and `plans/single-point-db-access.md` records the decision "server binds to 127.0.0.1
  only; no auth token (same as today)". Today it is not loopback-only.

**A2. High. File edit tools are not confined to the workspace.**
- `src/Core/TokenSaver.CodeHelper/Patching/PatchEngine.cs:360-363`: `ResolveAbsPath` returns any rooted path
  unchanged and joins relative paths without normalizing, so `..\..\x` and `C:\Windows\...` both pass.
- `PatchEngine.cs:159-170`: `RollbackAsync` copies a caller-supplied `backupPath` over a caller-supplied target with
  overwrite. It does not check that the source is under the backup folder. This is an arbitrary file copy.
- Combined with A1 this is arbitrary file write as LocalSystem. On its own it lets a confused model edit files
  outside the repo.

**A3. Med. `session_snapshot` / `session_restore` / `build_watch` read and write arbitrary paths.**
- `Tools/SessionTools.cs:58`: `outputPath` is used unchecked; `sessionId` is interpolated into a file name unchecked.
- `SessionTools.cs:97` and `:107`: `session_restore` reads any `snapshotPath`, then reads whatever path that JSON
  names in `full_blob_path`. A crafted snapshot file turns it into an arbitrary file read.
- `Tools/DevLoopTools.cs:435`: `build_watch` reads any `logPath` and returns its content.

**A4. Med. Default-on middleware lets a local model edit files in response to unrelated tool calls.** See B1; it is
listed there because the main problem is design, but the result (unreviewed writes at model-chosen paths) is a
security concern too.

### B. Design and architecture

**B1. High. `ContextInterceptMiddleware` hijacks any tool call that has a `prompt` argument.**
- `Middleware/ContextInterceptMiddleware.cs:167-212`: for every `tools/call` whose tool is not in a six-name skip
  list (`:50`) and whose arguments contain `prompt` (`:181`), the middleware calls
  `SimpleModelServerInterceptorService.TryInterceptAsync`.
- `Core/TokenSaver.CodeHelper/AutoWorkflow/SimpleModelServerInterceptorService.cs:78`: a keyword match
  (`DetectCodeBuildIntent`) plus a one-word classification from the draft model decide whether to "implement". If
  so, the draft model is asked for patch operations from the task text alone, with no file content, and
  `:252` applies them with `PatchEngine.ApplyAsync` at whatever `filePath` the model wrote (unconfined, see A2).
- `CodeHelperConfig.AutoEnabled` defaults to `true` (`Configuration/CodeHelperConfig.cs:27`).
- Tools with a `prompt` argument that are not in the skip list: `manage_plan` (`CodeHelperTools.cs:544`),
  `model_route` (`TokenEconomyTools.cs:68`), `build_adaptive_context` and `analyze_context_segmentation`
  (`AdaptiveContextLoaderTools.cs:65,196`). So an advisory call such as `model_route(prompt: "add a method to X")`
  can end with files edited and the real tool never run.
- No test references `ContextInterceptMiddleware` or `SimpleModelServerInterceptorService` (grep over `*Tests*`).

**B2. High. Workspace root is one process-wide mutable value, shared by all clients.**
- `Services/WorkspaceRootSessionResolver.cs:144-145`: each resolution overwrites the singleton
  `TokenSaverConfig.WorkspaceRoot` and the process environment variable `SIMPLEMODELSERVER_WORKSPACE`.
- Tools call the resolver and then read the global: `CodeHelperTools.cs:108-110` and `:359-361`
  (`string r = root ?? _config.WorkspaceRoot`). Two clients on different repos, which is the normal case for the
  always-on service, race: client A's `edit_file` with a relative path can resolve against client B's root.
- When nothing resolves, `WorkspaceRoot` is `""` (`TokenSaverConfig.cs:89`) and `Path.Combine("", rel)` resolves
  against the process working directory. Tools do not fail fast on an empty root.
- The doc comment at `:110` says "No-op if a workspace root is already known". There is no such early return: every
  tool call repeats the roots request, `EnsureDefaults`, `EnsureSynced` and `BehaviorConfigOverlay.Apply`
  (`:136-171`).

**B3. High. Root resolution through MCP roots cannot work over the HTTP transport as configured.**
- `ProgramRegistration.cs:39` sets `Stateless = true`. The SDK's own XML doc for
  `HttpServerTransportOptions.Stateless` (ModelContextProtocol.AspNetCore 1.4.x) states that in stateless mode
  "all server-to-client requests are also unsupported" and the `/sse` endpoint is disabled.
- `WorkspaceRootSessionResolver.TryResolveViaClientRootsAsync` (`:176-200`) depends on `RequestRootsAsync`, a
  server-to-client request. So over HTTP, which is the only transport the installed service and the VS Code
  extension use, the root comes only from config/env or a per-call `root` argument. Roots can resolve only on stdio.
  I did not run this; it follows from the SDK documentation and the code path.
- The comment at `ProgramRegistration.cs:34` ("Stateless=true allows SSE clients") contradicts the same SDK doc.
- `docs/architecture.md` still describes a cwd fallback that the resolver's own comment (`:132-134`) says was removed.

**B4. Med. MCP debugger tools report success without touching a debugger.**
- `Services/DebuggerControlService.cs:22-60` and onward: sessions, breakpoints, steps and state live in an in-memory
  dictionary. `StartDebugSessionAsync` returns `Success: true` after adding a dictionary entry. No call leaves the
  class (grep for `Http`, `Pipe`, `Bridge` in the file finds nothing).
- The same fake backs the public HTTP surface `/api/debugger/*` (`DebuggerEndpoints.cs`). An agent that calls
  `start_debug_session` / `set_breakpoint` / `execute_step` is told it worked.

**B5. Med. Dead provider auto-registration surface.**
- `src/Common/TokenSaver.Common.Models/AiProviderConfigService.cs:40-85`: `DetectProviders` returns `[]`, both
  update methods are no-ops, kept "so existing callers don't need to change".
- Still wired: `GET /api/register-providers` (`ProgramRegistration.cs:87-110`, a GET that reads `serverExePath` from
  the query string), the `register_mcp_providers` tool, `ProviderAutoRegistrationService` (a hosted service that logs
  one line), `McpRegistrationCheckService`, and the `AutoRegisterProviders` config knob documented in CLAUDE.md.

**B6. Med. Index schema is managed by `EnsureCreated` plus hand-written DDL.**
- `src/Database/TokenSaver.Database.Context/WorkspaceIndexContextFactory.cs:49-141`: `EnsureCreatedAsync`, then about
  ten `CREATE TABLE IF NOT EXISTS` / `ALTER`-style statements that must mirror `OnModelCreating` by hand. There is
  no schema version. Any entity change needs a matching hand edit or old databases silently differ.
- Two accessors open separate long-lived `DbContext`s on the same file with separate locks:
  `Core/TokenSaver.CodeHelper/Indexing/WorkspaceIndexDbAccessor.cs` and
  `Database/TokenSaver.Database.Context/TokenEconomyDbAccessor.cs` (near-identical `GetDbAsync` code). Both key the
  cache by the raw root string, so `F:\x` and `F:\x\` create two contexts. `plans/single-point-db-access.md`
  already targets this.

**B7. Med. Three test-running paths and at least eight process launchers.**
- Test runs: `DevLoopTools.RunTests`, `TestRunnerService` (behind `ITestRunner`), `IdeTestRunService`.
- Hand-rolled process launch: `DevLoopTools.cs:487-513`, `DevLoopTools.cs:173-217`, `TestRunnerService.cs:144-170`,
  `IdeTestRunService.cs:45-65`, `GitStalenessChecker.cs:268-316`, `GitRepoWatcherService.cs:136-162`,
  `OllamaService.cs:302-318`, plus `LanguageHelpers.Core/Process/ProcessRunner.cs` and
  `LogHelper/Sources/ProcessRunner.cs`. They differ in correctness (see C1-C3). Only some use `ArgumentList`.

**B8. Low. Large single files.** `extension.ts` (2,032 lines), `TokenSaverBehaviorConfig.cs` (1,090),
`WorkspaceIndexService.cs` (760), `CodeHelperTools.cs` (712), `LocalModelHelperTools.cs` (696). Tool classes mix
argument parsing, business logic, and formatting.

### C. Bugs

**C1. High. `DevLoopTools.RunProcessAsync` can deadlock and leaks the child on cancellation.**
- `Tools/DevLoopTools.cs:508-510`: reads stdout to the end, then stderr, then waits. A child that fills the stderr
  pipe while stdout is still open blocks forever (`dotnet test`, `dotnet format`, `docker logs` all write to both).
- There is no timeout and no kill. On cancellation `ReadToEndAsync` throws, `using Process` disposes the handle, and
  the child keeps running. `RunDockerExecAsync` in the same file (`:193-216`) does it correctly.
- Used by `run_tests`, `lint_fix`, `diff_summarize`, `container_logs`, and the container start/stop/restart tools.

**C2. High. `TestRunnerService` reports wrong results.**
- `Services/TestRunnerService.cs:166-170`: waits for exit before reading redirected stdout/stderr. Output larger
  than the pipe buffer deadlocks; `dotnet test` output normally is.
- `:131`: passes `--logger json`. `dotnet test` ships `console`, `trx` and `html` loggers; I know of no built-in
  `json` logger, so this should fail every run. Not executed here; confirm with one manual run.
- `:177-182` and `:255`: a non-zero exit with any stdout goes to `ParseTestOutput`, where
  `success = failed == 0`. A build failure or the logger error above parses as zero failed tests and returns
  `Success: true`.
- `:147`: arguments are joined with spaces, so a project path containing a space breaks, and `testName` is not quoted.
- `:158`: the `Process` is never disposed. `failedOnly` is accepted and ignored (`:94-99`).
  `RunTestsViaVisualStudioAsync` (`:190-203`) just calls the command-line path.

**C3. Med. Other process launchers leave stderr unread or have fixed short timeouts.**
- `Core/TokenSaver.Utilities/Services/GitStalenessChecker.cs:279-309`: stderr is redirected and never read; a hard
  5-second timeout kills git and returns `null`, and callers then fall back to mtime with no log line. Large repos
  or chatty stderr (CRLF warnings) degrade staleness detection without any signal.
- `Core/TokenSaver.OllamaIntegration/Services/OllamaService.cs:302-318`: `nvidia-smi` with stderr redirected and
  unread, and no timeout.

**C4. High. Draft-intercepted responses carry the wrong JSON-RPC id.**
- `Middleware/ContextInterceptMiddleware.cs:309`: the response id is the constant `"draft-model-intercepted"`. The
  parsed request (`rpc`) with its real `id` is in scope at the call site (`:212`). JSON-RPC clients match responses
  by id, so a client will not correlate this response with its request. The comment at `:305-308` asserts the
  opposite. This path is on by default (B1).
- `:167` and `:181`: `GetValue<string>()` throws `InvalidOperationException` when `method` or `prompt` is not a
  string, and indexing `rpc["method"]` throws when the body is a JSON array. Only the `Parse` call is guarded.

**C5. Med. `PatchEngine` backups can be overwritten and are not byte-exact.**
- `PatchEngine.cs:352-354`: backup name is `<UTC to the second>_<path with separators replaced by _>`. Two edits to
  the same file in one second, which `ApplyBatchAsync` (`:141-157`) makes likely, write the same name; the second
  overwrites the backup of the original. `a/b_c.cs` and `a_b/c.cs` also collide.
- `:356`: the backup is `ReadAllText` then `WriteAllText`, and the edit itself is `ReadAllText`/`WriteAllText`
  (`:63`, `:112`). A BOM or a non-UTF-8 encoding is not preserved in either, so rollback does not restore the
  original bytes.
- The class doc (`:15-16`) says "Each write is atomic". The write is a direct `WriteAllTextAsync`; a crash mid-write
  truncates the file.

**C6. Med. `session_snapshot` can overwrite its own JSON.**
- `SessionTools.cs:73`: `dest.Replace(".json", ".full.txt")`. If `outputPath` has no `.json`, both writes
  (`:74`, `:81`) go to the same file and the snapshot is replaced by the raw blob; `session_restore` then fails to
  parse it. `Replace` also rewrites `.json` anywhere in the path, including directory names.

**C7. Med. `LogHelperOptions` freezes the workspace root at first use.**
- `Services/ServiceRegistrationExtensions.cs:346-355`: a singleton factory reads `WorkspaceRoot` once. `LogService`
  and `FileLogSourceProvider` are singletons built from it. If the first log tool call happens before a root is
  known (the normal service case, see B3), `AllowedRoots` is empty and `StateDirectory` is null for the life of
  the process, and a later root change is never picked up.

**C8. Low. Shipped agent instructions contain a developer path and wrong tool names.**
- `src/Core/TokenSaver.Docs/Resources/agent.md:7`: tells every client to fall back to `F:\mcp` as the workspace
  root. The same file names tools as `EditFile`, `ManagePlan`, `CodeIndex(action: "find")`; the registered names are
  snake_case (`edit_file`, `manage_plan`, `code_index`).

### D. Error handling

**D1. Med. 45 bare `catch` blocks in non-test code**, several of which hide the cause of a degraded result:
`GitStalenessChecker.cs` (3), `OllamaService.cs` (3), `SuspiciousDirectoryScanner.cs` (4),
`TerminalConfigurationDiscovery.cs` (3), `FolderTreeManager.cs` (2), `CalibrationService.cs` (2),
`Program.cs:302` (`EnsureTokenSaverEventLogSourceExists`). The git and Ollama ones matter most because their
callers silently switch behavior (mtime fallback, "not running").

**D2. Low. Fire-and-forget background work.** `WorkspaceRootSessionResolver.cs:221,251,268` start index, semantic
index, and a 10-minute warm-up with `Task.Run` and no cancellation tied to host shutdown. Exceptions are logged, so
this is a shutdown-latency and lifetime issue, not a silent-failure one.

### E. Tests

**E1. Med. No test references these types** (grep over all `*Tests*` paths): `PatchEngine`, `RollbackAsync`,
`ContextInterceptMiddleware`, `SimpleModelServerInterceptorService`, `DebuggerControlService`,
`AnthropicAgentAdapter`, `QwenAgentAdapter`. The file-writing path and the default-on interception path are the
two riskiest pieces of the server and have no direct coverage. (`PatchEngine` may be exercised indirectly through
`CodeHelperToolsTests`; I did not trace that.)

**E2. Med. Orphaned test sources.** `src/Core/TokenSaver.Common.Core.Tests/Contracts/*.cs` (4 files, 8 test
attributes) have no tracked `.csproj` and are not in `TokenSaver.slnx`. They are never compiled.

**E3. Low. CI does not run the extension gate.** `TokenSaver/.github/workflows/ci.yml` has no `npm` step, so
`npm run check` (lint + vitest, `VsCodeExt/package.json:19-21`) runs only locally.
`.claude/rules/commands.md` describes it as "the lint and test gate".

### F. Build, CI and repo hygiene

**F1. Med. A stale fork of the VS Code extension is tracked and is the one in the solution.**
- `src/Tooling/TokenSaver.VsCode/TokenSaver.VsCode.Extension/` holds an older `extension.ts` (2,040 lines; 194 diff
  lines against the live one, missing the IDE bridge). It last changed in "WIP"/merge commits.
- `TokenSaver.slnx` references this `.esproj`. The live `src/Tooling/TokenSaver.VsCodeExt/TokenSaver.VsCodeExt.esproj`
  is the only project file not in the solution, while scripts (`build-vsix.ps1:31`), CLAUDE.md and the root
  `.vscode/tasks.json` all use `VsCodeExt`.

**F2. Med. Build output and packages are committed.**
- Both extension folders track `TokenSaver.MCP.exe`, `testhost.exe`, `testhost.dll`, `xunit.*.dll`,
  `*.deps.json`, `*.runtimeconfig.json`.
- `packages/Nerdbank.GitVersioning.3.10.91/` (43 files, about 25 MB of native libgit2 binaries) is tracked, and is
  not the version in use (`Directory.Build.props` pins 3.10.94).
- Also tracked: `Backup/TokenSaver.slnx`, `archive/backup-old1|2/TokenSaver.slnx`, `UpgradeLog.htm`,
  `build/u1.err`, `build/u1.out`, tokenizer blobs under `docs/retrieval-benchmark/models/` (2.7 MB + 1.6 MB).

**F3. Med. The root repo's CI never runs.** `mcp/.github/workflows/build-and-test.yml` triggers on `master`/`main`
only. The remote has `wip` and `instr-index`; `origin/HEAD` is `wip`. If it did run, `dotnet restore
TokenSaver/TokenSaver.slnx` has no step adding the GitHub Packages source that TokenSaver's own CI needs
(`ci.yml` "Add TokenSaver.Common NuGet source").

**F4. Low. Quality gate described but not enforced.** `.claude/rules/commands.md` says set
`ENFORCE_CODE_QUALITY=true` "to reproduce CI strictness". `TokenSaver/.github/workflows/ci.yml` never sets it. Only
the root workflow does, and it does not run (F3).

**F5. Low. Non-reproducible local restore.** `Directory.Build.props:6` floats `SperryDev.Logger` at `0.*-*` locally
while `ci.yml:30` pins `0.1.12-gf10ffa299f` after the float broke the build on 2026-11-15. The props comment
(`:3-5`) still says CI sets floating ranges. `global.json` pins only the WiX SDK, not the .NET SDK.

**F6. Low. Root docs point at files that do not exist.**
- `mcp/CLAUDE.md` says "two submodules" and lists one; `.gitmodules` has three (`TokenSaver`, `Common`,
  `SimpleModelServer`). `README.md` says two.
- `.claude/rules/build.md`, `README.md` and `.vscode/tasks.json` reference `build\scripts\setup.ps1`,
  `build\scripts\compose-vsix.ps1`, `build/scripts/build-mcpb.ps1`. The root has no `build/` directory and none is
  tracked. The root `.gitignore` contains `[Bb]uild/`, which would have ignored it.
- `mcp/CLAUDE.md` links `docs/folder-index.md`; the file does not exist, so by the rule in
  `.claude/rules/instructions.md` the `folder-index` health check reports Degraded.

**F7. Low. TokenSaver docs drift.**
- `TokenSaver/CLAUDE.md` cites `docs/config-behavior-contract.md`, `docs/tokensaver-mcp-health-contract.md`,
  `docs/token-economy-tools-contract.md`. They live under `docs/Host-MCP/` and `docs/Core/`. `TokenSaver.slnx`
  lists the same dead paths plus `docs/retrieval-design.md` and `todo.md`, which do not exist.
- CLAUDE.md and `docs/architecture.md` describe `TokenSaver.Library` in the dependency chain; no such project exists.
- `TokenSaver/.claude/mcp.json` points at ports 3010/3020; the server listens on 11436.
- `ServiceRegistrationExtensions.cs:335-343`: the WslControl summary is attached to `AddLogHelperServices`.

**F8. Low. Root repo layout.** `gotcha-db/`, `gotcha-ingest/`, `gotcha-mcp/` are plain tracked folders in a repo
that CLAUDE.md says has "no application source of its own". `gotcha-db/.github/workflows/validate.yml` is nested,
so GitHub never runs it. `gotcha-mcp/src/*` holds only `.gitkeep`. Plans live in both `plans/` and `docs/plans/`.
`scripts/git/GitHelpers.psm1:8,35,96` protects `main`/`dev` and defaults the base to `main`; neither repo's remote
has a `main` branch, and `wip` (the actual trunk) is not protected.

---

## Fix plan

Units are ordered. Each is sized to be one PR in `TokenSaver` (plus a pointer bump in `mcp`) unless it says root.

### Quick wins

**Q1. Bind to loopback only.**
- Scope: `ProgramRegistration.cs:284`, `Program.cs:126-128` comment, `ContextInterceptMiddleware.cs:62` comment.
- Approach: listen on `http://127.0.0.1:{port}` and `http://[::1]:{port}`. Add a `BindAddress` config knob only if
  open question 1 says a non-loopback client exists.
- Risk: breaks any client that reaches the server from WSL2 (NAT mode) or a container. See open question 1.
- Verify: `netstat -ano | findstr 11436` shows only loopback listeners; `/health` answers on `localhost` and
  `127.0.0.1` (see `docs/pitfalls.md` on the localhost/127.0.0.1 hang); a request to the LAN address is refused.
- Depends on: nothing.

**Q2. Fix the JSON-RPC id and harden parsing in the intercept middleware.**
- Scope: `ContextInterceptMiddleware.cs:160-185`, `:278-310`; new `ContextInterceptMiddlewareTests`.
- Approach: pass `rpc["id"]?.DeepClone()` to the response writer; return a pass-through when the body is not a JSON
  object or `method`/`name`/`prompt` are not strings. Becomes moot for the handled branch if R4 removes it, but the
  parsing fix stays.
- Risk: low.
- Verify: unit tests with numeric id, string id, array body, non-string `prompt`.
- Depends on: nothing. Superseded in part by R4.

**Q3. Fix process deadlocks and leaks in place.**
- Scope: `DevLoopTools.cs:487-513`, `TestRunnerService.cs:144-188`, `GitStalenessChecker.cs:268-316`,
  `OllamaService.cs:302-318`.
- Approach: read stdout and stderr concurrently, then wait; kill the process tree on cancellation or timeout;
  dispose the `Process`; log when git times out instead of returning `null` silently. Copy the shape already in
  `DevLoopTools.RunDockerExecAsync` / `IdeTestRunService`.
- Risk: low. Behavior change: cancelled calls now kill the child.
- Verify: a test that runs a child writing 1 MB to stderr then stdout completes; a cancelled call leaves no child
  (check with `process_list`).
- Depends on: nothing. R5 later replaces these with one runner.

**Q4. Make `TestRunnerService` tell the truth.**
- Scope: `TestRunnerService.cs:131-147`, `:177-182`, `:226-267`; `TestRunnerServiceTests`.
- Approach: use `ArgumentList`; replace `--logger json` with a TRX logger and reuse `IdeTestRunService.ReadSummary`,
  or delete this path in favor of `IdeTestRunService` if open question 5 allows; `Success` requires exit code 0.
- Risk: low.
- Verify: a failing build returns `Success: false`; a project path with a space runs.
- Depends on: Q3 (same lines).

**Q5. Make `PatchEngine` backups unique and byte-exact; make the write atomic.**
- Scope: `PatchEngine.cs:109-117`, `:345-358`; new `PatchEngineTests`.
- Approach: backup with `File.Copy` to `<timestamp with ms>_<short guid>_<name>`; write to a temp file in the same
  directory and `File.Replace`/`Move`; detect and keep the original encoding and BOM.
- Risk: low to medium. Encoding preservation needs tests with BOM, UTF-16 and CRLF files.
- Verify: two edits in one batch produce two backups; rollback output is byte-identical to the original.
- Depends on: nothing.

**Q6. Fix `session_snapshot` path handling.**
- Scope: `SessionTools.cs:55-82`.
- Approach: build the blob path with `Path.ChangeExtension`; reject a `sessionId` with path characters. Path
  confinement itself comes in R2.
- Risk: low.
- Verify: `outputPath` without `.json` round-trips through `session_restore`.
- Depends on: nothing.

**Q7. Resolve `LogHelperOptions` per use.**
- Scope: `ServiceRegistrationExtensions.cs:344-369`.
- Approach: give `LogService`/`FileLogSourceProvider` a root accessor (`Func<string>` or the workspace context from
  R3) instead of a frozen options object.
- Risk: low.
- Verify: start with no root, resolve a root, then `log_channels` lists workspace logs.
- Depends on: nothing; simplified by R3.

**Q8. Remove committed binaries and stray files (TokenSaver).**
- Scope: `git rm --cached` for the exe/dll/deps/runtimeconfig files under both extension folders,
  `packages/`, `Backup/`, `archive/backup-old*`, `UpgradeLog.htm`, `build/u1.*`; extend `.gitignore`.
- Approach: untrack, then confirm `build-vsix.ps1` regenerates what the VSIX needs. History rewrite is a separate
  decision (open question 7).
- Risk: medium if a script relies on the tracked binaries being present on a fresh clone.
- Verify: fresh clone, `scripts/build-vsix.ps1` produces a working VSIX; CI green.
- Depends on: nothing; do before R6 so the fork deletion is a small diff.

**Q9. CI corrections.**
- Scope: `TokenSaver/.github/workflows/ci.yml`; `mcp/.github/workflows/build-and-test.yml`;
  `src/Core/TokenSaver.Common.Core.Tests/`.
- Approach: add `npm ci && npm run check` for `VsCodeExt`; set `ENFORCE_CODE_QUALITY` in CI or change the rule text
  (open question 6); add a `.csproj` for the orphaned contract tests and put it in the solution, or delete them;
  fix or delete the root workflow (open question 8).
- Risk: turning on warnings-as-errors may fail the build on existing warnings; do it in its own PR.
- Verify: CI runs the vitest suite and the contract tests; a deliberate warning fails the build if enforcement is on.
- Depends on: nothing.

**Q10. Documentation and config drift.**
- Scope: `TokenSaver/CLAUDE.md`, `docs/architecture.md`, `TokenSaver.slnx` solution-items, `agent.md`,
  `.claude/mcp.json`, `Directory.Build.props` comment, `ProgramRegistration.cs:33-34`,
  `ServiceRegistrationExtensions.cs:335-343`; root `CLAUDE.md`, `README.md`, `.claude/rules/build.md`,
  `.vscode/tasks.json`; generate `docs/folder-index.md`.
- Approach: correct paths and names; remove `F:\mcp` from `agent.md` and use the registered snake_case tool names;
  pin `SperryDev.Logger` in the props to the CI version. Use the `instruction-placement` skill for the CLAUDE.md
  and rule edits.
- Risk: low. `agent.md` is sent to every client; keep the change minimal.
- Verify: every path cited in CLAUDE.md and the solution exists; `/health` reports `folder-index` Healthy.
- Depends on: open question 9 for the root `build/scripts` references.

### Larger refactors

**R1. Trust boundary for the HTTP endpoint.**
- Scope: `ProgramRegistration.cs`, new auth middleware, `Service.wxs`, VS Code extension and VS extension clients,
  install prompts under `install-clients/`.
- Approach: require a per-install bearer token (generated at install, ACL'd file under `%ProgramData%\TokenSaver`,
  readable by the interactive user) on `/mcp` and `/api/*`; reject requests with a non-loopback `Host` or a
  browser `Origin`; run the service under a least-privilege account instead of LocalSystem if WSL session launch
  (`WTSQueryUserToken` needs `SeTcbPrivilege`) allows it. Health endpoints can stay open.
- Risk: high. Every client config changes; `WTSQueryUserToken` may force LocalSystem, in which case the token and
  R2's command restrictions carry the weight.
- Verify: unauthenticated `tools/call` returns 401; an unprivileged second user cannot call tools; all listed
  clients connect after re-running the install prompt.
- Depends on: Q1. Needs open questions 1 and 2.

**R2. Workspace confinement and command allowlist.**
- Scope: new `WorkspacePathGuard` (Core); `PatchEngine`, `SessionTools`, `DevLoopTools` (`build_watch`,
  `diff_summarize`, `run_tests`, `lint_fix`), `CodeHelperTools` rollback, `LanguageHelperTools.cs:159`.
- Approach: one function that full-paths, resolves links, and requires the result to be under the workspace root
  (or the backup folder for rollback sources); return a tool error otherwise. Restrict `testCommand`/`lintCommand`
  to an allowlist of executables from behavior config (default `dotnet`, `npm`, `pytest`, ...), passed through
  `ArgumentList`.
- Risk: medium. Users who point tools at paths outside the repo lose that; make the allowlist configurable.
- Verify: tests for `..`, absolute, UNC, and junction escapes on each tool; `run_tests` with `cmd /c ...` is refused.
- Depends on: R3 for a trustworthy root (can ship first using the per-call `root`). Needs open question 3.

**R3. Per-request workspace context.**
- Scope: `WorkspaceRootSessionResolver`, `TokenSaverConfig.WorkspaceRoot` and every reader (tools, middleware,
  `LogHelperOptions`, `BehaviorConfigOverlay`, `InstructionOptimizerService`), `Stateless` setting.
- Approach: stop writing to the singleton. Resolve a `WorkspaceContext` per call from, in order: explicit `root`
  argument, a client-supplied header or query on the MCP URL (HTTP), MCP roots (stdio or stateful HTTP), configured
  default. Tools receive it as a parameter and fail with a clear message when it is empty. Cache per-root setup
  (`EnsureDefaults`, sync, overlay) so it runs once per root, not once per call. Decide stateless vs stateful
  (open question 4).
- Risk: high. Touches every tool class and the behavior-config overlay, which is also global today.
- Verify: integration test with two clients on two temp repos calling `edit_file` concurrently; no cross-writes.
  A call with no root returns an error and writes nothing.
- Depends on: none strictly; do after Q-units. R2, Q7 and R7 get simpler after it.

**R4. Redesign or remove draft interception.**
- Scope: `ContextInterceptMiddleware`, `SimpleModelServerInterceptorService`, `CodeHelperConfig.AutoEnabled`,
  `config-behavior-contract.md`, extension env var `TOKENSAVER_TokenSaver__CodeHelper__AutoEnabled`.
- Approach (recommended): the middleware never applies patches. Keep context cleaning (`AutoIntercept`) as an
  allowlist of tools that opt in. Draft implementation stays reachable only through the explicit `code_work` tool,
  which already exists and is in the skip list. Default `AutoEnabled` to false if any automatic path remains.
- Risk: medium. Changes a documented default; update the contract doc and tests in the same PR, per CLAUDE.md.
- Verify: `model_route` and `manage_plan` with a code-like prompt reach their own handlers and modify no files.
- Depends on: Q2. Needs open question 5.

**R5. One process runner, one test path.**
- Scope: the launch sites listed in B7; `ITestRunner`, `TestRunnerService`, `IdeTestRunService`, `DevLoopTools.RunTests`.
- Approach: move a single runner (argument list, concurrent drain, timeout, kill tree, registry tracking, output
  cap) to a Core project and use it everywhere. Keep one test implementation (TRX-based) behind `ITestRunner`.
- Risk: medium; wide but mechanical.
- Verify: existing tool tests pass; grep finds `new ProcessStartInfo` only in the runner and the WSL session runner.
- Depends on: Q3, Q4.

**R6. Remove dead and fake surfaces.**
- Scope: `AiProviderConfigService`, `/api/register-providers`, `register_mcp_providers`,
  `ProviderAutoRegistrationService`, `McpRegistrationCheckService`, `AutoRegisterProviders`;
  `DebuggerControlService` and its tools/endpoints; `src/Tooling/TokenSaver.VsCode/`; `TokenSaver.slnx`.
- Approach: delete the provider stubs and the stale extension fork; point the solution at `VsCodeExt.esproj` with
  the same `BuildDependency` list (CLAUDE.md gotcha: preserve that ordering). For the debugger: either route the
  tools through the IDE bridge (`IdeInstanceRouter`) or remove them and the endpoints.
- Risk: medium. Public tool names disappear; `ToolCoverageTests` and contract docs change with them.
- Verify: solution builds in VS and with `dotnet build`; no WiX build race; tool list matches the contract docs.
- Depends on: Q8. Needs open question 5.

**R7. Database access and schema versioning.**
- Scope: `WorkspaceIndexContextFactory`, both accessors, `ChunkSchemaRecovery`.
- Approach: fold into the existing `plans/single-point-db-access.md` work. Add `PRAGMA user_version`; on mismatch
  rebuild the index (it is a cache) instead of patching with hand DDL; one accessor, one lock per root, key
  normalized with `Path.GetFullPath` + trimmed separator.
- Risk: medium; a version bump forces a full reindex for users.
- Verify: open a database from an older build; it is rebuilt and tools work. Two spellings of one root share a context.
- Depends on: R3 helps. Coordinate with the existing plan rather than running both.

**R8. Tests for the risky paths.**
- Scope: new tests for `PatchEngine` (all four operations, rollback, encoding), the intercept middleware,
  `WorkspaceRootSessionResolver`, one test per AgentHelpers adapter.
- Approach: write alongside Q2, Q5, R3, R4 (TDD per the repo's skill); this unit covers what those leave.
- Risk: low.
- Verify: coverage for the named types; CI green.
- Depends on: follows the units above.

**R9. Root repo cleanup.**
- Scope: `gotcha-*`, `plans/` vs `docs/plans/`, `scripts/git/GitHelpers.psm1`, `.gitmodules` docs.
- Approach: per open questions 8-10.
- Risk: low.
- Depends on: answers.

**R10. Split the large files.** `extension.ts` first (commands, service control, MSI install, health polling into
modules), then tool classes. Low priority; do opportunistically when a unit above already touches the file.

### Order and dependencies

```
Q1 -> R1
Q2 -> R4
Q3 -> Q4 -> R5
Q5, Q6, Q7            (independent)
Q8 -> R6
Q9, Q10               (independent; Q10 waits on question 9 for root docs)
R3 -> R2, R7          (R2 can start earlier using the per-call root)
R8 runs alongside; R9, R10 last
```

Suggested sequence: Q1, Q3, Q4, Q2, Q5, Q6, Q8, Q9, Q10, Q7, then R4, R3, R2, R1, R5, R6, R7, R8, R9, R10.

---

## Open questions

1. Does any client reach the server from outside loopback (WSL2 in NAT mode, a container, another machine)? This
   decides whether Q1 is a plain loopback bind or needs a configurable bind address plus R1 first.
2. Must the service stay LocalSystem (the WSL runner uses `WTSQueryUserToken`), or can it move to a lower-privilege
   account? Is a per-install bearer token acceptable given every client config has to carry it?
3. For `run_tests` / `lint_fix`: allowlist of executables, or remove the free-form command argument?
4. Stateless HTTP was chosen deliberately. Keep it and pass the workspace root from the client explicitly, or switch
   to stateful sessions so MCP roots work?
5. Draft interception, the debugger tools, and the provider-registration tools: remove, or keep and finish? Removing
   them deletes public tool names and endpoints.
6. Should CI enforce warnings-as-errors (`ENFORCE_CODE_QUALITY=true`), or should the rule text stop claiming it does?
7. After untracking the binaries and `packages/`, rewrite history to drop them, or leave history as is?
8. Root CI workflow: retarget to `wip` (and add the package-source step) or delete it, given each submodule has its
   own CI?
9. The root `build/scripts/*.ps1` files referenced by README, rules and tasks: were they lost to the `[Bb]uild/`
   ignore rule and should be restored, or are they gone and the references should be deleted?
10. Which branch is the trunk? Global instructions say `main`; both remotes use `wip` and have no `main`, and
    `GitHelpers.psm1` protects `main`/`dev` only.
11. Should `gotcha-db`, `gotcha-ingest`, `gotcha-mcp` move to their own repos/submodules, and which of `plans/` and
    `docs/plans/` is the plan folder?
12. `Common` and `SimpleModelServer` were not reviewed. Include them in a follow-up pass?

## Decisions (user, 2026-11-16)

- Q1 bind scope: loopback only (127.0.0.1).
- R1 auth: per-install bearer token + Origin/Host check; service stays LocalSystem.
- R2 commands: executable allowlist for run_tests / lint_fix.
- R3 workspace root: switch to stateful sessions so MCP roots resolve (drop `Stateless = true`).

- Q5 dead surfaces: keep and finish all (draft interception, debugger, provider registration). R4/R6 become "finish", not "remove".
- Q6 CI: enforce npm check and ENFORCE_CODE_QUALITY.
- Q7 history: leave as is; untrack going forward only.
- Q8 root CI: retarget to wip and add the package-source step.
- Q9 root scripts: delete references to the missing build/scripts; fix .gitignore.
- Q10 trunk: create `main` on the remotes and branch from it.
- Q11 layout: keep gotcha-* in place; docs/plans is the plan folder (merge plans/ into it).
- Q12: Common and SimpleModelServer out of scope.

## Progress

- Q1 done: TokenSaver branch `fix/loopback-bind` (94c3a4c). Verified 127.0.0.1 and ::1 listen, /health 200, LAN address refused.
- Q3 + Q4 done: TokenSaver branch `fix/process-runners` (stacked on fix/loopback-bind). MCP.Tests 567 pass. No new unit tests (the runner shells out to dotnet); verify by running run_tests on a failing project.
- Q2 done: TokenSaver branch `fix/intercept-jsonrpc` (stacked). 9 new tests pass; tests were written after the code, no red run.
- Branch stack: fix/loopback-bind -> fix/process-runners -> fix/intercept-jsonrpc. Next: Q5, Q6, Q8, Q9, Q10, Q7.
- Q5 done: TokenSaver branch `fix/patchengine-backups` (stacked). 6 PatchEngine tests; a flaky File.Replace lock was found and fixed with a retry.
- Q6 done: TokenSaver branch `fix/session-snapshot-paths` (stacked). 3 new tests.
- Q8 done: TokenSaver branch `chore/untrack-binaries` (stacked). 75 files untracked; MCP builds clean. Not done: fresh-clone build-vsix check (R6 deletes the stale extension fork next).
- Q9 done (TokenSaver branch `chore/ci-corrections`, stacked): ENFORCE_CODE_QUALITY on in CI, npm run check job added, enforced Release build verified at 0 warnings, LogHelper 178 and MCP 580 tests pass. Common.Core contract tests deleted (dead). Root workflow retargeted to wip with the package-source step (not run on GitHub). Open: VSEXT0010 is suppressed, needs a real check that the VS extension loads on VS 18 (.NET target).
- Q10 done: TokenSaver branch `docs/drift-fixes` and root branch `docs/root-drift-fixes` (stacked). Contract doc paths, dependency chain, mcp.json ports (11436/11435, /mcp), slnx doc items, Logger pin, root README/CLAUDE.md/build.md/tasks.json references fixed; docs/folder-index.md generated. Not done: root .gitignore `[Bb]uild/` left (harmless now that nothing references root build/); `/health` folder-index check not confirmed; agent.md (F:\mcp path, tool names) not touched yet.
- Q7 done: TokenSaver branch `fix/loghelper-late-root` (stacked). 2 new tests; LogHelper 180 and MCP 580 pass; enforced build clean. All Q units done except the agent.md part of Q10. R units next (R3 first per the dependency order: R4, R3, R2, R1, R5...).
- R4 done: TokenSaver branch `fix/draft-intercept-advisory` (stacked). Middleware is allowlist-only (`build_adaptive_context`), advisory-only (`TryAdviseAsync`, no patching, no response), honors Calibration toggle; `AutoEnabled` defaults to false; contract doc updated. MCP 592 tests pass, enforced build clean. `code_work` stays the explicit write path. Note: the old `TryInterceptAsync`/`ImplementWithGuidanceAsync` are now uncalled; R6 decides whether to wire or remove them.
- R3 done: TokenSaver branch `fix/session-workspace-root` (stacked on fix/draft-intercept-advisory). Stateful HTTP; per-request `WorkspaceScope` seeded from `WorkspaceSessionRoots`; `TokenSaverConfig.WorkspaceRoot` answers per session, so the ~70 existing readers needed no edits. Two-client integration test over a real stateful host passes; MCP 598 tests, enforced build clean. Not done: tools still do not fail on an empty root (moves to R2's path guard); `BehaviorConfigOverlay` still last-resolved-wins and `SIMPLEMODELSERVER_WORKSPACE` is process-wide; not run against a real VS Code/Claude client; stdio mode has no scope (single client, last-resolved root).
- R2 done: TokenSaver branch `fix/path-and-command-confinement` (stacked on fix/session-workspace-root). `WorkspacePathGuard` (links/junctions followed) on PatchEngine apply and rollback (backup source must be under BackupPath), session_snapshot/restore incl. stored full_blob_path, build_watch, diff_summarize, run_tests/lint_fix working dir, check_code/fix_code; empty root is an error. `CommandAllowlist` (config `AllowedCommands`, default dotnet/npm/pytest/...) for run_tests/lint_fix. MCP 611, CodeHelper 71, Utilities 43 tests pass, enforced build clean; tests written after code (no red run). Not covered: container_exec, wsl_run/wsl_do, other tools that take paths but were not in the plan list; allowed tools like npm/dotnet can still run project scripts.
- R1 done: TokenSaver branch `fix/endpoint-auth` (stacked on fix/path-and-command-confinement; built in a separate worktree because the TokenSaver checkout was on the user's feature/vs-inproc-port). `EndpointAuthMiddleware` (Host loopback, no Origin, bearer token; /health open), `AuthTokenStore` (token file ACL: SYSTEM, Administrators, creator, "TokenSaver Users"), netapi32 group management + `/api/auth/users`; VS Code ext (auth.ts, Manage Users, Copy Auth Token), VS ext Users card, WiX group creation + installing user, install prompts. Verified live: no/bad token 401, good 200, Origin/bad Host 403, /health 200; MCP 651, VsCodeExt 31, Vs.Extension 38 tests. Also fixed a Q9 bug: the vscode-ext CI job used `npm ci` with a gitignored lockfile. Not done: MSI install/uninstall not run; the VS extension Users card and VS Code picker not exercised in a real IDE; the service still runs as LocalSystem (WTSQueryUserToken); stdio transport unauthenticated by design; the group's members can read the token. Merge conflicts to expect with feature/vs-inproc-port in SettingsViewModel.cs, TokenSaverToolWindowContent.xaml.
- R5 partly done: TokenSaver branch `fix/process-runner` (stacked on fix/endpoint-auth). `CommandRunner` + `CommandLine` in Common.Core/Processes (concurrent drain, timeout, tree kill, output cap, OnStarted registry hook); migrated DevLoopTools, TestRunnerService, IdeTestRunService, GitStalenessChecker, GitRepoWatcherService, OllamaService GPU probe, LanguageHelpers ProcessRunner. Utilities 60, CodeHelper 71, LogHelper 180 pass; MCP 649/650 (the failure is environmental: a stray C:\Users\rsper\AppData\Local\Temp\new.slnx created 10:00 today makes WorkspaceRootResolverTests.FindRepoRoot_NoMarkerAnywhereInIsolatedTree find a marker above %TEMP%). Not done: (1) the grep goal is not met: LogHelper keeps its own runner (ScaffoldTests forbids a Common reference), and long-lived or interactive launchers (IDEs, terminals, VS extension, Client.Helpers service/lifecycle helpers) were left; (2) "one test path": TestRunnerService still parses console output while IdeTestRunService reads TRX, they now share the runner but not the result model.
- R6 part 1 done: TokenSaver branch `fix/ide-debugger-bridge` (stacked on fix/process-runner). `DebuggerControlService` forwards to the real IDE debugger over the existing named-pipe bridges (new `IIdeBridge`; router gets an IDE filter), failures carry the IDE's reason, conditions/hit counts/Pause/Restart are refused; VS Code `step` now accepts `mode` (it only read `kind` while the MCP tool sends `mode`); stale `src/Tooling/TokenSaver.VsCode` deleted and `TokenSaver.slnx` points at `TokenSaver.VsCodeExt.esproj` (whole solution builds, 0 errors); 14 tests. Not done: debug state has no file/line, call stack or variables; not run against a live VS/VS Code window; npm audit reports high advisories in the extension's devDependencies (typescript-eslint, tinyglobby) via the esproj build.
- R6 part 2 (providers) held. Why client config writing was unreliable (from the repo and this machine, no recorded reason exists: the stub is in the initial commit): formats differ (VS Code mcp.json root `servers` and JSONC; Claude Code/Cursor/Cline `mcpServers` JSON; Continue YAML or JSON; Sixth needs `disabled:false`); `~/.claude.json` is 194 KB and rewritten by Claude Code itself, so a second writer races it; Claude Desktop may live under an MSIX virtualized path; the entry now also needs an `Authorization` header (token) after R1. Official CLIs (`claude mcp add`, `code --add-mcp`) exist for some clients. Waiting for the decision between generate-only snippets, CLI-assisted, full writers, or removal.
- R6 part 2 done (user chose: regenerate the configs, record why they are unreliable, debug): TokenSaver branch `fix/provider-config-writer` (stacked on fix/ide-debugger-bridge). `AiProviderConfigService` writes the entry into installed clients (VS Code, Claude Code, Cursor, Continue own file, Cline, Sixth) on request only; `JsonConfigEditor` refuses JSONC/invalid files, keeps BOM/newlines/number text/key order, re-reads before the swap, backs up, replaces atomically, verifies; reasons and limits in docs/Host-MCP/provider-config-reliability.md. Debugged on copies of real configs: found and fixed LF files being rewritten as CRLF (would have changed every line of a 5,600-line ~/.claude.json); saw ~/.claude.json change size between runs (Claude Code rewrites it). 22 tests on a temp profile. Not done: not verified against the real clients after a write (restart + connect); the last-instant race with Claude Code remains; Claude Desktop unsupported; `/api/register-providers` is now a POST.
- R7 done: TokenSaver branch `fix/db-schema-versioning` (stacked on fix/provider-config-writer). `WorkspaceIndexContextFactory.SchemaVersion` in PRAGMA user_version; an index with tables but another version (including 0 = pre-versioning) is deleted with its WAL/SHM and rebuilt on open (a cache: full reindex, no migration). Hand DDL for Chunks/TokenSavings/indexes/ALTERs removed (EF model builds them); folder_overview kept. `NormalizeRoot` keys both accessors' context caches. Tests: 10 new schema tests; CodeHelper 79, TokenEconomy 84, MCP 695 pass; enforced build clean. Not done: the per-root lock (one lock per accessor remains; WithDbLockAsync has no root parameter); the two accessors are not merged (circular reference); ChunkSchemaRecovery is still called from the semantic trigger and is now largely redundant; the schema bump forces every user's index to rebuild on first start.
