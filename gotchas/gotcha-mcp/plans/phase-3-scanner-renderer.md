# Phase 3 — Dependency scanner + template renderer

Two independent components; either order.

## Dependency scanner (`Gotcha.Core/Scanning/`)

- Input: project root path. Output: `IReadOnlyList<Dep>` where
  `Dep(Ecosystem, Package, Version)`, versions normalized to semver-ish
  (`Major.Minor.Patch`, best effort; keep raw string in `Dep.Raw`).
- One parser class per manifest, all implementing `IManifestParser.TryParse`:
  `package.json` + `package-lock.json` (lock wins), `pyproject.toml` (+ poetry.lock/
  uv.lock), `*.csproj` PackageReference + `packages.lock.json`, `Cargo.toml`/`.lock`,
  `go.mod`. TOML: use `Tomlyn` NuGet. XML csproj: `System.Xml.Linq`, beware multiple
  PackageReference ItemGroups and `Version` as attribute OR child element.
- Range matching: `VersionRange.Satisfies(depVersion, rangeString)` supporting the
  subset used in the DB: `>=x`, `<x`, `>=x <y`, `^x.y`, exact. Write this by hand
  (~60 lines), no NuGet dep — test against every `version_range` value present in
  the DB (enumerate them in the test so a new range syntax breaks loudly).

## Template renderer (`Gotcha.Core/Rendering/`)

- `Render(template, variables)` replaces `{{name}}`; resolution order for missing
  keys: caller context → style config → sidecar `default` → error listing ALL
  unresolved names at once (not first-only).
- Do NOT use regex-replace-in-loop (rescans replaced text). Single pass:
  `Regex.Replace(template, @"\{\{(\w+)\}\}", m => resolve(m))`.
- Style chain (project `.gotcha/styles.json` → user → defaults) is a flat
  dictionary merge computed once, passed in — renderer itself stays pure.

## Acceptance

- Scanner: fixture folder per ecosystem under `tests/fixtures/`, exact expected dep
  lists. Renderer: unresolved-variable error lists all names; snapshot's real
  snippets all render with their declared defaults.
