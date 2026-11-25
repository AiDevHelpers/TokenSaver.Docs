# Plan: TokenSaver.Common as NuGet packages

Status: in progress.
Base: `remove-draftmodel` (stacked on PR #1 and PR #2).

Goal: `rsperry79/TokenSaver.Common` builds and publishes its libraries as NuGet packages to GitHub Packages. TokenSaver consumes them as PackageReferences instead of the `Common` submodule. Locally, both repos use the packages that the Common build produces.

Decisions (from the user):
- Publish to GitHub Packages (private feed, rsperry79).
- Local development uses the Common repo's own `artifacts/` output (`dotnet pack -o artifacts`).

Facts checked:
- Common has three projects: `TokenSaver.Common.Core` (no Nerdbank reference), `TokenSaver.Common.LLM-Connection`, and `TokenSaver.Common.Logging`. Both of the latter reference Nerdbank.GitVersioning 3.10.91. Common's `version.json` is `1.0-alpha`.
- TokenSaver references only `TokenSaver.Common.Logging`, from `src/Host/TokenSaver.MCP/TokenSaver.MCP.csproj`. The `Common` submodule is at `Common`, pinned to `85d0085`.
- `TokenSaver.slnx` lists `Common/LLM-Connection/...` and `Common/Logging/...` projects.
- The `TOKENSAVER_READ_TOKEN` secret (not yet created) must be a classic PAT with `repo` (private checkout) and `read:packages` (GitHub Packages NuGet). Fine-grained PATs don't work with the NuGet registry.
- `TokenSaver.Common.Core` is not published (`IsPackable=false`). TokenSaver's in-repo project has the same name, and TokenSaver doesn't consume the package. Logging and LLM-Connection are published.

Units (each: build, check, update status, commit, then start the next):

- [ ] U1. Common repo, branch `packaging` (PR into `main`). Add a root `Directory.Build.props` with RepositoryUrl and Authors. Set `IsPackable=false` on Core. Add Nerdbank.GitVersioning 3.10.91 to Logging and LLM-Connection (already there). Add `artifacts/` to `.gitignore`. Verify `dotnet pack -c Release -o artifacts` creates `TokenSaver.Common.Logging` and `TokenSaver.Common.LLM-Connection` packages with versions from version.json. Non-main builds get a prerelease suffix (`-alpha.N-gSHA`), so TokenSaver's PackageReference uses a prerelease range.
- [ ] U2. Common repo CI (`.github/workflows/ci.yml`): on push to `main` and on PRs, restore, build, test (if any), and pack. On push to `main` only, push the packages to `https://nuget.pkg.github.com/rsperry79/index.json` with `GITHUB_TOKEN` (`packages: write`).
- [x] U3. Done. TokenSaver: remove the `Common` submodule (`.gitmodules` and the gitlink). Replace the `ProjectReference` to Logging with `PackageReference` `TokenSaver.Common.Logging`. Remove the `Common/...` projects from `TokenSaver.slnx`. Keep the versions in each csproj, unless `Directory.Packages.props` already exists in TokenSaver (check first).
- [x] U4. Done (verified with the sibling layout). TokenSaver `nuget.config`: sources are nuget.org, GitHub Packages (`rsperry79`, authenticated with `%TOKENSAVER_READ_TOKEN%`), and a local folder `../Common/artifacts` for side-by-side checkouts. `packageSourceMapping` maps `TokenSaver.Common.*` to the Common sources only. Verify local restore picks the packages from the local folder.
- [x] U5. Done (YAML parses; first PR run is the check). TokenSaver CI: remove the submodule checkout. Add `TOKENSAVER_READ_TOKEN` to the NuGet source credentials, so restore reads the Common feed. Keep the existing jobs.
- [x] U6. Done locally: solution builds with 0 errors against the packages, 580 tests pass. Remote publish and CI are verified after the Common PR merges. Verify: Common `dotnet pack` output; TokenSaver `dotnet restore` against the local folder; full TokenSaver solution build with 0 errors and tests passing. Remote publish and CI on GitHub are verified after the PRs run.

Done when: TokenSaver builds from restored packages with no submodule, local dev uses `../Common/artifacts`, and CI publishes from Common and restores from GitHub Packages.

Risks:
- Common's packages get versions from git height. Local `artifacts/` versions must not collide with published versions.
- The `TOKENSAVER_READ_TOKEN` needs `read:packages` on the Common feed. A fine-grained token must list the Common repo's packages.
- NuGet credentials in `nuget.config` use `%VAR%` expansion. Confirm this works on the runner.
- Removing the submodule drops the pin. The pin becomes the package version.
