# Token Optimization Helper

This helper guides optimizing token usage when working with TokenSaver. The TokenSaver project is already loaded into context alongside 30+ deferred tool schemas that consume ~20k tokens even when unused.

## Quick Start

### 1. Use `/fewer-permission-prompts` to Reduce Permission Prompts

When you start a new TokenSaver session, run:
```
/fewer-permission-prompts
```

This scans your transcripts and automatically adds safe read-only Bash/MCP tools to `.claude/settings.json` under `permissions.allow`, so you won't be interrupted by repetitive approval dialogs.

**What it does:**
- Finds common patterns in your recent tool calls
- Adds low-risk patterns to the allowlist (e.g., `Bash(git status)`, `Read(src/**)`)
- Preserves destructive/risky operations (git push, delete, etc.) behind approval gates

---

### 2. Lazy-Load Tools via ToolSearch Instead of Keeping Schemas Loaded

Deferred tool schemas sit in your context consuming tokens until you use them. Instead of loading all schemas upfront, load them on-demand with `ToolSearch`:

#### When you need a specific tool:
```
ToolSearch with query "select:mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__navigate"
```
This loads ONLY those schemas for this turn. Next turn, they're gone again.

#### When you need a category of tools:
```
ToolSearch with query "computer-use"
```
This matches and loads all computer-use MCP tools by keyword.

#### One-time fetch of a knowledge base:
```
ToolSearch with query "select:mcp__bdb76430-8edd-4beb-a650-a8761b3896fb__microsoft_docs_search"
```

**Pro tip:** Batch-load related tools in ONE ToolSearch call:
```
ToolSearch with query "select:tool1,tool2,tool3"
```
Not three separate calls — that's inefficient.

---

### 3. Disable Unused MCP Servers

Two layers:

#### Layer 1: Document disabled servers in `.tokensaver/mcp.json` (team reference)
```json
{
  "disabledMcpServers": [
    "datadog",           // requires auth, not used
    "pagerduty",         // requires auth, not used
    "intercom",          // requires auth, not used
    "monday",            // requires auth, not used
    "asana",             // requires auth, not used
    "figma",             // requires auth, not used
    "microsoft_docs_search",
    "microsoft_docs_fetch",
    "microsoft_code_sample_search"
  ],
  "lazyLoadTools": true,
  "notes": "Document which servers are disabled and why, for team clarity"
}
```

#### Layer 2: Enforce in `.claude/settings.json` (actually disables in Claude Code)
```json
{
  "disabledMcpjsonServers": [
    "datadog",
    "pagerduty",
    "intercom",
    "monday",
    "asana",
    "figma",
    "microsoft_docs_search",
    "microsoft_docs_fetch",
    "microsoft_code_sample_search",
    "playwright"
  ]
}
```

**Save ~5-8k tokens** by removing auth APIs you'll never use without explicit authentication.

---

### 4. Apply Settings & Verify Token Savings

After editing:

1. **Restart the Claude session** — new context with disabled servers removed
2. **Check token usage** — run another `/context .` and compare before/after
3. **Note the savings** — typically 5-10% of system overhead

Expected before/after:
- **Before:** 50k tokens (25% overhead)
- **After:** 42k tokens (21% overhead)

---

## Token Breakdown by Category

| Category | Tokens | On by Default? | Action |
|----------|--------|----------------|--------|
| Auth-required APIs (12) | 8k | Yes | **Disable** all unless authenticated |
| Windows-MCP (20 tools) | 4k | Yes | Keep if using `dragonfire` remote; disable if local-only |
| Playwright Browser | 3k | Yes | **Disable** if using Claude-in-Chrome (redundant) |
| Microsoft Learn tools | 2k | Yes | **Disable**; use ToolSearch when needed |
| Misc tools/MCPs | 3k | Yes | Keep common ones; disable the rest |

---

## Enabling Token Optimization

Token optimization is **opt-in per session**. To enable it:

### Option A: Per-Session (Local Override)
Create `.claude/settings.local.json` with:
```json
{
  "disabledMcpjsonServers": [
    "datadog", "pagerduty", "intercom", "monday", "asana", "figma",
    "microsoft_docs_search", "microsoft_docs_fetch", "microsoft_code_sample_search", "playwright"
  ]
}
```

Then restart Claude Code. The `.local.json` file is gitignored and won't affect other team members.

### Option B: Team-Wide (Checked In)
If the team wants token optimization always on, merge the config from `.claude/settings.token-optimization.json` into `.claude/settings.json` and commit it.

## Workflow: Before Working on TokenSaver

1. **Enable token optimization** (Option A or B above)
2. **Run `/fewer-permission-prompts`** once per session to reduce permission dialogs
3. **Use ToolSearch lazily** — when you need a tool, load it on-demand instead of keeping it in context
4. **Verify** with check current token usage at start of session vs. without optimization

---

## Reference: ToolSearch Cheat Sheet

```bash
# Load a single tool
ToolSearch with query "select:mcp__claude-in-chrome__navigate"

# Load multiple tools at once (batch)
ToolSearch with query "select:mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__computer"

# Search by keyword (e.g., all computer-use tools)
ToolSearch with query "computer-use"

# Search by provider (e.g., all GitHub tools)
ToolSearch with query "github"

# Search with max results
ToolSearch with query "browser" max_results 10
```

---

## Expected Token Impact

Running all three optimizations:
- **Disable 9 unused auth APIs:** saves 5-8k tokens
- **Use ToolSearch for docs tools:** saves 1-2k per use (not always loaded)
- **Reduce permission prompts:** saves interruptions, keeps context clean

**Total:** 15-25% reduction in unavoidable overhead, keeping your 150k work tokens intact.
