# Plan: TokenSaver CI and the standalone TokenSaver MCP installer

Status: in progress.
Base: `wip` (this repo). Branch `ci-standalone-installer`.

Decisions (from the user):
- Separate CI. SimpleModelServer's CI no longer touches TokenSaver. TokenSaver gets its own workflow in this repo, which builds its MSI and its standalone exe and publishes them.
- TokenSaver is removed from the SimpleModelServer installer. That repo already has no TokenSaver integration on `dev`. The unpushed branch `installer-tokensaver-mcp` in that repo is abandoned.
- The standalone installer is an Inno Setup `.exe` that wraps `TokenSaver-Setup-<version>.msi`.

Facts checked:
- This repo has no `.github/workflows/`. Its only build entry points are `dotnet build TokenSaver.slnx` and `scripts/publish-tokensaver-for-wix.ps1 -Pack`, which writes `build/dist/TokenSaver-Setup-<Version>.msi`.
- Versioning: `version.json` uses Nerdbank.GitVersioning, `"1.0-alpha"`, with `publicReleaseRefSpec` `^refs/heads/main$`. The MSI version has to be numeric, so the workflow derives it from `nbgv get-version -v NuGetPackageVersion` with the pre-release suffix removed.
- The WiX SDK is `WixToolset.Sdk/6.0.0`, restored from NuGet. The `wix` CLI is not needed for `dotnet build`.
- `.claude/rules/packaging.md` says outputs go to `build/dist/`.

Units (each: build, check, update status, commit, then start the next):

- [x] U1. Done. `installer/TokenSaverMcp.iss`: Inno Setup script. It bundles `{#TokenSaverMsi}` and runs `msiexec /i` silently on install, and `msiexec /x` on uninstall. Exit codes 0 and 3010 are success. Log under `{commonappdata}\TokenSaver\`, created with `[Dirs]`. Uses a new, distinct AppId. Output `TokenSaverMCP-Setup-{#MyAppVersion}.exe`. Admin required.
- [x] U2. Done. `scripts/build-standalone-installer.ps1`: runs `dotnet build` on the wixproj with `-p:MyAppVersion=<numeric>`, copies the MSI to a fixed name, compiles `TokenSaverMcp.iss` with ISCC, and writes `SHA256SUMS.txt` for both files into `build/dist/`.
- [x] U3. Done (YAML parses). Checkout uses `submodules: recursive` and `token: ${{ secrets.TOKENSAVER_READ_TOKEN }}`, because Common is private. `.github/workflows/ci.yml`: on push to `wip` and `main`, and on pull requests. Jobs: `build-and-test` (restore, build, `dotnet test TokenSaver.slnx`), `installer` (runs U2, uploads `build/dist/*`; push only), and `release` (push only; `v<version>`, prerelease unless `main`; creates the tag if missing, as in SimpleModelServer's CI). PRs never publish from this repo, unless the user changes that.
- [x] U4. Done: solution builds (0 errors), standalone MSI and exe build with checksums. Install and uninstall on a real machine not run. Verify locally: the MSI and standalone exe build, and the checksums match. The workflow YAML parses. Install and uninstall on a real machine are not run here.

Done when: U1 to U4 are verified, and the TokenSaver CI installer job produces both assets on a push.

Risks:
- TokenSaver's tests may not pass in CI yet. Check the local `dotnet test` result before enabling the test gate.
- The TokenSaver MSI build prints warnings (159 on the last local run). They are not errors, so this plan doesn't fix them.
- ISCC is not on GitHub's `windows-latest` image by default. Install it with `choco install innosetup`, as SimpleModelServer's CI does.
