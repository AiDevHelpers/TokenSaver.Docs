# gotcha-mcp plan (index)

C# repo: Gotcha.Core (compile/validate/scan/render), Gotcha.Cli, Gotcha.Mcp (server).
Master design: `mcp/TokenSaver/plans/nosql.md`. Data contract: the JSON Schemas in
gotcha-db (`data/` submodule) — never invent fields.

**Lazy loading rule:** read this file, then ONLY the active phase file. Read a hint
file only when its trigger matches. Phases are strictly ordered — do not start a
phase before the previous one's acceptance passes.

| Phase | File | Status |
|---|---|---|
| 1. Solution + C# validator | `phase-1-validator.md` | ready |
| 2. Snapshot compiler + loader | `phase-2-snapshot.md` | blocked by 1 |
| 3. Dependency scanner + renderer | `phase-3-scanner-renderer.md` | blocked by 2 |
| 4. MCP server + 6 tools | `phase-4-mcp-tools.md` | blocked by 3 |
| 5. Bootstrap + contribute | `phase-5-bootstrap-contribute.md` | blocked by 4 |

Hints:

- `hints/csharp-gotchas.md` — trigger: writing ANY C# in this repo.
- `hints/validator-parity.md` — trigger: Phase 1, or any schema/validation change.
- `hints/snapshot-loading.md` — trigger: Phase 2, or touching load/reload code.
- `hints/mcp-tool-safety.md` — trigger: Phase 4, or touching any MCP tool.

Hard rules (apply always):

1. Every MCP tool ships with a contract doc (`docs/<tool>-contract.md`) + tests in
   the SAME change. No exceptions — repo policy inherited from TokenSaver.
2. `<Nullable>enable</Nullable>` everywhere; treat CS86xx warnings as real.
3. Reference implementations for host/health/test patterns: TokenSaver.MCP
   (`TokenSaver/src/Host/TokenSaver.MCP` + its Tests project). Mirror, don't invent.
