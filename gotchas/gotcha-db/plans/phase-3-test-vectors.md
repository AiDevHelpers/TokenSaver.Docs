# Phase 3 — Test-vector growth (do alongside Phase 2)

`metadata/test-vectors/` must cover every validation rule so the C# validator
(gotcha-mcp Gotcha.Core) can prove parity with `validate.py`.

Current vectors: minimal-valid gotcha; invalid: unknown field, bad detection.kind,
pattern with both `skeleton` and `uses`.

## Missing vectors to add (one file each, name = rule violated)

- `invalid/gotcha-id-path-mismatch.json` — NOTE: this rule is checked against file
  location, so the vector needs a `_expected_error` convention instead; see below.
- `invalid/gotcha-bad-regex.json` — `detection.pattern` that doesn't compile.
- `invalid/snippet-undeclared-variable.json` + `.tpl` — tpl uses `{{x}}` not in sidecar.
- `invalid/pattern-dangling-refs.json` — `starting_point`/`gotchas` pointing nowhere.
- `invalid/pattern-marker-mismatch.json` + skeleton — step without TODO marker.
- `valid/gotcha-maximal.json` — every optional field populated.
- `valid/pattern-with-uses.json` — composition, no local skeleton.

## Convention for non-schema rules

Schema violations are self-describing. For cross-file rules (dangling refs, id↔path,
markers), add a `_expected_error` top-level key with a substring the validator's
message must contain. Both validators strip keys starting with `_` before schema
checking. Update `validate.py` and the README here when introducing this convention.
