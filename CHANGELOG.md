# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow the scheme resolved
by Nerdbank.GitVersioning from `version.json`.

## [Unreleased]

### Added

- Log helper (`TokenSaver.LogHelper`) with `LogChannels`, `LogQuery` (summary, traces, ignored views;
  cursors, run diffs and a bounded watch), `LogMarkRun` and `LogSinkCompare`. Sources: files, VS Code
  output and debug sessions, Visual Studio output panes, journald and `/var/log`, Windows Event Log.
- Skills: `log-level-advisor`, `log-sink-prune`, `log-sink-elevate`.

### Changed

- **Breaking:** DraftModel is removed. TokenSaver talks only to SimpleModelServer on
  `http://localhost:11435`.
- **Breaking:** the `draftModel` settings are renamed `simpleModelServer`. Existing
  `.tokensaver/config.json` files and VS Code `tokenSaver.draftModel.*` settings must be
  renamed by hand. The defaults are unchanged.
- **Breaking:** the `draftmodel` health check is renamed `simplemodelserver`, and its helpers
  are renamed `IsSimpleModelServerHealthyAsync` and `isSimpleModelServerHealthy`. Anything that
  reads the old check name must be updated.
- The agent config is read from `SimpleModelServer.config.json`, selected by
  `SIMPLEMODELSERVER_WORKSPACE`, which replaces `DraftModel.config.json` and `DRAFTMODEL_WORKSPACE`.
- The VS Code extension manages the SimpleModelServer service, replacing the DraftModelLoader
  service. Its Copilot chat provider for DraftModel is removed.

### Added

- Initial commit: `TokenSaver.MCP`, `TokenSaver.CodeHelper`, `TokenSaver.ContextHelper`,
  `TokenSaver.Library`, `TokenSaver.Docs`, `TokenSaver.VsCodeExt`, and their test projects,
  moved out of the [rsperry79/mcp](https://github.com/rsperry79/mcp) orchestration repo.
- `TokenSaver.AgentHelpers.Core`, `TokenSaver.AgentHelpers.Anthropic`, `TokenSaver.AgentHelpers.Qwen`, `TokenSaver.AgentHelpers.DeepSeek`,
  `TokenSaver.AgentHelpers.OpenSource` — per-agent context-formatting and caller-detection adapters, moved
  from the same repo.
- `TokenSaver.slnx` solution file.
- MSI installer packaging for `TokenSaver.MCP` via WiX (`build/wix/TokenSaver.Setup`), output
  to `build/dist/TokenSaver-Setup-<version>.msi`.
- VSIX packaging for the VS Code extension (`build/scripts/build-vsix.ps1`), bundling the
  TokenSaver MSI.
- Claude Desktop Extension (`.mcpb`) packaging (`build/scripts/build-mcpb.ps1`).
- `build/scripts/setup.ps1` — publishes TokenSaver.MCP and registers it with Claude Desktop.
- `build/scripts/update-service.ps1` — rebuilds and updates the installed `TokenSaverMCP`
  Windows service in place.
- `version.json` for Nerdbank.GitVersioning.
- `docs/architecture.md`, `docs/tokensaver-mcp-health-contract.md`, `docs/versioning.md`.
- `.gitignore`, `.editorconfig`, `Directory.Build.props`, `README.md`.
