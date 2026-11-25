# Plan: single point of database access (TokenSaver, Common, SimpleModelServer)

Split from `inherited-forging-crab.md`. Source: pasted pattern `db-single-point`, forked for `F:\source\mcp`. Applies to
every submodule that owns a database.

## Answered decisions
- Base branch: `feat/reindex-optimization` (not `master`, not `main`). Create the same-named branch in each submodule
  touched, from that base.
- Scope: all three submodules (`TokenSaver`, `Common`, `SimpleModelServer`). Check `SimpleModelServer` for database use
  before its units.
- Unit 1: prune removed or ignored files from the index (first todo item).
- Route versioning: URL path prefix, e.g. `/api/v1/index/...`.
- Client auth: server binds to 127.0.0.1 only; no auth token (same as today).
- Sonnet: read-only plan review only, when explicitly asked. Haiku does implementation.

## Target
- Only the indexer project owns the database context, entities, and repositories. Other projects never reference the
  database project or its entities.
- Contracts: each repository gets a DTO interface, using the old interface name. The old interface is renamed to a
  write repository and stays server-side.
- Server adapter: DTO repository calls the write repository and converts with extension methods. Enum DTOs mirror
  entity enums by member name, converted with `Enum.Parse`.
- API: each DTO operation is a versioned MCP server route. Validate input at the boundary.
- Clients (AgentHelpers adapters, VS Code extension): implement DTO interfaces through an HTTP-backed remote class.
  Server and client DI registrations live in separate blocks.
- `Common` contracts must not import database entities; replace them with DTO types.

## Method
1. Architecture gate tests first: scan project files and client source for database-project references. Must fail
   before the change, pass after.
2. Per unit: DTO, mapping, server DTO repository, remote class, DI registrations, consumers and tests.
3. Build serially (parallel builds cause stale-output errors). Run affected suites with no-build.
4. One local commit per unit; message written to a file, `git commit -F`; stage only that unit's files.

## Rules
- Work in a git worktree on a new branch; never edit the main checkout.
- Do not push or open PRs until asked.
- No stream-editing tools for file rewrites; read, then edit.
- Do not read docs or archive folders unless asked.
- Read each submodule's CLAUDE.md and matching `.claude/rules` before coding.
- Superproject pointer is updated last; only the pointer changes in `mcp`.

## Done when
Gate tests pass; client projects have no database references; affected suites pass (counts and skips reported); each
submodule branch has one commit per unit.

- Branch name in each submodule: `feat/single-point-db`, from `feat/reindex-optimization`.

## Open before unit 1
- Confirm where the index database and its owning project live inside `TokenSaver`.
