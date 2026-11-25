# Versioning

This repo uses [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) (NBGV) to derive version numbers automatically from git, instead of hand-editing version numbers per project/release.

## How it works

`version.json` at the repo root is the single source of truth:

```json
{
  "version": "1.0-alpha",
  "publicReleaseRefSpec": ["^refs/heads/main$"]
}
```

`Directory.Build.props` adds `PackageReference Include="Nerdbank.GitVersioning"` (`PrivateAssets="all"`, build-time only — it doesn't become a runtime dependency of anything that references these projects). Every C# project in the solution picks this up automatically and gets `Version`, `AssemblyVersion`, `FileVersion`, and `AssemblyInformationalVersion` computed as `{version.json version}.{git height}` — e.g. `1.0.42` where `42` is the number of commits since `version.json`'s version was last changed.

Bump the `version` field in `version.json` (e.g. `1.0` → `1.1`) when you want to start a new version series; NBGV resets git height counting from that commit.

## Checking the current version

```powershell
dotnet tool install --global nbgv   # one-time
nbgv get-version
```

## WiX installer (`TokenSaver.Setup.wixproj`)

NBGV has a known incompatibility with WiX Bundle/Package project types (`CodeDomProvider not available for language: wix` — see [wixtoolset discussion #7322](https://github.com/orgs/wixtoolset/discussions/7322)), so `TokenSaver.Setup.wixproj` does **not** reference NBGV directly.

Instead, `scripts/publish-tokensaver-for-wix.ps1` resolves the version via `nbgv get-version --format json` and passes it into the wixproj as `-p:MyAppVersion=<version>`:

```powershell
.\scripts\publish-tokensaver-for-wix.ps1 -Pack
```

**`TokenSaver.Setup.wixproj` also resolves it itself now**, via an `InitialTargets` target called `ResolveMyAppVersionFromNbgv`. It runs `dotnet nbgv get-version -v SimpleVersion` (using `nbgv` as a local tool restored from `.config/dotnet-tools.json` — no global install needed) whenever `-p:MyAppVersion` wasn't passed explicitly, so a plain `dotnet build TokenSaverMCP.slnx` or Visual Studio "Build Solution" gets a real, monotonically-increasing version too, not just builds that go through the publish script.

This closes a real bug: previously, any build that skipped the publish script fell back to a hardcoded `1.0.0` literal every single time. Since `MajorUpgrade` detects "is this an upgrade?" by comparing `Package/@Version` under the same `UpgradeCode`, an *identical* version between two installs is neither newer nor older, so `RemoveExistingProducts` never fires — each build's freshly auto-generated `ProductCode` got installed as a brand-new product instead of upgrading the old one. That's why Programs & Features could accumulate several "TokenSaver MCP" (and "SimpleModelServer Loader") entries all stamped version 1.0.0. The `1.0.0` literal is now only a last-resort fallback for when `nbgv` genuinely can't resolve a version (shallow clone, blocked tool restore).

`ResolveMyAppVersionFromNbgv` also resolves `GitCommitIdShort` into `GitCommitHash`, stamped into the installed product's `ARPCOMMENTS` property (see `Product.wxs`) purely for build traceability — visible as "Comments" in Programs & Features. It plays no role in upgrade detection itself; MSI version fields are numeric only, so the commit hash can't (and doesn't need to) be part of `Package/@Version`.

`TokenSaver.Setup.wixproj` also has a `PublishTokenSaverMcp` MSBuild target (`BeforeTargets="Build"`) that runs `dotnet publish` on `TokenSaver.MCP.csproj` into `build\staging\TokenSaver.MCP` automatically if the staged exe is missing or older than the csproj, so a plain `dotnet build TokenSaver.slnx` / Visual Studio "Build Solution" doesn't fail on WIX0103 (missing Icon/File) just because the manual publish step wasn't run first. This target is a fixed `Release`/`win-x64` publish with no version stamping beyond what NBGV already bakes into the exe via `Directory.Build.props` — for a real release build with an explicit `MyAppVersion` and clearer console output, still prefer `scripts\publish-tokensaver-for-wix.ps1 -Pack`.

### How the version drives upgrade vs. fresh install

`Product.wxs`'s `Package/@Version="$(MyAppVersion)"` plus the fixed `UpgradeCode` is what Windows Installer uses to detect "an existing TokenSaver MCP install is present, and this is a newer/older/same version of it" — that's the whole upgrade-detection mechanism, and it's why `MyAppVersion` must increase release over release (NBGV's git-height scheme guarantees this automatically; see above). `MajorUpgrade`'s `DowngradeErrorMessage` blocks installing an older version over a newer one.

`MajorUpgrade Schedule="afterInstallExecute"` (rather than WiX's default `afterInstallInitialize`) additionally makes upgrades install the new version's files/service "on top of" the existing install rather than fully uninstalling the old product first. Combined with `ServiceComponent` in `Service.wxs` keeping a stable `Component/@Guid` and `ServiceInstall/@Name` across releases, this means an upgrade stops the running `TokenSaverMCP` service, replaces its files, and restarts it — it is not deleted and recreated in the SCM. A genuine uninstall still fully removes it via `ServiceControl`'s `Remove="uninstall"`.

## CI

No CI workflow exists in this repo yet. If one is added, make sure its checkout step uses
`fetch-depth: 0` (full git history) — NBGV requires it to compute an accurate commit height.
