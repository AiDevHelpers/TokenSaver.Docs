> Status (2026-11-18): approved, not started. Ide-Bridge repo exists and is empty on main; namespaces (SperryDev.Ide.Bridge) and IBridgeLogger in BridgeServer are in progress, uncommitted. Work merges into local wip; PRs only wip -> dev.

# Split the IDE bridge into SperryDev.Ide-Bridge

## Context

The Visual Studio IDE bridge (named pipe between Visual Studio and the TokenSaver MCP server) lives inside
TokenSaver. It becomes its own repo, `SperryDev.Ide-Bridge` under the SperryDev GitHub org, consumed by TokenSaver
as a NuGet package. A second repo, `SperryDev.Docs`, holds the docs of the other org repos.

## Decisions (settled)

- Scope: full bridge (VS side and MCP client side, tests). Fresh repos, no history carried over.
- Both repos are created as private GitHub repos under SperryDev. Both exist and are empty.
- Package version starts at `0.1.0`.
- Manifest: one shared record with required `Ide` and `LogRoots`. No optional fields and no compatibility shim.
  The VS writer (`InstanceRegistry`) is changed to emit `Ide = "VisualStudio"` and `LogRoots = []`.
  The VS Code writer already emits both.
- Branches: the new repos use local `wip` and `dev`. Work merges into local `wip`. PRs go only from `wip` to `dev`.
  `wip` is never pushed. Work branches may be pushed.
- TokenSaver's docs stay in TokenSaver, including `docs/ide-bridge.md`. Its `unsupported: bool` line is checked before editing.
- The snake_case tool names (`query_ide_status`, `launch_ide`, `stop_ide`) belong to the VS Code bridge, as
  `docs/self_test.md` shows. They stay in TokenSaver and are not part of this split.
- Commits carry no Claude attribution, per the global rule.

## Ide-Bridge repo (`F:\source\SperryDev.Ide-Bridge`)

- `SperryDev.Ide.Bridge` (net10.0-windows, no VS SDK): `BridgeServer`, `BridgeControl`, `InstanceRegistry`,
  `OutputPaneSlice`, `IBridgeLogger`, `VsInstanceRegistry`, `IdeInstanceRouter`, one shared manifest record.
- Make the moved types public. The VS adapter and MCP both use them.
- `SperryDev.Ide.Bridge.Tests`: moved `BridgeServerTests`, `OutputPaneSliceTests`, `VsInstanceRegistryTests`,
  plus new routing tests for `IdeInstanceRouter`.
- Solution file, `.gitignore` (`.tokensaver/`, `bin/`, `obj/`), README linking to `docs/ide-bridge.md` in TokenSaver.
- Done so far: namespaces are `SperryDev.Ide.Bridge`, and `BridgeServer` uses `IBridgeLogger`.

## SperryDev.Docs repo

- Holds the docs of the other org repos, one folder per repo: `SimpleModelServer/`, `Common/`, `Ide-Bridge/`.
- Move and point: each source repo deletes its moved docs and its README links to the matching folder. No copies.
- Regenerate the org index `F:\source\mcp\docs\folder-index.md` after the moves, using `code_index(action: 'table')`.

## TokenSaver (`feature/vs-inproc-port`)

- Replace the moved files with package references in `TokenSaver.Vs.Extension` and `TokenSaver.MCP`.
- `TokenSaverPackage`: construct `BridgeServer` with the action delegate. Adapt `SperryExtensionLogger` to `IBridgeLogger`.
- Update callers of `IdeInstanceRouter` and `VsInstanceRegistry`. `VsCodeLogSourceProvider.cs` and
  `ServiceRegistrationExtensions.cs:358` stay in TokenSaver and read the moved types from the package.
- Remove the moved files and the three moved test files.
- Fix the `unsupported` line in `docs/ide-bridge.md`.
- `IdeActions`, `IdeTools`, `IdeInstanceLifecycle`, `ServicesViewModel` and the VS Code bridge stay as they are.
- Note: the in-process VSSDK port (csproj net472, Remote UI and command rewrite) is a separate, not-yet-started change.
  The uncommitted Services and bridge work on this branch is unaffected by the split until the consumer switch.

## Risks

- Packaging: both consumers target `net10.0-windows`. The package DLL must ship in the VSIX and the MCP publish output.
  Restore needs a feed (local or CI publish) before TokenSaver builds.
- VSIX install: the Debug VSIX install into VS Community still fails on the stale `extensionDir` path
  (`VSExtensions\j30o0obs.15i`). The in-process port may avoid it; not verified.
- Submodules: the two new repos are not submodules of `mcp` unless added. If added, the pointer-sync rule applies:
  push the submodule first, then update and push the `mcp` pointer.
- Stash: `vs-services-bridge-wip` is on the TokenSaver stash list. The changes were restored, so the stash entry should be dropped.

## Verification

- `dotnet build` and `dotnet test` in the Ide-Bridge repo (both test projects green).
- `dotnet build` of `TokenSaver.slnx` after both consumers switch to the package.
- Run the MCP server, call `IdeBridgeHealth` and `IdeListInstances` against a running VS instance.
- Reinstall the VS extension and confirm the Services Start/Stop bridge section works.

