| Path | Kind | Title | Summary | Code | Semantic |
| --- | --- | --- | --- | --- | --- |
| .claude/rules/build.md | file | Build / run (orchestration layer) | No repo-root solution — build each submodule directly. Run on the user's machine via | code:.claude/rules/build.md | sem:pending |
| .claude/rules/instructions.md | file | Instructions and folder index (orchestration layer) | - The folder/file table `docs/folder-index.md` is generated. Never hand-edit it. | code:.claude/rules/instructions.md | sem:pending |
| .claude/rules/pitfalls.md | file | Pitfalls (orchestration layer only) | Check `docs/pitfalls.md` for a documented root cause before debugging any of these — each entry is | code:.claude/rules/pitfalls.md | sem:pending |
| CLAUDE.md | file | CLAUDE.md | Orchestration/glue repo (`mcp`) over three submodules — no application source of its own: | code:CLAUDE.md | sem:pending |
| Common/ | folder | Common |  | code:Common | sem:pending |
| SimpleModelServer/ | folder | SimpleModelServer |  | code:SimpleModelServer | sem:pending |
| TokenSaver/ | folder | TokenSaver |  | code:TokenSaver | sem:pending |
| docs/ | folder | docs |  | code:docs | sem:pending |
| docs/branch-and-submodule-workflow.md | file | Branch and submodule workflow | The `mcp` superproject has two submodules: `TokenSaver` and `Common`, plus `SimpleModelServer`. This repo | code:docs/branch-and-submodule-workflow.md | sem:pending |
| docs/pitfalls.md | file | Known Pitfalls | Root causes for bugs that took more than 2 attempts to resolve, so the next person (or agent) hits | code:docs/pitfalls.md | sem:pending |
| docs/plans/additons.md | file | TokenSaver — New Tools Implementation Plan (v2: token-economy design) | Assumption: server is Node.js (typical for `.mcpb`/DXT packages). If it's actually | code:docs/plans/additons.md | sem:pending |
| docs/plans/codebase-review-fix-plan.md | file | Codebase review and fix plan | Date: 2026-11-16. Reviewed at: `mcp` @ `a0685a4` (branch `wip`), `TokenSaver` @ `60b38c5`. | code:docs/plans/codebase-review-fix-plan.md | sem:pending |
| docs/plans/gotcha-system.md | file | Gotcha System — master index | Design record (decisions, data model, rationale): `TokenSaver/plans/nosql.md`. | code:docs/plans/gotcha-system.md | sem:pending |
| docs/plans/inherited-forging-crab.md | file | Plan: auto-documented context DB (systems, features, docs, functions) for the index | The TokenSaver index today tracks folders, files, chunks (semantic), and symbols (code index). It has no | code:docs/plans/inherited-forging-crab.md | sem:pending |
| docs/plans/instr-index.md | file | Plan: instruction maintenance + folder/file index (mcp repo) | Adapt the pasted VideoForensics plan to `F:\source\mcp`. Goal: a small, generated folder/file table | code:docs/plans/instr-index.md | sem:pending |
| docs/plans/model-eval.md | file | Plan: pick the summary and embedding models for semantic search | Status: research done, index rebuild not started. | code:docs/plans/model-eval.md | sem:pending |
| docs/plans/reindex-optimization.md | file | Reindex optimization plan | Status: draft, not approved. Scope: `TokenSaver/src` (submodule). Orchestration repo only holds this file. | code:docs/plans/reindex-optimization.md | sem:pending |
| docs/plans/settings-scope.md | file | Plan: settings scope (global vs local) | Split from `inherited-forging-crab.md` (Global knowledge DB section, item 3). Settings items were found by grep during | code:docs/plans/settings-scope.md | sem:pending |
| docs/plans/single-point-db-access.md | file | Plan: single point of database access (TokenSaver, Common, SimpleModelServer) | Split from `inherited-forging-crab.md`. Source: pasted pattern `db-single-point`, forked for `F:\source\mcp`. Applies to | code:docs/plans/single-point-db-access.md | sem:pending |
| gotcha-db/ | folder | gotcha-db |  | code:gotcha-db | sem:pending |
| gotcha-ingest/ | folder | gotcha-ingest |  | code:gotcha-ingest | sem:pending |
| gotcha-mcp/ | folder | gotcha-mcp |  | code:gotcha-mcp | sem:pending |
| scripts/ | folder | scripts |  | code:scripts | sem:pending |
