# Remaining work (TokenSaver), 2026-11-19

Status as of 2026-11-19. Sources: common-as-nuget.md, ci-standalone-installer.md, wt-standard-session.md, and the IDE bridge split.

## IDE bridge
- Moved to SperryDev.Ide-Bridge: docs/plans/remaining-work-2026-11-19.md.
## Common as NuGet (in progress, from common-as-nuget.md)

- [ ] U1 (Common repo, branch packaging): root Directory.Build.props, IsPackable=false on Core, artifacts/ in .gitignore, verify dotnet pack output.
- [ ] U2 (Common repo CI): build, test and pack on PRs; publish to GitHub Packages on push to main.
- [ ] U6: remote publish and GitHub CI verification, after the Common PR merges. Done locally only.
- [ ] User action: create TOKENSAVER_READ_TOKEN (classic PAT, repo and read:packages) and add it as a secret.

## CI standalone installer (in progress, from ci-standalone-installer.md)

- [ ] U4 verification: install and uninstall on a real machine.
- [ ] Done when: the CI installer job produces both assets on a push.
- [ ] Before enabling the test gate in CI: confirm the local dotnet test result.
- [ ] ISCC is not on windows-latest; confirm the workflow installs it (choco install innosetup).

## Windows Terminal standard session

- Moved to `SperryDev.Ide-Bridge/docs/plans/wt-standard-session.md` with the terminal helper and MCP tool.

## Housekeeping

- [ ] Remove worktree F:\source\TokenSaver-wt-work after its merge.
- [ ] Local wip is ahead of origin. Decide what gets pushed; wip itself is never pushed.
