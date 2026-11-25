# Phase 1 — Solution + C# validator

Goal: `dotnet test` proves Gotcha.Core validates records identically to gotcha-db's
`validate.py`. Read `hints/csharp-gotchas.md` and `hints/validator-parity.md` first.

## Steps

1. Solution: `Gotcha.slnx` with Gotcha.Core (net8.0 classlib), Gotcha.Core.Tests
   (xunit), Gotcha.Cli (console), stubs only for Gotcha.Mcp. `Directory.Build.props`
   with Nullable enable. Nerdbank.GitVersioning already configured (version.json).
2. NuGet: `JsonSchema.Net` (draft 2020-12 support) for schema checks; no other deps.
3. `Gotcha.Core/Validation/RecordValidator.cs`:
   - `ValidateFile(path, dbRoot)` → schema check (pick schema by id prefix:
     `patterns/`→pattern, `snippets/`→snippet, `/errors/`→error-mapping, else gotcha)
   - id↔path rule; then cross-file pass: dangling refs (fix_snippet, related, uses,
     skeleton, starting_point, gotchas, error-mapping targets), regex compile check,
     tpl variable declarations, pattern-step↔TODO-marker consistency.
   - Return `IReadOnlyList<ValidationError>` (record type: FilePath, Rule, Message).
     Never throw for data problems; throw only for IO.
4. Tests, in this order:
   a. Test-vector conformance: every file in `data/metadata/test-vectors/valid/`
      produces zero errors; every file in `invalid/` produces ≥1 error.
   b. Full-DB parity: validating all of `data/` produces zero errors (the Python CI
      already guarantees the DB is clean — any error here is a C# bug).
5. `Gotcha.Cli`: `gotcha validate <db-path>` printing the same summary format as
   validate.py (`N gotchas, N snippets, N patterns, N error mappings — ALL VALID`).

## Acceptance

- `dotnet test` green including both 4a and 4b.
- `gotcha validate data/` output matches `python3 data/validate.py` output.
