# Plan: settings scope (global vs local)

Split from `inherited-forging-crab.md` (Global knowledge DB section, item 3). Settings items were found by grep during
review; line numbers are omitted because they drift. Re-grep before editing.

## Current state → proposed
- Global `CLAUDE.md` machine facts (Git Bash, CRLF, `-F` commits): move to `ToolIncompat` with a pointer. Flag.
- `settings.json` `permissions.allow` (about 240 entries): keep generic ones (`dotnet build *`, `gh api *`) global;
  move one-off RomRaider, PsScripts, and ECU-Toolkit entries local. Flag.
- `Bash(python3 -)` is allowed although `CLAUDE.md` says the pattern hangs. Remove. Flag.
- `Move-Item f:\mcp\DraftModel…` entries are stale; DraftModel is archived. Remove. Flag.
- `additionalDirectories` holds three RomRaider/ECU paths. Move local. Flag.
- `autoMode` describes the VideoForensics repo but applies everywhere. Move local. Flag.
- `ProgramData` config: `context.debug: true` is non-default and belongs local. Flag.
- `repoHelper.autoSplitOversizedInstructions: true` rewrites `CLAUDE.md` in every workspace. Local. Flag.
- `tokenEconomy.modelRoutes.embed`: both. Record `EmbedModel` per project; mismatch raises a finding.
- `install.ps1` item list omits `skills\implement-plan`, which `CLAUDE.md` requires. Flag.
- `build.md` names a cloud-only tool and "SimpleModelServer" as a submodule, but the repo has three submodules
  (`.gitmodules`). Flag. The mcp `CLAUDE.md` also says two submodules; fix both.
- Server default root `F:\mcp` is stale. Flag.

## Applied (user approved "safe removals")
- Removed `Bash(python3 -)` from `~/.claude/settings.json`.
- Removed the four stale `Move-Item f:\mcp\DraftModel…` entries from `~/.claude/settings.json`.
- Not applied: all other flagged items.

## Open
- Each other "Flag" item needs your yes before any settings file changes.
- Settings changes are made by the user, or by the approved `ccd_settings` tools, not by this plan.
