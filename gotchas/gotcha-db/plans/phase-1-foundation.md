# Phase 1 — Foundation (DONE 2026-07-07)

What exists; do not redo. Reference only.

- 4 schemas in `metadata/schema/`: gotcha, snippet (sidecar for .tpl), pattern,
  error-mapping. All `additionalProperties: false`, all carry `schema_version: 1`.
- 17 gotchas (C#, PowerShell, Windows platform, pydantic), 4 snippets, 2 patterns
  (`fetch-parse-bind` composes `observable-viewmodel` via `uses`), 2 error mappings.
- `validate.py` — the executable spec: schema conformance, id↔path, dangling refs,
  regex syntax, tpl variable declarations, pattern-step ↔ `TODO(gotcha:...)` marker
  consistency. CI runs it on every PR (`.github/workflows/validate.yml`).
- `metadata/test-vectors/{valid,invalid}/` — shared conformance suite for both
  validator implementations.
- `CONTRIBUTING.md` — sharding + interlinking rules.
