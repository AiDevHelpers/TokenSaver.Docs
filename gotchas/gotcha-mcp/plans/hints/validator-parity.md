# Hint: validator parity with validate.py

The Python validator (`data/validate.py`) is the reference. Parity traps:

1. **Schema selection by id prefix**, not by directory walk order:
   `patterns/` → pattern.schema.json; `snippets/` → snippet.schema.json;
   contains `/errors/` → error-mapping; everything else (languages/ gotchas,
   platforms/, dependencies/) → gotcha.schema.json.
2. **Gotcha glob set**: `languages/**/gotchas/**/*.json`, `platforms/**/gotchas/
   **/*.json`, AND `dependencies/**/*.json` (added 2026-07-07 — easy to miss).
3. **Draft 2020-12**: JsonSchema.Net supports it; `Newtonsoft.Json.Schema` does not
   fully — don't switch libraries.
4. **Regex compile check**: Python `re` and .NET accept slightly different dialects.
   The DB rule (see gotcha-db hints/authoring.md) is the common subset, so compile
   with .NET `new Regex(p)` and treat ArgumentException as invalid. If .NET accepts
   something Python rejects, Python CI catches it upstream — acceptable asymmetry,
   document it in the contract doc.
5. **tpl variable check** is exact set equality both directions:
   `{{(\w+)}}` occurrences vs sidecar `variables` keys.
6. **Marker check**: for each pattern component with `skeleton`, the referenced
   .tpl's `TODO\(gotcha:(\w+)\)` set must equal the component's step placeholder
   set — both directions, per component (not pooled across components).
7. **Test vectors may gain `_expected_error`** (see gotcha-db plans/phase-3):
   strip top-level keys starting with `_` before schema validation.
8. When any rule changes: change validate.py + RecordValidator + add a test vector,
   in one coordinated change across both repos.
