# LocalHelper — New Tools Implementation Plan (v2: token-economy design)

Assumption: server is Node.js (typical for `.mcpb`/DXT packages). If it's actually
Python, say so and I'll flip the stubs — logic/manifest stay the same either way.

---

## Core idea: Claude should almost never see raw output

Every tool result gets charged against the calling conversation's context window —
that's the token budget you're trying to protect (same motivation as
BuildConciseContext/ContextHygiene, extended to every new tool). The fix is
architectural, not per-tool: **no tool returns raw bulk text to Claude.**
Everything bulky (logs, diffs, test output, file contents, grep hits) gets routed
through a local distillation step first, and only the distilled result — plus an
optional pointer to the raw artifact on disk — comes back.

```
 Raw source (log file, diff, stdout, files)
        │
        ▼
 ┌────────────────┐
 │  Gather (JS)    │  no LLM — deterministic collection/parsing
 └────────────────┘
        │  (often 2k–50k tokens of raw text)
        ▼
 ┌────────────────┐
 │  Distill        │  local Ollama call, role-specific prompt,
 │  (Ollama)       │  hard output ceiling (e.g. 200–400 tokens)
 └────────────────┘
        │  (compact structured result)
        ▼
 Claude sees: summary + counts + file:line refs + "raw saved to X if you need it"
```

This turns every "dump N KB of log/diff/output" tool into a "here's the 5-line
verdict" tool. Claude can always ask for the raw artifact by path if the summary
isn't enough — that's a cheap, rare escape hatch rather than the default path.

### Per-feature config: every token-saving mechanism gets its own on/off switch

`LOCALHELPER_TERSE` (added below) already covers one axis. Each *independent*
saving mechanism should be independently toggleable too — so if, say,
distillation for a given tool turns out not worth it (see `WorthKeeping`
below) or the tracker DB writes add unwanted I/O, you can turn just that off
without touching the others. All default to on (`1`); this is a kill-switch
list, not an opt-in list.

```
LOCALHELPER_ENABLE_DISTILL=1        # master switch for distill() itself — 0 = every tool returns raw text, uncompressed
LOCALHELPER_ENABLE_TERSE=1          # allows LOCALHELPER_TERSE to take effect at all — 0 = terse param/env ignored, normal prompts only
LOCALHELPER_ENABLE_RAW_RETENTION=1  # write raw output to LOCALHELPER_DATA/raw/... — 0 = skip the write, summary-only, no escape hatch
LOCALHELPER_ENABLE_SAVINGS_TRACKING=1  # record rows to the token_savings table — 0 = distill() runs but doesn't log, TokenSavingsReport/WorthKeeping return empty
LOCALHELPER_ENABLE_SUMMARY_EMBEDDING=1 # EmbedCache/IndexRepo embed the chunk summary (cheap) — 0 = embed raw chunk text instead (more accurate recall, heavier disk/compute, no token savings angle since it's not returned to Claude anyway)
```

Each flag gates exactly one mechanism and nothing else, so turning one off
doesn't silently disable another:

- **`LOCALHELPER_ENABLE_DISTILL=0`** short-circuits `distill()` to return the
  raw text untouched (still capped at 16000 chars to avoid a runaway
  response) — the fallback path every tool already has via its `verbose`
  param, just promoted to a standing config instead of a per-call flag.
- **`LOCALHELPER_ENABLE_TERSE=0`** makes `LOCALHELPER_TERSE=1` and any
  per-call `terse:true` a no-op — useful if terse output turns out to compress
  past the point of usefulness for your workflow, without losing the rest of
  the distillation pipeline.
- **`LOCALHELPER_ENABLE_RAW_RETENTION=0`** skips the `fs.writeFile` raw-artifact
  step entirely (ContainerLogs, RunTests, etc.) — saves disk I/O and
  `LOCALHELPER_DATA` growth if you never actually use the escape hatch, at
  the cost of losing it.
- **`LOCALHELPER_ENABLE_SAVINGS_TRACKING=0`** skips the `recordSavings()`
  call inside `distill()` — avoids a DB write on every single tool call if
  you don't care about the analytics, though this means `WorthKeeping`/
  `TokenSavingsReport` have nothing to report on while it's off.
- **`LOCALHELPER_ENABLE_SUMMARY_EMBEDDING=0`** switches `IndexRepo` to embed
  the raw chunk text instead of the one-line summary — this one is not a
  token-savings toggle in the Claude-facing sense (embeddings never reach
  Claude either way) but is included because it's the other config knob that
  trades local compute/storage for a quality difference in `SemanticGrep`
  recall, and belongs in the same list rather than buried in Phase 2.

### Shared building block: `lib/distill.js`

Every tool that produces bulk text calls this instead of returning text directly.

```js
// lib/distill.js
const { callOllama } = require('./ollama');

const ENABLE_DISTILL = process.env.LOCALHELPER_ENABLE_DISTILL !== '0';
const ENABLE_TERSE_FEATURE = process.env.LOCALHELPER_ENABLE_TERSE !== '0';
const ENABLE_RAW_RETENTION = process.env.LOCALHELPER_ENABLE_RAW_RETENTION !== '0';
const ENABLE_SAVINGS_TRACKING = process.env.LOCALHELPER_ENABLE_SAVINGS_TRACKING !== '0';

const ROLE_PROMPTS = {
  test_failure: (raw) => `You are compressing test output for an AI coding assistant that pays per token.
Extract ONLY: (1) which tests failed, (2) the one-line reason for each, (3) the single most likely
file/line to fix. Omit passing tests, stack trace noise, and framework boilerplate.
Max 6 lines total.\n\nRAW OUTPUT:\n${raw}`,

  log_errors: (raw) => `Extract only new/anomalous error or warning lines from this log.
Deduplicate repeated errors into one line with a count. Ignore routine INFO/DEBUG noise.
Max 8 lines.\n\nLOG:\n${raw}`,

  diff_summary: (raw) => `Summarize this git diff as a commit message: one-line imperative summary,
then up to 4 bullets for notable changes. No preamble.\n\nDIFF:\n${raw}`,

  lint_summary: (raw) => `Group these lint results by rule. Report rule name, count, and ONE representative
file:line per rule. Drop anything auto-fixed already.\n\nLINT OUTPUT:\n${raw}`,

  generic_condense: (raw) => `Condense this to the minimum a developer needs to decide their next action.
Max 5 lines.\n\nCONTENT:\n${raw}`
};

async function distill({ role, raw, maxTokens = 300, model = 'qwen2.5-coder:7b' }) {
  if (!raw || raw.trim().length === 0) {
    return { summary: '(empty)', raw_tokens: 0, distilled_tokens: 0 };
  }
  // Master kill-switch: skip the Ollama call entirely and hand back raw text
  // (still capped) if distillation is turned off server-wide.
  if (!ENABLE_DISTILL) {
    const capped = raw.slice(0, 16000);
    return { summary: capped, raw_tokens: estimateTokens(raw), distilled_tokens: estimateTokens(capped), distilled: false };
  }
  const promptFn = ROLE_PROMPTS[role] || ROLE_PROMPTS.generic_condense;
  const prompt = promptFn(raw.slice(0, 16000)); // cap input to keep local inference fast
  const summary = await callOllama({ model, prompt, max_tokens: maxTokens });
  return {
    summary,
    raw_tokens: estimateTokens(raw),
    distilled_tokens: estimateTokens(summary)
  };
}

function estimateTokens(s) {
  return Math.ceil(s.length / 4); // rough; swap for gpt-tokenizer if precision matters
}

module.exports = { distill, estimateTokens };
```

Every tool below reports `raw_tokens` / `distilled_tokens` in its response so you
can see the savings ratio directly in the tool result — useful for tuning which
tools actually need distillation vs. which are already small.

### Escape hatch: raw artifact retention

`distill()` doesn't delete the source — gather steps write raw output to
`%LOCALHELPER_DATA%\raw\<tool>\<timestamp>.txt` before distilling, and the tool
result includes that path. Claude only pulls it (via a filesystem read, not
LocalHelper) if the distilled summary is insufficient. This means you never lose
information, you just don't pay for it by default.

Gated by `LOCALHELPER_ENABLE_RAW_RETENTION` (see the per-feature config block
above) — each gather step wraps its `fs.writeFile(rawPath, raw)` call in a
check of that flag and omits the `full: <path>` reference from its response
when off, e.g.:

```js
// pattern every gather step (ContainerLogs, RunTests, etc.) follows
let rawPath = null;
if (process.env.LOCALHELPER_ENABLE_RAW_RETENTION !== '0') {
  rawPath = path.join(process.env.LOCALHELPER_DATA, 'raw', 'containerLogs', `${container_name}-${Date.now()}.txt`);
  await fs.mkdir(path.dirname(rawPath), { recursive: true });
  await fs.writeFile(rawPath, raw);
}
// ...later, only append "; full log: ${rawPath}" to the response text if rawPath is non-null
```

---

## Terse-mode: global compression toggle for tool returns

Everything above already routes bulk text through `distill()`. Terse-mode is an
orthogonal knob on top of that pipeline: a single env var that, when set,
tightens every distilled response further and switches the prompt style to a
caveman-like telegraphic register (drop articles/filler, fragments over
sentences, no preamble) — same content, fewer output tokens per tool call,
same reasoning cost since it's Ollama doing the compressing, not Claude.

### Config
```
LOCALHELPER_TERSE=1        # 0 (default) = normal role prompts / normal maxTokens
                            # 1 = terse prompts + reduced maxTokens ceiling everywhere
```

### `lib/distill.js` changes
Two additions: a terse variant of every existing role prompt, and a global
maxTokens multiplier applied when terse mode is on. Callers don't need to
change — `distill()` reads `LOCALHELPER_TERSE` itself so every existing call
site (ContainerLogs, RunTests, LintFix, DiffSummarize, BuildWatch,
SessionSnapshot) gets the benefit for free.

```js
// lib/distill.js (additions)
// Gate on both: LOCALHELPER_ENABLE_TERSE is the feature kill-switch (0 = terse
// can never activate, ignores the env/per-call flag below entirely).
// LOCALHELPER_TERSE is the actual mode toggle once the feature is enabled.
const TERSE = ENABLE_TERSE_FEATURE && process.env.LOCALHELPER_TERSE === '1';
const TERSE_MAX_TOKENS_RATIO = 0.5; // terse mode halves whatever maxTokens the caller asked for

const TERSE_PREFIX = `Answer in fragments. Drop articles, filler words, and preamble.
No "here is" / "this shows". Telegraphic style — verdict first, no restating the question.\n\n`;

const ROLE_PROMPTS_TERSE = {
  test_failure: (raw) => `${TERSE_PREFIX}Failed tests + 1-line reason each + most likely fix file:line.
Max 4 lines. Skip passing tests, stack noise.\n\nRAW:\n${raw}`,

  log_errors: (raw) => `${TERSE_PREFIX}New/anomalous errors only, dedup repeats w/ count.
Max 4 lines.\n\nLOG:\n${raw}`,

  diff_summary: (raw) => `${TERSE_PREFIX}One-line commit summary + up to 2 bullets max.\n\nDIFF:\n${raw}`,

  lint_summary: (raw) => `${TERSE_PREFIX}Rule name + count + one file:line per rule. Max 4 lines.\n\nLINT:\n${raw}`,

  generic_condense: (raw) => `${TERSE_PREFIX}Absolute minimum to decide next action. Max 3 lines.\n\n${raw}`
};

async function distill({ role, raw, maxTokens = 300, model = 'qwen2.5-coder:7b' }) {
  if (!raw || raw.trim().length === 0) {
    return { summary: '(empty)', raw_tokens: 0, distilled_tokens: 0 };
  }
  const prompts = TERSE ? ROLE_PROMPTS_TERSE : ROLE_PROMPTS;
  const promptFn = prompts[role] || prompts.generic_condense;
  const effectiveMaxTokens = TERSE ? Math.round(maxTokens * TERSE_MAX_TOKENS_RATIO) : maxTokens;
  const prompt = promptFn(raw.slice(0, 16000));
  const summary = await callOllama({ model, prompt, max_tokens: effectiveMaxTokens });
  return {
    summary,
    raw_tokens: estimateTokens(raw),
    distilled_tokens: estimateTokens(summary),
    terse: TERSE
  };
}
```

### Structured (non-prose) tools also get trimmed
`TokenBudget`, `EmbedCache` lookups, `SemanticGrep`, `DependencyAudit` don't go
through `distill()` at all today — they already return compact JSON, but the
JSON itself can carry avoidable weight (full row dumps, unrounded floats,
verbose keys). Terse-mode should also trim these directly rather than relying
on distill():

- `SemanticGrep`: when `LOCALHELPER_TERSE=1`, drop the `vector`/raw row fields
  before serializing (already partially done — audit that `score` stays
  rounded to 3 decimals, and consider trimming `summary` itself to first
  sentence only in terse mode).
- `EmbedCache` `get_by_path`: return `{name, chunk_type, start_line, end_line}`
  only in terse mode, omit `summary`/`vector` unless explicitly requested via
  a `full: true` param.
- `TokenBudget` / `DependencyAudit`: already minimal by construction — leave
  as-is, don't add terse handling here (matches the existing "no LLM needed"
  rationale for DependencyAudit above).

### Per-call override
Every tool's params should accept an optional `terse` boolean that overrides
the global env var for that one call, so Claude can request a fuller answer
mid-session without flipping the whole server's mode:

```js
async function distill({ role, raw, maxTokens = 300, model = 'qwen2.5-coder:7b', terse }) {
  // Feature kill-switch wins even over an explicit per-call terse:true — if
  // LOCALHELPER_ENABLE_TERSE=0, no caller can force terse mode on.
  const useTerse = ENABLE_TERSE_FEATURE && (typeof terse === 'boolean' ? terse : TERSE);
  // ...rest uses useTerse instead of the module-level TERSE constant
}
```

### Where this lands in build order
Bundle into the same pass as `lib/distill.js` (build-order step 1) — it's a
change to the shared building block, not a new tool, so there's no separate
phase entry. Every tool built afterward inherits it automatically. Retrofit
onto Phase 1 tools already shipped before this addition (ContainerLogs) as a
quick follow-up.

### Surfacing terse-mode to the calling AI

Terse-mode shouldn't be a silent server-side setting the calling AI has to
already know about — it needs to be discoverable (so a client knows the
option exists and how to use it) and visible in-flight (so the client can see
what mode is currently active and how much it's saving). Two mechanisms,
both needed:

**1. Advertise `terse` as a real param in every tool's MCP schema.**
Every tool's `inputSchema` gets the optional `terse: boolean` param described
in the per-call override above, with a description string the client actually
sees during tool discovery:

```js
// example addition to each tool's manifest entry
{
  name: "runTests",
  description: "Run the project's test suite. Returns PASS or a distilled failure summary.",
  inputSchema: {
    type: "object",
    properties: {
      project_path: { type: "string" },
      test_command: { type: "string" },
      verbose: { type: "boolean", description: "Return raw untruncated output instead of a distilled summary." },
      terse: {
        type: "boolean",
        description: "Force maximally compressed output for this call (telegraphic style, ~half the tokens of the default summary). Overrides the server's LOCALHELPER_TERSE setting for this call only."
      }
    },
    required: ["project_path"]
  }
}
```

This means any MCP client — not just one that's read this plan — can see via
normal tool introspection that terse output is an option, without needing
out-of-band documentation.

**2. Surface current mode + running savings as a context note on responses.**
Separate from the per-tool `terse`/`raw_tokens`/`distilled_tokens` fields
already in each response, add a lightweight, once-per-session context blurb —
similar in spirit to how CLAUDE.md conventions get surfaced to a calling
agent — so the client knows the server-wide default without having to probe
env vars or infer it from behavior. Simplest implementation: piggyback on the
MCP server's `initialize` response / server instructions field (most MCP
SDKs support a static `instructions` string returned at handshake), plus an
optional `x-localhelper-mode` note appended to the *first* tool response of a
session:

```js
// server startup / initialize handler
const SERVER_INSTRUCTIONS = `LocalHelper.MCP tools distill bulk output locally before
returning it. Current mode: ${process.env.LOCALHELPER_TERSE === '1' ? 'TERSE (compressed)' : 'NORMAL'}.
Pass terse:true/false on any call to override per-call. Raw output is always retained
on disk (path included in each response) even when a tool's summary is compressed.`;
```

```js
// lib/distill.js — session-level running total, reset per server process
let sessionRawTokens = 0, sessionDistilledTokens = 0;

async function distill({ role, raw, maxTokens = 300, model = 'qwen2.5-coder:7b', terse }) {
  // ...existing body...
  sessionRawTokens += raw_tokens;
  sessionDistilledTokens += distilled_tokens;
  return {
    summary, raw_tokens, distilled_tokens, terse: useTerse,
    session_savings_pct: sessionRawTokens > 0
      ? Math.round((1 - sessionDistilledTokens / sessionRawTokens) * 100)
      : 0
  };
}
```

Keep this to one line appended to the response text (e.g. `[terse: on, session
savings so far: 71%]`) rather than a verbose block — the point is cheap
visibility, not a new thing to read every call. Don't duplicate the
`SERVER_INSTRUCTIONS` handshake text into every response; that only needs to
go out once at session start.

### Build-order note
Both mechanisms are additions to the same `lib/distill.js` pass and the
existing manifest-wiring step — no new phase, no new build-order entry beyond
what's already listed for terse-mode above.

---

## Phase 1 — High value, low effort (build first)

### 1. TokenBudget
Pure function, no external deps, no LLM call (this one measures the economy, doesn't
participate in it).

```js
// tools/tokenBudget.js
const { estimateTokens } = require('../lib/distill');

async function tokenBudget({ content, threshold = 8000 }) {
  const tokens = estimateTokens(content);
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        tokens,
        threshold,
        over_budget: tokens > threshold,
        pct_of_threshold: Math.round((tokens / threshold) * 100)
      })
    }]
  };
}
module.exports = { tokenBudget };
```

### 2. SessionSnapshot / SessionRestore
Extends your existing CONTEXT.md pattern. Snapshot itself should also be distilled
before restore if it's grown large — restoring a stale 10k-token dump defeats the
purpose of a "concise context" tool.

```js
// tools/session.js
const fs = require('fs/promises');
const path = require('path');
const { distill } = require('../lib/distill');

async function sessionSnapshot({ session_id, context_blob, output_path }) {
  const dest = output_path || path.join(process.env.LOCALHELPER_DATA, 'sessions', `${session_id}.json`);
  await fs.mkdir(path.dirname(dest), { recursive: true });

  // if the incoming context blob is large, store a distilled version as the
  // "quick restore" and the full blob alongside for when detail is needed
  const { summary } = context_blob.length > 4000
    ? await distill({ role: 'generic_condense', raw: context_blob, maxTokens: 400 })
    : { summary: context_blob };

  await fs.writeFile(dest, JSON.stringify({
    session_id,
    saved_at: new Date().toISOString(),
    summary,
    full_blob_path: dest.replace('.json', '.full.txt')
  }));
  await fs.writeFile(dest.replace('.json', '.full.txt'), context_blob);

  return { content: [{ type: "text", text: `Saved snapshot: ${dest}` }] };
}

async function sessionRestore({ snapshot_path, full = false }) {
  const data = JSON.parse(await fs.readFile(snapshot_path, 'utf-8'));
  const text = full ? await fs.readFile(data.full_blob_path, 'utf-8') : data.summary;
  return { content: [{ type: "text", text }] };
}
module.exports = { sessionSnapshot, sessionRestore };
```

### 3. ContainerLogs
This is the clearest token sink otherwise — container logs are often pure noise.
Gather raw, distill to `log_errors` role, keep raw on disk.

```js
// tools/containerLogs.js
const Docker = require('dockerode'); // npm install dockerode
const fs = require('fs/promises');
const path = require('path');
const { distill } = require('../lib/distill');
const docker = new Docker(); // Windows named pipe by default

async function containerLogs({ container_name, tail_lines = 500, verbose = false }) {
  const container = docker.getContainer(container_name);
  const stream = await container.logs({ stdout: true, stderr: true, tail: tail_lines });
  const raw = stream.toString('utf-8');

  const rawPath = path.join(process.env.LOCALHELPER_DATA, 'raw', 'containerLogs', `${container_name}-${Date.now()}.txt`);
  await fs.mkdir(path.dirname(rawPath), { recursive: true });
  await fs.writeFile(rawPath, raw);

  if (verbose) return { content: [{ type: "text", text: raw }] };

  const { summary, raw_tokens, distilled_tokens } = await distill({ role: 'log_errors', raw });
  return {
    content: [{
      type: "text",
      text: `${summary}\n\n[${raw_tokens}→${distilled_tokens} tokens; full log: ${rawPath}]`
    }]
  };
}
module.exports = { containerLogs };
```

---

## Phase 2 — Ollama wiring / model routing backbone

### 4. ModelRoute (build this before DiffSummarize/SemanticGrep — everything depends on it)
Centralizes every local-model call so you tune models/prompts in one place instead
of per-tool.

```js
// tools/modelRoute.js
const { callOllama } = require('../lib/ollama');

const ROUTES = {
  code: 'qwen2.5-coder:7b',
  chat: 'llama3.2:3b',
  summarize: 'qwen2.5-coder:7b',
  embed: 'nomic-embed-text',
  rerank: 'qwen2.5-coder:7b'
};

async function modelRoute({ task_type, prompt, max_tokens = 400 }) {
  const model = ROUTES[task_type] || ROUTES.chat;
  const result = await callOllama({ model, prompt, max_tokens });
  return { content: [{ type: "text", text: result }] };
}
module.exports = { modelRoute, ROUTES };
```

### 5. DiffSummarize
```js
// tools/diffSummarize.js
const { execSync } = require('child_process');
const { distill } = require('../lib/distill');

async function diffSummarize({ repo_path, staged_only = false }) {
  const cmd = staged_only ? 'git diff --staged' : 'git diff';
  const diff = execSync(cmd, { cwd: repo_path, maxBuffer: 10 * 1024 * 1024 }).toString();
  if (!diff.trim()) return { content: [{ type: "text", text: "No changes." }] };

  const { summary, raw_tokens, distilled_tokens } = await distill({ role: 'diff_summary', raw: diff });
  return { content: [{ type: "text", text: `${summary}\n\n[${raw_tokens}→${distilled_tokens} tokens]` }] };
}
module.exports = { diffSummarize };
```

### 6. EmbedCache
Chunk-level now, not file-level — schema extended to hold the summary and
location metadata that chunking/summarization (below) produces. Lookups are
still pure disk reads; only new/changed chunks trigger Ollama calls.

```js
// tools/embedCache.js
const Database = require('better-sqlite3');
const { callOllama } = require('../lib/ollama');
const db = new Database(process.env.LOCALHELPER_CACHE_DB);
db.exec(`CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,        -- ${filePath}::${startLine}-${endLine}
  path TEXT,
  hash TEXT,                  -- hash of chunk content only, not whole file
  chunk_type TEXT,            -- 'function' | 'class' | 'md_section' | 'module'
  name TEXT,                  -- function/class name or heading text
  start_line INTEGER,
  end_line INTEGER,
  summary TEXT,               -- one-line local-model summary
  vector TEXT,                -- JSON embedding of the SUMMARY, not raw code
  updated_at TEXT
)`);
db.exec(`CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)`);

async function embedCache({ action, id, path: filePath }) {
  if (action === 'get') {
    const row = db.prepare('SELECT * FROM chunks WHERE id = ?').get(id);
    return { content: [{ type: "text", text: JSON.stringify(row || null) }] };
  }
  if (action === 'get_by_path') {
    const rows = db.prepare('SELECT * FROM chunks WHERE path = ?').all(filePath);
    return { content: [{ type: "text", text: JSON.stringify(rows) }] };
  }
  if (action === 'delete_by_path') {
    db.prepare('DELETE FROM chunks WHERE path = ?').run(filePath);
    return { content: [{ type: "text", text: "deleted" }] };
  }
  return { content: [{ type: "text", text: "unsupported action" }] };
}
module.exports = { embedCache, db };
```

Deliberate choice: **embed the summary, not the raw chunk.** A one-line
description ("validates JWT and refreshes if expired") embeds more cleanly for
natural-language queries than raw code tokens do, and it's what gets returned to
Claude anyway — so the embedding space and the display text are the same thing.
Raw code is still available by file:line if Claude needs to actually read it.

### 7. IndexRepo — structural chunking + summarization
This is the tool that does the actual work: walk the repo, split into
function/class/heading-sized chunks, summarize each with the local model, embed
the summary, cache it. Everything else (SemanticGrep) just queries this table.

```js
// tools/indexRepo.js
const fs = require('fs');
const path = require('path');
const glob = require('glob');
const crypto = require('crypto');
const pLimit = require('p-limit'); // npm install p-limit — bounds concurrent Ollama calls
const { callOllama } = require('../lib/ollama');
const { db } = require('./embedCache');

const IGNORE = ['**/node_modules/**', '**/.git/**', '**/dist/**', '**/build/**', '**/venv/**', '**/__pycache__/**'];

// --- chunkers -------------------------------------------------------------

// Heuristic function/class boundary detection. Not a real parser — good enough
// for indexing purposes, cheap, and language-agnostic-ish. Swap for tree-sitter
// later if boundary accuracy becomes a problem on a particular language.
const BOUNDARY_PATTERNS = {
  '.js':  /^\s*(export\s+)?(async\s+)?function\s+(\w+)|^\s*(export\s+)?class\s+(\w+)|^\s*const\s+(\w+)\s*=\s*(async\s*)?\(/,
  '.ts':  /^\s*(export\s+)?(async\s+)?function\s+(\w+)|^\s*(export\s+)?class\s+(\w+)/,
  '.py':  /^\s*(async\s+)?def\s+(\w+)|^\s*class\s+(\w+)/,
};

function chunkCode(filePath, content) {
  const ext = path.extname(filePath);
  const pattern = BOUNDARY_PATTERNS[ext];
  if (!pattern) return [{ type: 'module', name: path.basename(filePath), start: 1, end: content.split('\n').length, text: content }];

  const lines = content.split('\n');
  const boundaries = [];
  lines.forEach((line, i) => {
    const m = line.match(pattern);
    if (m) boundaries.push({ line: i + 1, name: m[3] || m[5] || m[2] || 'anonymous' });
  });
  if (boundaries.length === 0) {
    return [{ type: 'module', name: path.basename(filePath), start: 1, end: lines.length, text: content }];
  }

  const chunks = [];
  for (let i = 0; i < boundaries.length; i++) {
    const start = boundaries[i].line;
    const end = (i + 1 < boundaries.length) ? boundaries[i + 1].line - 1 : lines.length;
    chunks.push({
      type: 'function',
      name: boundaries[i].name,
      start,
      end,
      text: lines.slice(start - 1, end).join('\n')
    });
  }
  return chunks;
}

// Markdown: split on headings (any level), section runs until next heading of
// equal-or-higher level.
function chunkMarkdown(content) {
  const lines = content.split('\n');
  const headings = [];
  lines.forEach((line, i) => {
    const m = line.match(/^(#{1,6})\s+(.*)/);
    if (m) headings.push({ line: i + 1, level: m[1].length, text: m[2].trim() });
  });
  if (headings.length === 0) {
    return [{ type: 'md_section', name: '(no headings)', start: 1, end: lines.length, text: content }];
  }
  const chunks = [];
  for (let i = 0; i < headings.length; i++) {
    const start = headings[i].line;
    let end = lines.length;
    for (let j = i + 1; j < headings.length; j++) {
      if (headings[j].level <= headings[i].level) { end = headings[j].line - 1; break; }
    }
    chunks.push({ type: 'md_section', name: headings[i].text, start, end, text: lines.slice(start - 1, end).join('\n') });
  }
  return chunks;
}

// --- summarization ---------------------------------------------------------

const ENABLE_SUMMARY_EMBEDDING = process.env.LOCALHELPER_ENABLE_SUMMARY_EMBEDDING !== '0';

async function summarizeChunk(chunk) {
  const prompt = chunk.type === 'md_section'
    ? `One line only. Describe what this documentation section covers. Section heading: "${chunk.name}".\n\n${chunk.text.slice(0, 2000)}`
    : `One line only, no preamble. Describe what this function/class does and its key inputs/outputs.\n\nCODE (${chunk.name}):\n${chunk.text.slice(0, 2000)}`;
  return callOllama({ model: 'qwen2.5-coder:7b', prompt, max_tokens: 60, temperature: 0.1 });
}

// What gets embedded is controlled by LOCALHELPER_ENABLE_SUMMARY_EMBEDDING —
// on: embed the (already-computed) one-line summary; off: embed the raw
// chunk text instead, trading heavier disk/compute for recall accuracy.
function textToEmbed(chunk, summary) {
  return ENABLE_SUMMARY_EMBEDDING ? summary : chunk.text;
}

// --- main entry --------------------------------------------------------

async function indexRepo({ root_path, extensions = ['.js', '.ts', '.py', '.md'], concurrency = 4 }) {
  const pattern = `**/*{${extensions.join(',')}}`;
  const files = glob.sync(pattern, { cwd: root_path, absolute: true, ignore: IGNORE });

  const limit = pLimit(concurrency); // bounded concurrent Ollama calls — Ollama serializes
  let indexed = 0, skipped = 0, deleted = 0;

  for (const filePath of files) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const chunks = path.extname(filePath) === '.md' ? chunkMarkdown(content) : chunkCode(filePath, content);

    const seenIds = [];
    await Promise.all(chunks.map(chunk => limit(async () => {
      const id = `${filePath}::${chunk.start}-${chunk.end}`;
      seenIds.push(id);
      const hash = crypto.createHash('md5').update(chunk.text).digest('hex');
      const existing = db.prepare('SELECT hash FROM chunks WHERE id = ?').get(id);
      if (existing?.hash === hash) { skipped++; return; }

      const summary = await summarizeChunk(chunk);
      const vector = await callOllama({ model: 'nomic-embed-text', prompt: textToEmbed(chunk, summary), embed: true });

      db.prepare(`INSERT OR REPLACE INTO chunks
        (id, path, hash, chunk_type, name, start_line, end_line, summary, vector, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(id, filePath, hash, chunk.type, chunk.name, chunk.start, chunk.end, summary, JSON.stringify(vector), new Date().toISOString());
      indexed++;
    })));

    // prune chunks for this file that no longer exist (function deleted/renamed)
    const stale = db.prepare('SELECT id FROM chunks WHERE path = ?').all(filePath)
      .filter(row => !seenIds.includes(row.id));
    stale.forEach(row => { db.prepare('DELETE FROM chunks WHERE id = ?').run(row.id); deleted++; });
  }

  // prune chunks for files that no longer exist at all
  const allPaths = new Set(files);
  const dbPaths = db.prepare('SELECT DISTINCT path FROM chunks').all().map(r => r.path);
  dbPaths.filter(p => !allPaths.has(p)).forEach(p => {
    const n = db.prepare('DELETE FROM chunks WHERE path = ?').run(p).changes;
    deleted += n;
  });

  return { content: [{ type: "text", text: JSON.stringify({ files: files.length, chunks_indexed: indexed, chunks_skipped: skipped, chunks_deleted: deleted }) }] };
}
module.exports = { indexRepo, chunkCode, chunkMarkdown };
```

Run this as its own tool call (not inline in SemanticGrep) so a big first index
doesn't block a query, and re-running it later only pays for changed chunks —
the hash check is per-chunk now, not per-file, so editing one function in a
500-line file only re-summarizes and re-embeds that one function.

### 8. SemanticGrep
Now queries chunk-level summaries instead of file-level vectors — results are
function/section granular, and the summary text itself is often enough for
Claude to decide relevance without reading the file at all.

```js
// tools/semanticGrep.js
const { callOllama } = require('../lib/ollama');
const { db } = require('./embedCache');

function cosineSim(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

async function semanticGrep({ query, path_filter, top_k = 5 }) {
  const queryVec = await callOllama({ model: 'nomic-embed-text', prompt: query, embed: true });

  const rows = path_filter
    ? db.prepare('SELECT * FROM chunks WHERE path LIKE ?').all(`%${path_filter}%`)
    : db.prepare('SELECT * FROM chunks').all();

  const scored = rows.map(row => ({
    ...row,
    score: cosineSim(queryVec, JSON.parse(row.vector))
  })).sort((a, b) => b.score - a.score).slice(0, top_k);

  // Claude gets name + summary + file:line — not raw code. It reads the actual
  // file only for the 1-2 hits it decides are actually relevant.
  return {
    content: [{
      type: "text",
      text: JSON.stringify(scored.map(s => ({
        file: s.path,
        lines: `${s.start_line}-${s.end_line}`,
        type: s.chunk_type,
        name: s.name,
        summary: s.summary,
        score: s.score.toFixed(3)
      })))
    }]
  };
}
module.exports = { semanticGrep };
```

---

## Phase 3 — Shell-out tools (Windows-only, flag in manifest)

### 8. RunTests
This is the single biggest per-call token sink of the shell-out tools — pytest/jest
output on a real failure can be 10-30k tokens of stack trace and passing-test
noise. Distill role `test_failure` cuts this to a handful of lines.

```js
// tools/runTests.js
const { exec } = require('child_process');
const util = require('util');
const fs = require('fs/promises');
const path = require('path');
const { distill } = require('../lib/distill');
const execAsync = util.promisify(exec);

async function runTests({ project_path, test_command, verbose = false }) {
  const cmd = test_command || 'pytest -q';
  let raw, passed;
  try {
    const { stdout } = await execAsync(cmd, { cwd: project_path, maxBuffer: 20 * 1024 * 1024 });
    raw = stdout; passed = true;
  } catch (err) {
    raw = err.stdout || err.message; passed = false;
  }

  const rawPath = path.join(process.env.LOCALHELPER_DATA, 'raw', 'runTests', `${Date.now()}.txt`);
  await fs.mkdir(path.dirname(rawPath), { recursive: true });
  await fs.writeFile(rawPath, raw);

  if (passed) return { content: [{ type: "text", text: "PASS (all tests)" }] };
  if (verbose) return { content: [{ type: "text", text: raw }] };

  const { summary, raw_tokens, distilled_tokens } = await distill({ role: 'test_failure', raw });
  return { content: [{ type: "text", text: `FAIL\n${summary}\n\n[${raw_tokens}→${distilled_tokens} tokens; full: ${rawPath}]` }] };
}
module.exports = { runTests };
```

### 9. LintFix
Same pattern — `lint_summary` role groups by rule instead of dumping every line.

```js
// tools/lintFix.js
const { exec } = require('child_process');
const util = require('util');
const { distill } = require('../lib/distill');
const execAsync = util.promisify(exec);

async function lintFix({ project_path, lint_command, auto_fix = true }) {
  const cmd = lint_command || (auto_fix ? 'eslint . --fix' : 'eslint .');
  let raw;
  try {
    const { stdout } = await execAsync(cmd, { cwd: project_path, maxBuffer: 10 * 1024 * 1024 });
    raw = stdout;
  } catch (err) {
    raw = err.stdout || err.message; // eslint exits non-zero when issues remain
  }
  if (!raw.trim()) return { content: [{ type: "text", text: "Clean — no remaining lint issues." }] };

  const { summary, raw_tokens, distilled_tokens } = await distill({ role: 'lint_summary', raw });
  return { content: [{ type: "text", text: `${summary}\n\n[${raw_tokens}→${distilled_tokens} tokens]` }] };
}
module.exports = { lintFix };
```

### 10. BuildWatch
```js
// tools/buildWatch.js
const fs = require('fs/promises');
const { distill } = require('../lib/distill');

async function buildWatch({ log_path, since_line = 0 }) {
  const content = await fs.readFile(log_path, 'utf-8');
  const lines = content.split('\n');
  const newLines = lines.slice(since_line);
  if (newLines.length === 0) return { content: [{ type: "text", text: JSON.stringify({ new_errors: [], last_line: lines.length }) }] };

  const raw = newLines.join('\n');
  const { summary } = raw.length > 800
    ? await distill({ role: 'log_errors', raw })
    : { summary: raw };

  return { content: [{ type: "text", text: JSON.stringify({ summary, last_line: lines.length }) }] };
}
module.exports = { buildWatch };
```

---

## DependencyAudit (no LLM needed — already token-cheap by design)
Kept out of the distillation pipeline entirely: it should return structured JSON
(package, current version, latest, CVE ids) rather than prose, which is already
minimal-token by construction. Adding a local-model pass here would only add
latency for no savings.

---

## Manifest wiring
Add each tool's `require` + registration to your existing DXT entrypoint, and
append the corresponding tool block from the earlier manifest.json spec. For
Phase 3 tools (and ContainerLogs, which needs the Docker socket), keep:
```json
"compatibility": { "platforms": ["win32"] }
```

## Config additions needed
```
LOCALHELPER_DATA=F:\LocalHelper\data        # raw artifact + session storage root
LOCALHELPER_CACHE_DB=F:\LocalHelper\cache.sqlite

# Per-feature kill switches for every token-saving mechanism (all default to
# "1" / on — see "Per-feature config" section above for full rationale per flag)
LOCALHELPER_ENABLE_DISTILL=1
LOCALHELPER_ENABLE_TERSE=1
LOCALHELPER_ENABLE_RAW_RETENTION=1
LOCALHELPER_ENABLE_SAVINGS_TRACKING=1
LOCALHELPER_ENABLE_SUMMARY_EMBEDDING=1

# Mode toggle + tuning, only meaningful while their respective ENABLE_* flag is on
LOCALHELPER_TERSE=0                    # 1 = terse prompts everywhere (needs LOCALHELPER_ENABLE_TERSE=1)
LOCALHELPER_WORTH_IT_MIN_PCT=30        # WorthKeeping / TokenSavingsReport verdict threshold
LOCALHELPER_WORTH_IT_MAX_MS=4000       # WorthKeeping / TokenSavingsReport verdict threshold
```

## Dependencies to add
```
npm install dockerode better-sqlite3 glob
```
(`better-sqlite3` needs native build tools on Windows — likely already present
from other native npm modules; flag if node-gyp gives you grief.)

## Suggested build order
1. `lib/distill.js` + `lib/ollama.js` wrapper (the backbone everything else uses)
2. TokenBudget (validates estimateTokens, no LLM dependency to debug)
3. ModelRoute
4. ContainerLogs (dockerode is a known quantity for you; good first distill() consumer)
5. RunTests → LintFix → BuildWatch (biggest raw-token savings, same pattern 3x)
6. SessionSnapshot/Restore
7. DiffSummarize
8. EmbedCache → IndexRepo → SemanticGrep (biggest architectural payoff, save for last)

## Measuring the win: per-tool token savings tracking

`raw_tokens`/`distilled_tokens` on each response tells you the savings for
*that one call*. To answer "what's actually saving the most tokens" you need
it broken down **by tool/role, aggregated over time** — otherwise you're
guessing whether RunTests or ContainerLogs is pulling its weight. This
replaces the single flat `token_savings.log` idea with a structured store and
a queryable report.

### Storage: SQLite table, not a flat log
Reuse the existing `LOCALHELPER_CACHE_DB` (already opened by EmbedCache) so
there's one DB file, not two. A flat log needs to be parsed to answer "which
tool saves the most" — a table can just be queried.

```js
// lib/savingsTracker.js
const Database = require('better-sqlite3');
const db = new Database(process.env.LOCALHELPER_CACHE_DB);

db.exec(`CREATE TABLE IF NOT EXISTS token_savings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool TEXT,              -- e.g. 'runTests', 'containerLogs', 'diffSummarize'
  role TEXT,              -- distill role used, e.g. 'test_failure', 'log_errors'
  terse INTEGER,          -- 0/1, was terse-mode active for this call
  raw_tokens INTEGER,
  distilled_tokens INTEGER,
  saved_tokens INTEGER,   -- raw_tokens - distilled_tokens, stored directly to avoid recomputing in every query
  duration_ms INTEGER,    -- Ollama call latency, for the qwen vs llama3.2 tradeoff question
  created_at TEXT
)`);
db.exec(`CREATE INDEX IF NOT EXISTS idx_savings_tool ON token_savings(tool)`);

const ENABLE_SAVINGS_TRACKING = process.env.LOCALHELPER_ENABLE_SAVINGS_TRACKING !== '0';

function recordSavings({ tool, role, terse, raw_tokens, distilled_tokens, duration_ms }) {
  // Gated: if tracking is off, this is a no-op — distill() still runs and
  // still compresses output, it just doesn't pay the DB-write cost per call.
  if (!ENABLE_SAVINGS_TRACKING) return;
  db.prepare(`INSERT INTO token_savings
    (tool, role, terse, raw_tokens, distilled_tokens, saved_tokens, duration_ms, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
    .run(tool, role, terse ? 1 : 0, raw_tokens, distilled_tokens,
         raw_tokens - distilled_tokens, duration_ms, new Date().toISOString());
}

module.exports = { recordSavings, db };
```

Note this makes the flag check live in `savingsTracker.js` rather than
`distill.js` — `distill()` always calls `recordSavings(...)` unconditionally;
the no-op decision is `savingsTracker`'s own responsibility. Keeps `distill()`
from needing to know about every downstream feature flag.

### Wiring: `distill()` records itself, callers just pass `tool`
Rather than every tool file calling `recordSavings` separately (easy to
forget), `distill()` takes one more param — `tool` — and does the recording
as part of its existing return path. This keeps the "every distilled tool
gets tracked" guarantee architectural instead of per-tool discipline.

```js
// lib/distill.js — extend the signature and the return path
const { recordSavings } = require('./savingsTracker');

async function distill({ role, raw, maxTokens = 300, model = 'qwen2.5-coder:7b', terse, tool = 'unknown' }) {
  if (!raw || raw.trim().length === 0) {
    return { summary: '(empty)', raw_tokens: 0, distilled_tokens: 0 };
  }
  const useTerse = typeof terse === 'boolean' ? terse : TERSE;
  const prompts = useTerse ? ROLE_PROMPTS_TERSE : ROLE_PROMPTS;
  const promptFn = prompts[role] || prompts.generic_condense;
  const effectiveMaxTokens = useTerse ? Math.round(maxTokens * TERSE_MAX_TOKENS_RATIO) : maxTokens;
  const prompt = promptFn(raw.slice(0, 16000));

  const start = Date.now();
  const summary = await callOllama({ model, prompt, max_tokens: effectiveMaxTokens });
  const duration_ms = Date.now() - start;

  const raw_tokens = estimateTokens(raw);
  const distilled_tokens = estimateTokens(summary);
  recordSavings({ tool, role, terse: useTerse, raw_tokens, distilled_tokens, duration_ms });

  return { summary, raw_tokens, distilled_tokens, terse: useTerse };
}
```

Every existing call site (`ContainerLogs`, `RunTests`, `LintFix`,
`DiffSummarize`, `BuildWatch`, `SessionSnapshot`) just needs a one-line
addition of `tool: 'runTests'` (etc.) to its existing `distill({...})` call —
no other code changes.

### New tool: `TokenSavingsReport`
Queryable rollup, grouped by tool, so this is an actual answer Claude (or you)
can pull instead of grepping a log file:

```js
// tools/tokenSavingsReport.js
const { db } = require('../lib/savingsTracker');

async function tokenSavingsReport({ since_days = 7, group_by = 'tool' } = {}) {
  const col = group_by === 'role' ? 'role' : 'tool';
  const rows = db.prepare(`
    SELECT ${col} AS name,
           COUNT(*) AS calls,
           SUM(raw_tokens) AS raw_tokens,
           SUM(distilled_tokens) AS distilled_tokens,
           SUM(saved_tokens) AS saved_tokens,
           ROUND(100.0 * SUM(saved_tokens) / NULLIF(SUM(raw_tokens), 0), 1) AS pct_saved,
           ROUND(AVG(duration_ms)) AS avg_duration_ms
    FROM token_savings
    WHERE created_at >= datetime('now', ?)
    GROUP BY ${col}
    ORDER BY saved_tokens DESC
  `).all(`-${since_days} days`);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({ since_days, ranked_by: 'saved_tokens', results: rows })
    }]
  };
}
module.exports = { tokenSavingsReport };
```

Sorted by `saved_tokens` descending, so the top row of the result *is* the
answer to "what's saving the most tokens" — no manual aggregation needed.
`avg_duration_ms` rides along in the same query since it's the other number
that matters for the qwen2.5-coder:7b-vs-llama3.2:3b tradeoff mentioned
below.

### "Is X worth keeping on?" — a verdict, not just raw numbers

`TokenSavingsReport` gives you the ranked numbers, but answering "is this
particular tool/role worth it" still means eyeballing pct_saved against
avg_duration_ms yourself. Add an explicit verdict computation so that's a
direct answer instead of a judgment call every time.

**Definition of "worth it":** net token savings clears a minimum threshold
*and* the latency cost per call doesn't exceed what you're willing to pay for
that savings. Both are configurable, since the right tradeoff differs by tool
(RunTests failing rarely can tolerate a slower call; SemanticGrep queried
constantly needs to stay snappy).

```
LOCALHELPER_WORTH_IT_MIN_PCT=30     # below this % saved, flag as "not worth it" regardless of latency
LOCALHELPER_WORTH_IT_MAX_MS=4000    # above this avg latency, flag as "not worth it" regardless of savings
```

```js
// lib/savingsTracker.js (addition)
const MIN_PCT = Number(process.env.LOCALHELPER_WORTH_IT_MIN_PCT || 30);
const MAX_MS = Number(process.env.LOCALHELPER_WORTH_IT_MAX_MS || 4000);

function verdict({ pct_saved, avg_duration_ms, calls }) {
  if (calls < 5) return { worth_it: null, reason: 'not enough calls yet (<5) to judge' };
  if (pct_saved < MIN_PCT) return { worth_it: false, reason: `only ${pct_saved}% saved, below ${MIN_PCT}% threshold` };
  if (avg_duration_ms > MAX_MS) return { worth_it: false, reason: `avg ${avg_duration_ms}ms per call exceeds ${MAX_MS}ms threshold` };
  return { worth_it: true, reason: `${pct_saved}% saved at ${avg_duration_ms}ms avg — clears both thresholds` };
}
module.exports = { recordSavings, db, verdict };
```

`TokenSavingsReport` attaches this verdict to every row so the ranked list
and the worth-it judgment come back together:

```js
// tools/tokenSavingsReport.js (updated return)
const { db, verdict } = require('../lib/savingsTracker');
// ...same query as above...
const results = rows.map(r => ({ ...r, ...verdict(r) }));
return { content: [{ type: "text", text: JSON.stringify({ since_days, ranked_by: 'saved_tokens', results }) }] };
```

**New tool: `WorthKeeping`** — a direct yes/no/unknown for one tool or role,
for when you just want the answer without reading a whole report:

```js
// tools/worthKeeping.js
const { db, verdict } = require('../lib/savingsTracker');

async function worthKeeping({ target, group_by = 'tool', since_days = 30 }) {
  const col = group_by === 'role' ? 'role' : 'tool';
  const row = db.prepare(`
    SELECT COUNT(*) AS calls,
           SUM(raw_tokens) AS raw_tokens,
           SUM(distilled_tokens) AS distilled_tokens,
           SUM(saved_tokens) AS saved_tokens,
           ROUND(100.0 * SUM(saved_tokens) / NULLIF(SUM(raw_tokens), 0), 1) AS pct_saved,
           ROUND(AVG(duration_ms)) AS avg_duration_ms
    FROM token_savings
    WHERE ${col} = ? AND created_at >= datetime('now', ?)
  `).get(target, `-${since_days} days`);

  if (!row || row.calls === 0) {
    return { content: [{ type: "text", text: JSON.stringify({ target, worth_it: null, reason: 'no data for this target' }) }] };
  }

  const result = { target, ...row, ...verdict(row) };
  return { content: [{ type: "text", text: JSON.stringify(result) }] };
}
module.exports = { worthKeeping };
```

Example call: `worthKeeping({ target: 'containerLogs' })` →
`{"target":"containerLogs","calls":42,"pct_saved":78.3,"avg_duration_ms":1120,"worth_it":true,"reason":"78.3% saved at 1120ms avg — clears both thresholds"}`.

If the answer comes back `worth_it: false`, the natural next actions are:
switch that role to a faster model in `ModelRoute` (llama3.2:3b instead of
qwen2.5-coder:7b), raise its `maxTokens` if it's over-compressing content that
still needs re-reading raw, or just turn off distillation for that one
tool/role and let it return raw text directly.

### Build-order note
Add `lib/savingsTracker.js` (including `verdict()`) alongside the
`lib/distill.js` pass (step 1) — same reasoning as terse-mode: it's a change
to the shared building block, so every tool built afterward is tracked
automatically with zero extra work. `TokenSavingsReport` and `WorthKeeping`
can be added any time after that (cheap, no dependencies beyond the table
existing) — reasonable to slot both right after TokenBudget in the build
order since all three are "pure/no new architecture" tools.