# Pattern (forked for F:\source\mcp): single point of database access

Forked from `db-single-point.md`. Target: the `mcp` orchestration repo and its submodules. Applies to any submodule that owns a database. The index database owned by the TokenSaver submodule is the first candidate.

## Target layout (from the repo)

- `mcp` is an orchestration repo with no application source. It pins three submodules: `TokenSaver`, `Common` (wip branch), `SimpleModelServer` (wip branch).
- `TokenSaver` contains the MCP server, the AgentHelpers adapters, and the VS Code extension. It also holds the indexer and its database. Confirm the database location and owning project inside `TokenSaver` before the first unit.
- `Common` holds shared contracts and core code used by several projects.
- Each submodule is its own git repo with its own CLAUDE.md, docs, and plans. Work inside the submodule when changing its code.

## Prompt

```text
Goal: make the index database in the TokenSaver submodule the single point of database access. Other projects in mcp (the MCP server, the AgentHelpers adapters, the VS Code extension, and any client tooling) reach index data only through DTOs on the server's API.

Repo setup:
- Work inside the submodule that owns the change. Do not change files in the mcp superproject except the submodule pointer.
- Create a branch with the same name in each submodule you touch, from the same base. Keep the superproject pointer on that submodule branch.
- Push submodule branches before the superproject.
- The default branch is `master` in this repo. Branch from it unless the submodule's rules name another base.

Before any code:
1. Read the root CLAUDE.md, the submodule's CLAUDE.md, and every path-scoped rule under .claude/rules that matches the files you touch.
2. Work in a git worktree on a new branch. Do not edit the main checkout.
3. Read the submodule's todo items that relate to the indexer (for example: index on pull via a git hook, and prune removed or ignored files from the database). Those are the first candidates for the single-point change.
4. List your open questions and ask them before planning. Do not guess at them.

Target architecture:
- Database owner: only the indexer project owns the database context, entities, and repository implementations. Other projects must not reference the database project or its entities.
- Contracts: each repository gets a DTO interface in the contracts project, with the name of the old interface. The old interface is renamed to a write repository and stays server-side.
- Server adapter: a DTO repository implements the DTO interface by calling the write repository and converting with extension methods. Enum DTOs mirror entity enums by member name and convert with Enum.Parse.
- API: each DTO operation is exposed on a versioned route in the MCP server. Validate input at the boundary.
- Clients: the AgentHelpers adapters and the VS Code extension implement the DTO interfaces through an HTTP-backed remote class. Register server services and client services in their own DI blocks.
- Shared contracts in Common must not import the database entities. Replace entity types with DTO types.

Method (one unit per type or repository, each committed locally):
1. Add architecture gate tests first: scan project files and source of client projects for database-project references. They should fail before the change and pass after.
2. Per unit: add the DTO, the mapping, the server DTO repository, the remote class, and the DI registrations. Update consumers and tests.
3. Build serially, one build at a time. Parallel builds cause stale-output errors. Run affected test suites with the no-build option.
4. Commit each unit locally. Write each commit message to a file and commit with it. Stage only that unit's files.

Rules:
- Do not push and do not open a PR until asked.
- No AI attribution in commits or PRs.
- Do not rewrite files with stream-editing tools. Read the file, then use the edit tool.
- Do not read docs or archive folders unless asked.
- Keep the plan in a plan file and mark each unit done when committed.

Done when: the gate tests pass, client projects have no database references, every affected suite passes (report counts and skips), and each submodule branch has one commit per unit. Update the superproject pointer last.
Final message: list the commits per submodule, test results, and open questions. Do not push.
```

## Notes
- The todo items (index on pull, prune removed or ignored files) are a natural first unit: they both change indexer writes.
- Keep the gate tests first. They prove the boundary holds in every submodule that touches the database.
