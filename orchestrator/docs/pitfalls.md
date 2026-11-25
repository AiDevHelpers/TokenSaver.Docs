# Known Pitfalls

Root causes for bugs that took more than 2 attempts to resolve, so the next person (or agent) hits
the same symptom and finds the real cause on the first try instead of re-deriving it. See the
"When a bug takes more than 2 tries to resolve" section in `CLAUDE.md` for the rule on adding new
entries here.

## Windows Installer (WiX/MSI) and Windows Services

### `msiexec /qn` does not show a UAC prompt — it just fails with error 1925
Code that shells out to `msiexec.exe /i ... /qn` from a non-elevated process (e.g. a VS Code
extension's `execFile("msiexec.exe", ...)`) will NOT trigger a UAC elevation dialog, even though
Windows Installer is a system service. `/qn` (quiet, no UI) suppresses *all* UI, including the
elevation prompt itself — with nothing to show, there's nothing for the user to click "Yes" on,
so an unelevated caller installing a `perMachine` MSI just gets error 1925 ("insufficient
privileges"), silently, with no dialog ever appearing. Symptom: installer fails, user reports "no
UAC appeared." Fix: shell out through `powershell -Command "Start-Process msiexec.exe -ArgumentList @(...) -Verb RunAs -Wait -PassThru"` instead of invoking `msiexec.exe` directly — `Start-Process
-Verb RunAs` genuinely triggers UAC regardless of the child command's own `/qn` flag. See
`TokenSaver.VsCodeExt/src/extension.ts`'s `runMsiexec()`.

### Concurrent `dotnet build`/MSBuild processes cause intermittent, hard-to-reproduce WiX cabinet failures
Symptoms: `WIXBUILD : error 0x80070002: failed to compress cabinet: ...#cab1.cab` and/or
`WixNativeException: wixnative.exe failed ... The system cannot find the file specified`, even
though the referenced files genuinely exist and `wixnative.exe` runs fine standalone. Root cause:
leftover reused MSBuild worker nodes (`dotnet build-server`, `nodeReuse:true`) plus multiple
overlapping build invocations (e.g. a CLI build running while Visual Studio is also mid-build)
racing to read/write the same `obj\` and `build\staging\` directories — one process's file gets
rewritten or locked mid-read by another. This is NOT a code or `.wxs` bug; re-running the exact
same build after simply waiting can "fix" it, which is a strong tell. Real fix: close other IDEs/
terminals driving a build of the same project, run `dotnet build-server shutdown`, kill any
leftover `dotnet`/`MSBuild`/`wixnative` processes, delete the affected project's `obj`/`bin`, then
run ONE build with nothing else concurrently touching the same output paths.

### A Windows service can work fine run manually but still fail to start under the SCM (error 1920 / SCM event 7009, 30s timeout)
If `YourApp.exe --service` runs perfectly when launched directly from an interactive PowerShell
session, that does NOT prove the actual Windows service (SCM-launched, running as `LocalSystem`
or a service account) will start successfully. The two contexts differ in ways an interactive
test won't catch: (1) **PATH** — the SCM uses the machine-wide (System) PATH, not your user PATH,
so any dependency your code locates via bare-command `PATH` lookup (e.g. `Process.Start(new
ProcessStartInfo { FileName = "ollama" })`) can silently fail to resolve even though it works in
your own shell; check `[System.Environment]::GetEnvironmentVariable("PATH","Machine")` explicitly
rather than assuming your interactive PATH is representative. (2) **No console session** — Session
0 has no console, so plain `Console`-based logging (including most `ILogger` console providers)
is completely invisible; you will see zero application-level detail, only generic SCM/Installer
symptoms (`msiexec` exit 1603, Service Control Manager event IDs 7000/7009, "service failed to
start... The operation completed successfully" — that message is a red herring, not a success).
When debugging this class of issue, don't trust a manual re-run as proof the service works, and
add a temporary file-based trace (raw `File.AppendAllText`, bypassing the `ILogger`/DI pipeline
entirely) at each startup checkpoint — it's the only thing that survives a real SCM-launched,
no-console process. See `SimpleModelServer.Server/Program.cs`'s `Trace()` helper and
`SimpleModelServerWorker.cs` for the pattern.

### `curl`/`Invoke-WebRequest` to `localhost` can hang or 503 even when the real server is healthy — check `127.0.0.1` and the literal `localhost` hostname separately, and check `netsh http show urlacl`/`servicestate` before assuming the app is stuck
Symptom: `Invoke-WebRequest http://localhost:11435/health` times out completely (or, depending on
which host header the client sends, comes back `503 Service Unavailable` with a generic IIS/
http.sys HTML error page — not JSON from the app). This looks exactly like "the process is hung"
and can burn hours chasing a nonexistent deadlock in application code. Root cause: on Windows,
`HttpListener.Prefixes.Add("http://localhost:PORT/")` registers a URL ACL reservation scoped to
the literal `localhost` hostname at the `http.sys` kernel driver level (visible via `netsh http
show urlacl`). A request to `127.0.0.1` or `[::1]` sends a different `Host:` header and does NOT
match a `localhost`-scoped registration — http.sys itself answers with its own generic 503 page,
without ever handing the request to the .NET listener. This is why `verifyMcpServer()`/health
checks in this repo deliberately use `127.0.0.1` instead of `localhost` in some places (IPv6
resolution) but the router itself is registered under `RouterHost` (`localhost` by default) — the
two need to actually agree, or diagnosis gets confusing. Separately, a **second, real** issue can
compound this: if a previous SimpleModelServer.Server instance crashed or was killed uncleanly, `http.sys`
can be left with a stale/wedged request queue for that URL reservation, and even hitting the
*correct* hostname (`http://localhost:PORT/health`) will hang indefinitely with no response and no
error — not a 503, a genuine hang. `netsh http show servicestate view=requestq` shows what's
actually registered and receiving connections. Fix for the wedged case: `sc stop
SimpleModelServer; sc start SimpleModelServer` — a clean restart re-registers the listener and
clears it immediately; don't assume "still warming up" for a process that has models already
cached locally (check `ollama.exe`'s own `/api/tags` separately — if Ollama itself answers
instantly, the hang is in the router layer, not model loading). Reproduced twice in a row
immediately after a fresh service install/restart during manual verification
of `TokenSaver.VsCodeExt`'s `runFullSetup` — both times the trace log showed `RunAsync` reaching
"ReloadModelForAgentAsync done" (i.e. everything up through the call into
`router.StartAsync` succeeded) with nothing logged after, and both times a plain restart fixed it
in seconds. No code-level root cause has been found yet (suspect `IsRouterAlreadyRunningAsync`'s
health probe against a not-yet-settled http.sys registration racing with `listener.Start()`, but
this is unconfirmed) — `runFullSetup` now works around it directly: if SimpleModelServer isn't healthy
after roughly a third of `simpleModelServer.startTimeout`, it runs one `sc stop`/`sc start` cycle
automatically before continuing to wait out the remaining budget, rather than making the user
wait out the full timeout (or manually restart it) for a condition a restart reliably clears.

### F5/Debug solution builds hit the WiX cabinet race even though nobody asked for an installer
Symptom: pressing F5 in Visual Studio (Debug configuration) fails with the exact same
`WixNativeException`/`0x80070002 cabinet` errors as the "concurrent MSBuild" pitfall above, even
on a clean machine with nothing else building — because `TokenSaver.Setup.wixproj` (in
`TokenSaver.slnx`) is an ordinary `<Project>` entry with no per-configuration build restriction, so a bare `.slnx` project entry builds under
**every** solution configuration by default (Debug included) — not just Release, and not just when
`BuildInstaller`/`RunInstaller` is explicitly opted into on the app csproj's publish target. F5
building an MSI installer nobody asked for is itself the bug; the underlying wixnative/cabinet
flakiness is secondary. Fix: give each wixproj entry in its `.slnx` an explicit
`<Build Solution="Release|Any CPU" Project="Release" />` and no entry for Debug — the `.slnx`
schema (`Microsoft.VisualStudio.SolutionPersistence`) only builds a project under configurations
that have an explicit `<Build Solution="..." .../>` rule; omitting Debug means it simply won't
build there. Verified against the current schema (`Slnx.xsd` in
`microsoft/vs-solutionpersistence`): the syntax is a `<Build>` *element* (not a `BuildType`
element with a `Build="false"` attribute), and turning a config off means omitting the element for
that config rather than setting an explicit false value.

**Known VS IDE bug that can silently undo this fix**: `microsoft/vs-solutionpersistence` issue
#138 (open, filed Oct 2025, no fix as of this writing) — opening the `.slnx` in Visual Studio and
hitting "Save All" (even with no solution-explorer changes) can silently re-add a bare `<Build />`
element with no `Solution`/`Project` attributes, which applies to every configuration and
re-enables building the wixproj under Debug again. If F5 starts hitting the WiX cabinet race again
after having previously been fixed, check the relevant `.slnx` for a bare `<Build />` under
`TokenSaver.Setup.wixproj` first — the fix is to remove it (leaving
only the scoped `<Build Solution="Release|Any CPU" Project="Release" />` line) rather than
re-deriving the whole investigation. Prefer editing `.slnx` by hand/via an external editor rather
than through VS's Solution Explorer UI for these two entries until upstream fixes #138.

### A Windows service can fail to start (error 1067) because a different launch mode of the *same app* already owns its port
`TokenSaver.MCP` can run three ways: manually (`dotnet run`), spawned as a child process by the
VS Code extension (`mcpExePath()` process-mode fallback), or as the `TokenSaverMCP` Windows
service. If the VS Code extension's process-mode instance is already running and healthy on port
11436 when the Windows service is installed/started, the service's own Kestrel bind throws
`AddressInUseException` → unhandled exception → process exits → SCM reports exit code 1067
("the process terminated unexpectedly") with no further detail from `sc query`. This is **not** a
permissions or install problem despite superficially looking like one (repeated `sc start` doing
nothing). Diagnose via `Get-WinEvent -FilterHashtable @{LogName='Application'} ` filtered to
recent — .NET's default unhandled-exception handler logs the full exception (including
`AddressInUseException` and the offending port) to the Application event log automatically, even
without any custom tracing. Fix: `Get-NetTCPConnection -LocalPort <port> -State Listen` to find
the PID actually holding the port, stop that process, then `sc start <service>` again.

## C#

### Reading external JSON config files (JSONC)
AI tool configs (`claude_desktop_config.json`, VS Code `settings.json`, etc.) are often JSONC — they contain comments and trailing commas that `System.Text.Json` rejects by default. Always parse them with tolerant options:

```csharp
var docOpts = new JsonDocumentOptions
{
    CommentHandling     = JsonCommentHandling.Skip,
    AllowTrailingCommas = true,
};
root = JsonNode.Parse(text, nodeOptions: null, documentOptions: docOpts)
           ?.AsObject() ?? new JsonObject();
```

Failing to do this causes `JsonNode.Parse` to throw, the catch block to swallow the error, and subsequent writes to overwrite the file with only our new entry — silently dropping all existing config.

### `with` expressions require `record` types
C# `with` expressions only work on `record` (or struct) types, not `class`. If a model type is used with `with { ... }` anywhere, declare it as `record`, not `class`. Check `ConfigUpdateResult` and similar result types.

### Primary constructors and `using` directives
When adding a primary constructor that references a type from another namespace (e.g. `IOptions<TokenSaverConfig>`), ensure the corresponding `using` is present. The compiler error `CS0246` means a `using` is missing, not that the type doesn't exist.

### Nullable reference types are enabled solution-wide
Every `.csproj` in this repo sets `<Nullable>enable</Nullable>`. Don't suppress warnings with `!` as a default habit — treat `CS8600`/`CS8602`/`CS8618` warnings as real signals, especially in EF Core entities and config-binding model types where a field can legitimately be null after deserialization.

### `TreatWarningsAsErrors` is conditional, not automatic
`Directory.Build.props` only sets `TreatWarningsAsErrors=true` when the `ENFORCE_CODE_QUALITY` env var is `true`. A local `dotnet build` can pass with warnings that will fail CI. When in doubt, build with `$env:ENFORCE_CODE_QUALITY = "true"` (PowerShell) before treating a build as clean.

## PowerShell 7

All `.ps1` scripts in this repo (`build/scripts/*.ps1`, including `setup.ps1` and `restart-loader.ps1`) target PowerShell 7+ and should start with `#Requires -Version 7.0` (or `7` for version-agnostic checks) — this fails fast with a clear error on Windows PowerShell 5.1 instead of hitting a cryptic parse error later. `restart-loader.ps1` is the one exception that doesn't follow the relative-path convention below and should not be used as a template for new scripts.

### Don't assume Windows PowerShell (5.1) syntax or defaults
PS7 (`pwsh`) is cross-platform and several 5.1 defaults changed:
- `Invoke-WebRequest`/`Invoke-RestMethod` no longer use IE's parsing engine — don't rely on `.ParsedHtml`.
- `ConvertTo-Json` default depth is still 2; nested config objects (e.g. writing `SimpleModelServer.config.json`) need explicit `-Depth` or they'll silently truncate to `"@{...}"` strings.
- String comparisons and `-eq` are still case-insensitive by default; use `-ceq`/`-ccontains` if case matters (e.g. matching Windows service names or registry keys).

### `$null` comparison order
Always put `$null` on the left: `if ($null -eq $value)`, not `if ($value -eq $null)`. If `$value` is an array, `$value -eq $null` filters the array and can silently return `$false` even when the array is empty, instead of doing the comparison you meant.

### Array/pipeline unwrapping surprises
A pipeline or cmdlet that returns zero or one items still returns a scalar in some contexts and `$null`/empty array in others. When capturing output that's used later as a collection (e.g. parsing service status or scanning `build/scripts` output), wrap in `@()` to force array semantics: `$results = @(Get-Service -Name "SimpleModelServer")`.

### Prefer relative/script-root paths over hardcoded absolute paths
Several scripts (e.g. `build/scripts/restart-loader.ps1`) hardcode paths like `f:\mcp\...`. New scripts should use `$PSScriptRoot` to build paths relative to the script's own location, so they work regardless of where the repo is cloned. Since all scripts now live in `build/scripts/` (not the repo root), resolve up two levels first: `$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path` — see `setup.ps1` for the pattern. Note: SimpleModelServer is built from its submodule by `SimpleModelServer/installer/build-installer.ps1` and installed silently from the resulting Inno `.exe`, so new install scripts should run that installer rather than reference local build output:

```powershell
$serverExe = Join-Path ${env:ProgramFiles} "SimpleModelServer\SimpleModelServer.Server.exe"  # installed by the SimpleModelServer Inno installer, not built from this repo
```

### External process exit codes
`dotnet build`/`dotnet publish`/`taskkill` invocations don't throw on failure in PowerShell — they just set `$LASTEXITCODE`. Check it explicitly after invoking build/install scripts in a chain (see `build-mcpb.ps1` for the pattern), otherwise a failed build can silently fall through to the next step (e.g. copying stale binaries during install).
