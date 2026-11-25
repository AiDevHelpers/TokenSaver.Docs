# Instruction store contract

Public contract for the editable instruction store and its MCP tools.

## Store location

- Folder: one subfolder per instruction, each containing `SKILL.md`.
- Default: `%USERPROFILE%\.tokensaver\instructions\skills`.
- Override: environment variable `TOKENSAVER_INSTRUCTIONS_DIR`.
- A missing folder is not an error; the store is simply empty.
- The repo ships defaults under `instructions/skills/`; the installer copying them to the store
  location is not implemented yet.

## File format

`SKILL.md` starts with a frontmatter block:

```
---
name: tdd
description: Test first: write and record a failing test before implementing.
---
Body...
```

- `name` must match the folder name and be lowercase letters, digits, and hyphens.
- `description` is one line and is what `list_instructions` shows.
- A folder without `SKILL.md` is ignored.

## MCP tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_instructions` | none | One line per instruction: `- name: description`, sorted by name. |
| `get_instruction` | `name` (string) | The full `SKILL.md` text, frontmatter included. |

- An unknown or invalid name returns a message naming the problem; it never reads outside the store.
- An empty store returns a message that gives the store path and the env var to set.

## Automatic injection

- `BuildConciseContext` appends the store sections relevant to its `prompt` to the response,
  each tagged `<!-- instruction: <name> > <heading> -->`.
- Relevance is a heuristic: prompt terms (4+ letters, trailing `s` stripped, common words dropped)
  are counted in each `##`/`#` section's body (1 point each) and heading (2 points each). Sections
  scoring 3 or more are kept, highest first, capped at 4000 characters.
- Disable with `TOKENSAVER_INSTRUCTIONS_INJECT=off`. The on-demand tools always work.
- Injection goes into the response, not the prompt: the client only sees what a tool returns.

## Not yet implemented

- A `repoHelper`/`ProgramData` config key for the store path and injection toggle (env vars only for now).
- Installer copy from repo defaults to the store folder.
- Stubs replacing the harness skill files (requires approval).
