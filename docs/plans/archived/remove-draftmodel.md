# Plan: remove DraftModel from TokenSaver; use SimpleModelServer

Status: in progress.
Base: `ci-standalone-installer` (stacked on TokenSaver PR #1).

Problem: TokenSaver reaches SimpleModelServer on `localhost:11435`, and that works. But the code, config, service checks, and docs still speak DraftModel: the `DraftModelLoader` service, `DraftModel.config.json` discovery, the `DRAFTMODEL_WORKSPACE` env var, the DraftModel TypeScript client, the `draftModel.*` config keys, and the `draftmodel` health check.

Decisions (from the user):
- Scope: TokenSaver. This includes the VS Code extension, the VS 2022 extension, the WiX installers, and the common packages. SimpleModelServer's own `DraftModelLoader` references and the DraftModel submodule stay for now.
- No fallback. TokenSaver talks only to SimpleModelServer. The DraftModel discovery and endpoint are removed outright.
- Config keys are renamed: `draftModel.*` becomes `simpleModelServer.*`. The shipped defaults are updated, and the CHANGELOG says existing config files need a one-time edit.
- The health check is renamed from `draftmodel` to `simplemodelserver`. The functions `isDraftModelHealthy` and `IsDraftModelHealthyAsync` become `isSimpleModelServerHealthy` and `IsSimpleModelServerHealthyAsync`. Consumers in this repo are updated, and the change is listed in the CHANGELOG.

Facts checked (review findings):
- `DraftModelConfigResolver` has one call site, `Program.cs:171`. Its flag `SimpleModelServerServiceInstalled` is read only there. Both `appsettings.json` files set `DraftModelServiceInstalled` (wrong key, never binds).
- `TokenSaverBehaviorConfig.cs:914` binds `draftModel` from `.tokensaver/config.json` and `%ProgramData%\TokenSaver\config.json`. Existing files stop binding after the rename.
- `TokenSaver.VsCode.Extension/package.json:231-252` defines `tokenSaver.draftModel.exePath`, `healthUrl` and `startTimeout`. `extension.ts` reads them.
- `TokenSaver.Vs.Extension/Configuration/BehaviorConfig.cs:58` has `"draftModel"`.
- `AgentConfigService.cs` reads `DraftModel.config.json` through the `DRAFTMODEL_WORKSPACE` env var. `WorkspaceRootSessionResolver.cs:125` sets it.
- `draftModelChatProvider.ts` imports `@tokensaver/draftmodel-provider`, declared in the VS Code extension `package.json:23`.
- `IExtensionDraftModelSettings` is in `contracts.ts:254-277`.
- `HealthCheckClient.cs:126,231` has `IsDraftModelHealthyAsync`. The health check name is `"draftmodel"` at `Program.cs:228`, and `isDraftModelHealthy` is in `Helpers.TypeScript/health.ts:88,134`.
- The VS 2022 extension has about 15 DraftModel files, including `HttpDraftModelClient`, `DraftModelCommands`, and `DraftModelMenu`, plus two test classes.
- The WiX files (`Service.wxs`, `Product.wxs`, `TokenSaver.Setup.wixproj`) and `TokenSaver.MCP.csproj` reference DraftModel.
- `docs/retrieval-benchmark/*.jsonl` and `run_eval.py` hold DraftModel names as data. Exclude them from the replace.

Units (each: build and test, update status, commit, then start the next):

- [x] U1. Done (host builds, 0 errors; warnings are pre-existing CA analyzer rules). Remove the DraftModel discovery. Delete `DraftModelConfigResolver.cs` and its call in `Program.cs`. Remove the `SimpleModelServerServiceInstalled` flag and the `DraftModelServiceInstalled` appsettings keys.
- [x] U2. Done (the lockfile is regenerated; `IExtensionDraftModelSettings` moved to U3, since it mirrors the `draftModel` config key). Remove the DraftModel TypeScript package `src/Tooling/TokenSaver.Common.DraftModelProvider.TypeScript`. Delete `draftModelChatProvider.ts` and the code in `extension.ts` that registers it. Remove the dependency from the VS Code `package.json`, and regenerate its lockfile. Remove `IExtensionDraftModelSettings` from `contracts.ts`.
- [x] U3. Done (host builds). Rename the config keys: `TokenSaverBehaviorConfig.cs` (`draftModel` becomes `simpleModelServer`), the VS Code `package.json` settings (`tokenSaver.draftModel.*` becomes `tokenSaver.simpleModelServer.*`), `extension.ts`, and `BehaviorConfig.cs` in the VS 2022 extension. Update the shipped defaults. Update the tests that assert key names.
- [x] U4. Done (host builds). Correction: `isDraftModelHealthy` is a TypeScript function that checks only the HTTP status, not a JSON field, and the check name is read nowhere except its registration. Rename the health check. `"draftmodel"` becomes `"simplemodelserver"` in `Program.cs`, `isDraftModelHealthy` becomes `isSimpleModelServerHealthy` in `health.ts`, and `IsDraftModelHealthyAsync` becomes `IsSimpleModelServerHealthyAsync` in `HealthCheckClient.cs`. Update their consumers and tests.
- [x] U5. Done (host builds). Replace the `DRAFTMODEL_WORKSPACE` env var and `DraftModel.config.json` usage in `AgentConfigService.cs` and `WorkspaceRootSessionResolver.cs` with the SimpleModelServer equivalents.
- [x] U6. Done (typecheck and build pass). Decision: port the SimpleModelServer lifecycle from `TokenSaver.VsCodeExt` into `TokenSaver.VsCode.Extension`, which the VSIX is built from. The DraftModel functions are renamed, and the ten SimpleModelServer functions are copied from `TokenSaver.VsCodeExt`. `logSimpleModelServer` is kept. Packaging note: `simpleModelServerMsiPath` expects `bin/SimpleModelServer.Setup/SimpleModelServer-Setup.msi`, which `build-vsix.ps1` does not bundle yet. Original scope: VS Code extension service logic: remove the `DraftModelLoader` install, uninstall, start and health code from `extension.ts`, the DraftModel commands and settings in `package.json`, and `startDraftModel`. Use the SimpleModelServer service.
- [x] U7. Done (builds with 0 errors, 20 tests pass). Ported by renaming, not removing: the DraftModel client, prompt builder, commands, menu, models, and tests now use SimpleModelServer names, and the files are renamed. Original scope: VS 2022 extension: remove the DraftModel client, commands, menu, options, and their two test classes. Update `BehaviorConfig.cs` (done in U3).
- [x] U8. Done (host builds). Removed the StartDraftModelForDebug target and start-draftmodel-for-debug.ps1. Renamed DraftModel text in the WiX files and scripts. Original scope: WiX and build: remove the DraftModel references in `Service.wxs`, `Product.wxs`, `TokenSaver.Setup.wixproj`, and `TokenSaver.MCP.csproj`. Delete `scripts/start-draftmodel-for-debug.ps1`. Remove the DraftModel branches in `setup.ps1`, `update-service.ps1`, `build-vsix.ps1`, and `build-mcpb.ps1`.
- [x] U9. Done. Renamed DraftModel text in 59 files (docs, rules, code comments, tests, and config). CHANGELOG entry added. Original scope: Docs and rules: `CLAUDE.md`, `README.md`, `.cursor/rules/*`, `docs/*.md`, `INSTALL_PROMPT.md`, `VERIFY_INSTALL.md`, and `plans/nosql.md`. Replace DraftModel with SimpleModelServer. Add a CHANGELOG entry for the health-key and config-key renames.
- [x] U10. Done. Results: solution clean rebuild 0 errors, 1016 warnings (mostly CA analyzer rules; baseline not measured). All 580 .NET tests pass. The VS 2022 extension builds and its 20 tests pass. The VS Code extension typechecks and builds. TypeScript Helpers typechecks. TypeScript Contracts fails on an existing unresolved `@tokensaver/common-models` import (not from this change). Original scope: Verify: `dotnet build` on the solution with 0 warnings. `dotnet test` with every suite passing. The TypeScript packages build and test. A case-insensitive grep for `draftmodel` finds nothing, excluding `archive/`, the `docs/retrieval-benchmark` data, and the lockfile history.

Done when: U1 to U10 are verified, the grep is clean, and the CHANGELOG lists both renames.

Risks:
- The config key rename breaks existing `.tokensaver/config.json` and VS Code settings files. The CHANGELOG says so.
- The health-key rename breaks any external reader of `draftmodel`.
- Test fixtures may use DraftModel names as data. Check each one, do not bulk-replace.
- The VS 2022 and VS Code extensions need their own build and test runs. The VS 2022 build needs the VS SDK, which may not be on this machine.
