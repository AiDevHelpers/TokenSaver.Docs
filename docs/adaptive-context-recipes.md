# Adaptive Context Segmentation — Usage Recipes

Quick start guides for common scenarios.

## Recipe 1: Fix a Bug in the Indexing Pipeline

**Your task:** "The symbol indexer is crashing on TypeScript files, fix it."

### Step 1: Plan which segments you need

```
AnalyzeContextSegmentation(
  action: "recommend",
  prompt: "The symbol indexer is crashing on TypeScript files"
)
```

**Output:**
```
Context Load Plan (Session: abc-123-def)

Detected Task Type: Debug (confidence: 0.95)
Total Token Budget: 50000 tokens
Segments to Load: 4 (16,000 tokens)

[Critical]
  Core Architecture (~3,000 tokens)

[Important]
  Indexing & Search (~5,000 tokens)
  Testing & Calibration (~4,000 tokens) ✓ (recommended)

[Optional]
  Documentation (~2,000 tokens) ✓ (recommended based on past patterns)
```

### Step 2: Load segments for your specific task

```
BuildAdaptiveContext(
  prompt: "The symbol indexer is crashing on TypeScript files",
  sessionId: "abc-123-def",
  tokenBudget: 50000
)
```

**Output shows path patterns for each segment:**
```
[Critical] Core Architecture
  *.csproj, **/CLAUDE.md, docs/, .tokensaver/

[Important] Indexing & Search
  src/Core/TokenSaver.CodeHelper/Indexing/**
  src/Core/TokenSaver.CodeHelper/Models/Index/**
  src/Core/TokenSaver.Library/Services/ChunkExtractor.cs
  
[Important] Testing & Calibration
  **/**.Tests/**
  src/Core/TokenSaver.CodeHelper/Calibration/**

...
```

### Step 3: Load the files

Use these patterns to load files from your context system (BuildConciseContext with `requestedFiles`).

### Step 4: Work on the bug

1. Read the TypeScript symbol parser: `src/Core/TokenSaver.CodeHelper/Indexing/TypeScriptSymbolParser.cs`
2. Check tests: `src/Core/TokenSaver.CodeHelper.Tests/TypeScriptSymbolParserTests.cs`
3. Fix and test

### Step 5: Record the session (train the system)

```
RecordContextSession(
  sessionId: "abc-123-def",
  segmentsUsed: ["codex", "testing_harness"],
  segmentsModified: ["codex"],
  outcome: "Succeeded"
)
```

**Result:** Next time someone debugs indexing, the system learns to load these segments immediately.

---

## Recipe 2: Add a New Feature to the Context Pipeline

**Your task:** "Add a new context stripping stage for sensitive data."

### Step 1: Get recommendations

```
AnalyzeContextSegmentation(
  action: "recommend",
  prompt: "Add a new context stripping stage for sensitive data removal"
)
```

**Output:**
```
Context Load Plan (Session: xyz-789-uip)

Detected Task Type: Code (confidence: 0.87)
Segments to Load: 4 (15,000 tokens)

[Critical]
  Core Architecture (~3,000 tokens)

[Important]
  Context Pipeline (~4,000 tokens)
  Configuration (~2,000 tokens)
  
[Optional]
  Testing & Calibration (~4,000 tokens) ✓ (recommended)
  Agent Adapters (~3,000 tokens)
```

### Step 2: Load context

```
BuildAdaptiveContext(
  prompt: "Add a new context stripping stage for sensitive data removal",
  sessionId: "xyz-789-uip"
)
```

### Step 3: Implement

- Read existing stages: `src/Core/TokenSaver.ContextHelper/Pipeline/Stages/`
- Implement `ISensitiveDataStrippingStage`
- Add to pipeline in `ContextPipelineService`
- Write tests in `TokenSaver.ContextHelper.Tests/`

### Step 4: Record

```
RecordContextSession(
  sessionId: "xyz-789-uip",
  segmentsUsed: ["context_pipeline", "configuration", "testing_harness"],
  segmentsModified: ["context_pipeline", "testing_harness"],
  outcome: "Succeeded"
)
```

---

## Recipe 3: Understand the MCP Server Architecture

**Your task:** "How does the MCP server route requests?"

### Step 1: Get planning context

```
AnalyzeContextSegmentation(
  action: "recommend",
  prompt: "How does the MCP server route requests between tools?"
)
```

**Output:**
```
Detected Task Type: Explain (confidence: 0.91)
Segments to Load: 3 (9,000 tokens)

[Critical]
  Core Architecture (~3,000 tokens)

[Important]
  MCP Server (~6,000 tokens)
  
[Optional]
  Documentation (~2,000 tokens)
```

### Step 2: Load context

```
BuildAdaptiveContext(
  prompt: "How does the MCP server route requests between tools?"
)
```

### Step 3: Read architecture

- `src/Host/TokenSaver.MCP/Program.cs` — tool registration
- `src/Host/TokenSaver.MCP/Middleware/` — request handling
- `CLAUDE.md` — architecture overview

### Step 4: Don't record (this was research, no changes)

No need to call `RecordContextSession` since you didn't modify code. The system learns mainly from task-driven sessions.

---

## Recipe 4: Check Learned Patterns

**Your task:** "I want to see what the system has learned about which segments go together."

### Run the pattern analysis

```
AnalyzeContextSegmentation(action: "patterns")
```

**Output:**
```
Segment Co-occurrence Affinities (recently learned):

  codex                    ↔ context_pipeline        (affinity: 0.89, co-occurrences: 9)
  mcp_server               ↔ codex                   (affinity: 0.76, co-occurrences: 6)
  context_pipeline         ↔ configuration           (affinity: 0.62, co-occurrences: 4)
  testing_harness          ↔ codex                   (affinity: 0.58, co-occurrences: 3)
  mcp_server               ↔ testing_harness         (affinity: 0.51, co-occurrences: 2)
```

**Interpret:**
- **0.89 (codex ↔ context_pipeline):** These almost always appear together — if you work on indexing, you also need the pipeline.
- **0.76 (mcp_server ↔ codex):** Frequently together — MCP server work often touches indexing.
- **0.51 (mcp_server ↔ testing_harness):** Occasionally together — less consistent pairing.

**Use this to:**
- Spot merge opportunities (if affinity > 0.85, consider merging segments)
- Improve `primaryTaskTypes` (if two segments are always loaded together, they should have overlapping task types)
- Spot stale segments (if a segment has no outgoing affinities, it's rarely used)

---

## Recipe 5: Customize Segments for Your Codebase

**Your task:** "The default segments don't match my codebase structure."

### Step 1: Review current segments

```
AnalyzeContextSegmentation(action: "segments")
```

### Step 2: Edit `.tokensaver/context/segments.json`

Example: if you have a "WebUI" subsystem not in defaults:

```json
{
  "id": "webui",
  "label": "Web UI",
  "pathPatterns": [
    "src/Host/TokenSaver.WebUI/**",
    "src/Host/TokenSaver.WebUI.Tests/**"
  ],
  "priority": "Important",
  "primaryTaskTypes": ["Code", "Test"],
  "estimatedTokens": 4000,
  "lastAccessed": null
}
```

### Step 3: Re-run analysis

```
AnalyzeContextSegmentation(action: "recommend", prompt: "Fix the web UI dashboard")
```

Now "webui" should appear in the recommendations.

### Step 4: Refine based on patterns

After 5-10 uses, check patterns:

```
AnalyzeContextSegmentation(action: "patterns")
```

If "webui" mostly pairs with "mcp_server", update the JSON:

```json
{
  "primaryTaskTypes": ["Code", "Test", "Debug"]  // add Debug
}
```

---

## Recipe 6: Force-Include Segments

**Your task:** "I usually work on just the pipeline, but this time I also need the documentation."

### Use forceIncludeSegments

```
BuildAdaptiveContext(
  prompt: "Refactor the context pipeline and document the stages",
  forceIncludeSegments: ["context_pipeline", "docs"]
)
```

**Result:**
- Normally this task would load [codex, context_pipeline, testing_harness]
- With forceIncludeSegments, it loads [codex, context_pipeline, testing_harness, docs]
- Total tokens used: within budget

---

## Recipe 7: Debug Poor Recommendations

**Your task:** "The system loaded segments I didn't need; how do I fix it?"

### Check what was recommended

```
AnalyzeContextSegmentation(
  action: "recommend",
  prompt: "your task description"
)
```

### Record accurately

Make sure when you end the session, you call `RecordContextSession` with the *actual* segments you used, not what was recommended:

```
RecordContextSession(
  sessionId: "...",
  segmentsUsed: ["codex", "context_pipeline"],  // ← what you *actually* used
  segmentsModified: ["codex"],
  outcome: "Succeeded"
)
```

### System learns over time

After 10 similar sessions with accurate feedback, the system will predict better.

If a segment is *consistently* loaded but never used:
1. Check if it should be Optional instead of Important
2. Check if it should be removed from that task type's `primaryTaskTypes`
3. File an issue if a segment is fundamentally wrong

---

## Best Practices

1. **Always call `RecordContextSession` at the end** — this is how the system learns.
2. **Be honest in `segmentsUsed`** — the system only learns from accurate feedback.
3. **Check patterns monthly** — see what the system has learned; adjust if it drifts.
4. **Customize segments early** — default segments are generic; adapt them to your codebase structure.
5. **Monitor token consumption** — the goal is to use less context; if you're hitting budget limits, add more segments to Optional priority.
