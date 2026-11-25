# gotcha-mcp

Standalone MCP server, CLI, and core library for the Gotcha System — a local-first,
version-aware knowledge base of coding pitfalls, fix snippets, and code patterns.

Plan: `TokenSaver/plans/nosql.md` in the `mcp` orchestration repo (will move here).

## Layout

```
src/Gotcha.Core/   compiler, validator, dependency scanners, template renderer, pattern matcher
src/Gotcha.Cli/    `gotcha` CLI (bootstrap, validate, snapshot, query)
src/Gotcha.Mcp/    MCP server host (mirrors TokenSaver.MCP host layout)
data/              → git submodule: gotcha-db (not yet wired; see data/README.md)
docs/              contract doc per MCP tool (required, with tests, per repo policy)
```

## MCP tools (planned — Phase 1)

`gotcha_check(diff, deps)` · `gotcha_error(error_text)` · `gotcha_snippet(id, context)`
· `gotcha_scaffold(intent, deps)` · `gotcha_expand(pattern_id, placeholder, context)`
