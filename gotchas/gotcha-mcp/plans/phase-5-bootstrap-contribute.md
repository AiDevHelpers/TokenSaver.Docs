# Phase 5 — Bootstrap + contribute

> **Gate:** `gotcha contribute` may ship for the repo owner's own use, but must NOT
> be released to other users before the contribution-security workstream exists
> (AV/deny-pattern scanning, regex-DoS CI check, staging branch — see
> `mcp/plans/gotcha-system.md` OPEN WORKSTREAM).

## `gotcha bootstrap` (Gotcha.Cli)

1. Detect languages (file extensions present) + deps (Phase 3 scanner) + runtime
   (OS, container marker files, TFMs from csproj, venv, node version).
2. Write `.gotcha/`: `deps.json` (scan output), `version.json` (bootstrap metadata),
   empty `styles.json`/`overrides.json` with commented examples, `drafts/` dir.
3. Compile a project-local snapshot including overrides.
4. Idempotent: re-run refreshes deps.json, never clobbers user-edited styles/
   overrides (merge, don't overwrite).

## `gotcha contribute` (Gotcha.Cli)

1. Validate all records in `.gotcha/drafts/`.
2. With `gh` CLI available + authenticated: clone/branch gotcha-db
   (`contrib/<user>-<date>`), copy drafts into shard layout, run its validate.py via
   `python3` if present (best-effort; C# validation already passed), commit, push,
   `gh pr create` listing record ids. Without `gh`: write `gotcha-contrib-<date>.zip`
   and print instructions.
3. Track submitted drafts in `.gotcha/drafts/.submitted.json` (id → PR url). On DB
   update containing the id, delete the local draft and its tracking entry.

## Acceptance

- Bootstrap on the TokenSaver repo itself produces a sane `.gotcha/` (manual check).
- Contribute round-trip tested with a local bare git repo standing in for GitHub
  (no network in tests).
