<!-- tokensaver:global-instructions:start (auto-synced from %USERPROFILE%\.claude\CLAUDE.md — edit the source there, not here) -->
<!-- source: C:\Users\rsper\.claude\CLAUDE.md -->
# CLAUDE.md — User Instructions

Personal instructions that apply to every project on this machine.

## Environment
- Windows 11, PowerShell 7.

## Writing instructions
- **Always make instructions lazy-load whenever possible.** Prefer mechanisms that keep guidance out of the session until it's actually needed over adding to always-loaded files.
- Detailed how-to for this lives in `~/.claude/rules/writing-instructions.md`, which itself loads on demand only when editing instruction files.

## Subagents
- Prefer delegating to subagents when possible (parallelizable, isolated, or research/search-heavy work) rather than doing it all in the main thread.
- Default subagent model to haiku. If a subagent's result looks confused, incomplete, or wrong, retry once on sonnet before reporting back.


<!-- source: F:\mcp\CLAUDE.md -->
# CLAUDE.md

Orchestration/glue repo (`mcp`) over two submodules — no application source of its own:
- `SimpleModelServer/` — rsperry79/SimpleModelServer: Ollama-compatible router (SimpleModelServer.Server) + libs/chat.
- `TokenSaver/` — rsperry79/TokenSaver: TokenSaver.MCP server, AgentHelpers.* adapters, VS Code ext.

Work inside the relevant submodule when touching its code — each is its own git repo with its own
CLAUDE.md/docs. Empty submodule folder → `git submodule update --init --recursive`.

Build/run commands and orchestration-layer pitfalls live in `.claude/rules/` — path-scoped, load
on demand.

<!-- source: F:\mcp\TokenSaver\CLAUDE.md -->
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`TokenSaver.MCP` is an ASP.NET Core MCP server (net10.0) that exposes workspace indexing, code
search, context building, file editing, and Ollama calls as MCP tools to Claude and other AI
clients. Ships with a VS Code extension (`TokenSaver.VsCodeExt`) and per-agent context-formatting
adapters (`TokenSaver.AgentHelpers.*`).

This is its own git repo, usually vendored as a submodule under the `mcp` orchestration repo. Work
here, not at the parent, when touching TokenSaver code.

## Environment
Detailed guidance lives in the "Environment" sub-doc, loaded on demand.
## Dev Environment Startup

**Port allocation** (fixed by convention): Ollama 11434, SimpleModelServer.Server 11435, TokenSaver.MCP 11436.

**Dev server startup**:
1. Run `.\scripts\run-dev-server.ps1` in a visible PowerShell terminal (reuse across stop/start, 
   never leave prod service as the thing under test).
2. Script checks if the port is in use: if yes and the process is `TokenSaver.MCP.exe` from 
   `C:\Program Files\TokenSaver` (prod service), it stops the service. If yes and it's something 
   else (stale dev instance), pass `-Force` to kill it.
3. Once the dev server is running, open IDE instances via the MCP `LaunchIde` tool 
   (`type: "VsCode" | "VisualStudio2026"`, `workspaceRoot: "F:\\mcp\\TokenSaver"`).

See `.claude/rules/commands.md` for detailed command reference.

## Architecture
Detailed guidance lives in the "Architecture" sub-doc, loaded on demand.
## Gotchas
Detailed guidance lives in the "Gotchas" sub-doc, loaded on demand.
## Versioning

Nerdbank.GitVersioning derives all versions from `version.json` + git height. No manual per-release
bumps outside `version.json`. See `docs/versioning.md`.
<!-- tokensaver:global-instructions:end -->
