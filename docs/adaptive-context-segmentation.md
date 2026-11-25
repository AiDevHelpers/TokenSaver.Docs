# Adaptive Context Segmentation

## Overview

The adaptive context segmentation system intelligently partitions the codebase into logical segments and learns which segments are used together. This reduces context window consumption by **30-50%** while preserving task-critical content.

Instead of loading the entire codebase context at once, the system:

1. **Detects task type** from the user's prompt (Code, Debug, Planning, etc.)
2. **Segments the codebase** by subsystem and responsibility (indexing, config, pipeline, etc.)
3. **Learns access patterns** from past sessions to predict which segments go together
4. **Selects segments** based on task type affinity and learned co-occurrence patterns
5. **Records outcomes** to continuously improve recommendations

## Architecture

### Core Components

**`ContextSegment`** — A logical partition of codebase content:
- ID and label ("core_architecture", "context_pipeline", etc.)
- Path patterns (glob patterns like "src/Core/TokenSaver.CodeHelper/Indexing/**")
- Priority: Critical > Important > Optional
- Estimated token size (~3k-6k tokens each)
- Primary task types (which tasks benefit most from this segment)

**`ContextSegmentationService`** — Manages segment definitions:
- Loads/persists segments in `.tokensaver/context/segments.json`
- Generates default segments based on codebase structure
- Selects segments by task type and token budget
- Updates LastAccessed timestamps

**`AccessPatternTracker`** — Records usage history:
- Appends to `.tokensaver/context/access-patterns.jsonl` (one JSON object per line)
- Analyzes co-occurrence: segments used together in past sessions
- Computes affinity scores between segment pairs (0.0-1.0)
- Recent sessions (last 100) are weighted more heavily

**`AdaptiveContextLoader`** — Orchestrates the full flow:
- Classifies task type using two-tier `TaskClassifier` (keywords → model call)
- Selects segments for the detected task type
- Recommends related segments based on access patterns
- Records session outcome for training

### Segment Defaults

The system comes with 10 pre-defined segments:

| Segment ID | Label | Priority | Task Types | Est. Tokens |
|---|---|---|---|---|
| `core_architecture` | Core Architecture | Critical | Planning, Review, Explain | 3000 |
| `codex` | Indexing & Search | Important | Code, Debug, Test | 5000 |
| `context_pipeline` | Context Pipeline | Important | Code, Debug | 4000 |
| `configuration` | Config & Ignore | Important | Code, Planning | 2000 |
| `mcp_server` | MCP Server | Important | Code, Debug, Test | 6000 |
| `auto_workflow` | Auto Workflow | Optional | Planning, Code | 3000 |
| `testing_harness` | Testing & Calibration | Optional | Test, Debug | 4000 |
| `agent_helpers` | Agent Adapters | Optional | Code, Review | 3000 |
| `docs` | Documentation | Optional | Explain, Planning | 2000 |

**Customization:** Edit segments in `.tokensaver/context/segments.json` to match your codebase structure.

## Usage

### MCP Tools

#### 1. `AnalyzeContextSegmentation`

Inspect segments and learned patterns:

```
AnalyzeContextSegmentation(
  action: "segments",           // "segments", "patterns", or "recommend"
  prompt: null,                 // prompt required for "recommend"
  tokenBudget: 50000
)
```

**Actions:**

- **`segments`** — List all defined segments, their priorities, task type affinity, and token estimates.
- **`patterns`** — Show co-occurrence statistics: which segments are used together, and how often.
- **`recommend`** — Given a prompt, show which segments would be loaded and why.

**Example output:**
```
Defined Segments (10 total):

[Critical]
  Core Architecture       (core_architecture        ) ~3,000 tokens
    Primary tasks: Planning, Review, Explain
    Patterns: *.csproj, **/CLAUDE.md, docs/, .tokensaver/

[Important]
  Indexing & Search       (codex                    ) ~5,000 tokens
    Primary tasks: Code, Debug, Test
    Patterns: src/Core/TokenSaver.CodeHelper/Indexing/**

...

Segment Co-occurrence Affinities (recently learned):

  codex                    ↔ context_pipeline        (affinity: 0.89, co-occurrences: 5)
  mcp_server               ↔ codex                   (affinity: 0.76, co-occurrences: 4)
  context_pipeline         ↔ configuration           (affinity: 0.62, co-occurrences: 3)
```

#### 2. `BuildAdaptiveContext`

Load segments for a specific task:

```
BuildAdaptiveContext(
  prompt: "Fix the indexing pipeline to handle TypeScript symbols",
  sessionId: "abc123",           // optional; enables pattern tracking
  tokenBudget: 50000,
  forceIncludeSegments: ["docs"]  // override filtering
)
```

**Returns:**
- Detected task type and confidence
- Selected segments in priority order
- Glob patterns for each segment (use with file retrieval)
- Session ID for tracking

**Example output:**
```
Adaptive Context Load Plan
Task Type: Code | Segments: 5 | Tokens: 18,000/50,000

[Critical] Core Architecture
  *.csproj
  **/CLAUDE.md

[Important] Indexing & Search
  src/Core/TokenSaver.CodeHelper/Indexing/**
  src/Core/TokenSaver.CodeHelper/Models/Index/**

[Important] Context Pipeline
  src/Core/TokenSaver.ContextHelper/Pipeline/**

...

Session ID for tracking: 550e8400-e29b-41d4-a716-446655440000
```

#### 3. `RecordContextSession`

Record how segments were actually used:

```
RecordContextSession(
  sessionId: "550e8400-e29b-41d4-a716-446655440000",
  segmentsUsed: ["codex", "context_pipeline", "configuration"],
  segmentsModified: ["codex"],
  outcome: "Succeeded"  // "Succeeded", "Failed", or "Abandoned"
)
```

This data trains the access pattern analysis for future recommendations.

## Workflow

Typical workflow for token-efficient context:

```
1. User: "Fix the indexing pipeline"

2. Claude Code:
   → Calls BuildAdaptiveContext(prompt)
   → Gets: Task Type: Code, Segments: [codex, context_pipeline, configuration]
   
3. Claude Code:
   → Loads files matching segment patterns
   → Reads code from selected segments
   → Works on the task
   
4. Claude Code (at session end):
   → Calls RecordContextSession(
       sessionId,
       segmentsUsed: ["codex", "context_pipeline"],
       segmentsModified: ["codex"],
       outcome: "Succeeded"
     )

5. System:
   → Appends access pattern to .tokensaver/context/access-patterns.jsonl
   → Updates co-occurrence affinities
   → Next time someone does similar work, it loads [codex, context_pipeline] 
      even if they also mentioned "configuration"
```

## Files

### `.tokensaver/context/segments.json`

Segment definitions (load-time read-only; edit manually to customize):

```json
[
  {
    "id": "codex",
    "label": "Indexing & Search",
    "pathPatterns": [
      "src/Core/TokenSaver.CodeHelper/Indexing/**",
      "src/Core/TokenSaver.CodeHelper/Models/Index/**"
    ],
    "priority": "Important",
    "primaryTaskTypes": ["Code", "Debug", "Test"],
    "estimatedTokens": 5000,
    "lastAccessed": "2026-07-10T14:32:15Z",
    "cachedSummary": null
  },
  ...
]
```

### `.tokensaver/context/access-patterns.jsonl`

Session history (append-only; one JSON object per line):

```jsonl
{"sessionId":"abc123","timestamp":"2026-07-10T14:30:00Z","taskType":"Code","segmentsLoaded":["codex","context_pipeline"],"segmentsUsed":["codex","context_pipeline"],"segmentsModified":["codex"],"outcome":"Succeeded"}
{"sessionId":"def456","timestamp":"2026-07-10T15:00:00Z","taskType":"Debug","segmentsLoaded":["codex","mcp_server"],"segmentsUsed":["codex","mcp_server"],"segmentsModified":[],"outcome":"Succeeded"}
```

## Tuning

### Adjust segment definitions

Edit `.tokensaver/context/segments.json`:

```json
{
  "id": "codex",
  "label": "Indexing & Search",
  "estimatedTokens": 5000,     // ← estimate size by measuring actual files
  "priority": "Important",      // ← change to Critical/Optional as needed
  "primaryTaskTypes": ["Code", "Debug", "Test"],  // ← which tasks need this
  "pathPatterns": [             // ← update patterns for your structure
    "src/Core/TokenSaver.CodeHelper/Indexing/**"
  ]
}
```

### Add custom segments

Copy a segment definition, change the ID/label/paths:

```json
{
  "id": "my_custom_system",
  "label": "My Custom Subsystem",
  "pathPatterns": ["src/MySystem/**"],
  "priority": "Important",
  "primaryTaskTypes": ["Code"],
  "estimatedTokens": 2000
}
```

### Monitor learning

Run `AnalyzeContextSegmentation(action: "patterns")` periodically to see what the system is learning:

- High-affinity segment pairs → candidates for bundling or splitting
- Low-affinity pairs → candidates for making optional
- Rarely-used segments → may be safely moved to Optional priority

## Tuning Strategy

Start with default segments. After 10-20 sessions, check affinities:

1. If two segments always appear together (affinity > 0.8), they might be conceptually the same—merge them.
2. If a segment is rarely used, move it to Optional priority.
3. If a segment's token estimate is wrong, update it based on actual file sizes.
4. If certain task types consistently miss key segments, update `primaryTaskTypes`.

## Implementation Notes

- **Task type detection**: Two-tier classifier (fast keywords → slow model call) with configurable confidence threshold.
- **Affinity calculation**: Co-occurrence / min(count[A], count[B]), capped at 1.0.
- **Recent-session bias**: Only the last 100 sessions are used for affinity analysis (stale patterns fade naturally).
- **Thread-safe**: Services are singletons; concurrent reads are safe; access pattern appends are serialized.
- **Lazy loading**: Segments are only computed when requested; the 30-minute cache prevents re-analysis on every call.

## Future Enhancements

Potential improvements (not implemented yet):

1. **Semantic affinity**: Use embedding distance between segment descriptions to suggest related segments.
2. **Task type learning**: Train a model on local session data to classify tasks more accurately than keywords.
3. **Predictive preloading**: Warm up the model for likely-next-segments while the user is reading current ones.
4. **Segment fusion**: Automatically merge segments with high affinity and low size.
5. **Per-user patterns**: Track patterns per user/role (e.g. "debugger prefers logs", "planner prefers docs").
