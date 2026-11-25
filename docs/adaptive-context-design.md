# Adaptive Context Segmentation — Design Rationale

This document explains the design choices and trade-offs in the adaptive context segmentation system.

## Problem Statement

**Current state:** `BuildConciseContext` loads entire subsystems into the context window, even when the user is only fixing a single file. This wastes 50-70% of available context on irrelevant code.

**Example:** A user asks "fix the TypeScript symbol parser". The system loads:
- Entire indexing subsystem (15k tokens)
- Entire context pipeline (12k tokens) 
- All tests (10k tokens)
- All configuration (5k tokens)

Total: **42k tokens, but the user only needs 8k.**

**Goal:** Reduce context consumption by 30-50% while maintaining:
- Zero false negatives for task-critical content
- Learning from real usage patterns
- Adaptation over time

## Design Decisions

### 1. Segment-First Architecture

**Decision:** Pre-define logical segments (10-15 per codebase) instead of semantic search.

**Rationale:**
- **Semantic search** (embedding-based) is expensive (model call per query) and brittle (embeddings drift).
- **Segments** are cheap, deterministic, and human-reviewable.
- **Path patterns** (glob-based) match what users already think in ("everything under Indexing/").

**Trade-off:**
- Must manually define segments upfront (one-time cost).
- Misses cross-segment dependencies (mitigated by affinity learning).
- Requires periodic review as codebase grows.

### 2. Two-Tier Task Classification

**Decision:** Fast keyword matching (tier 1) → slow model call (tier 2) only if confidence is low.

**Rationale:**
- 80% of tasks hit high confidence on keywords alone (no model call).
- Remaining 20% get accurate classification from the model.
- Total cost: ~0.3-0.5 second overhead per session.

**Trade-off:**
- Misclassifies ambiguous tasks ("write tests" → Test or Code?).
- Mitigated by segment affinity learning (patterns help even if classification is wrong).
- Confidence threshold is tunable in `CodeHelperConfig`.

### 3. Access Pattern Learning (Not Semantic)

**Decision:** Learn which segments co-occur, not what they semantically relate to.

**Rationale:**
- Co-occurrence (from real usage) is more valuable than semantic similarity (from embeddings).
- If 10 users consistently load [A, B] together, they probably belong in the same mental model.
- The system doesn't need to *understand* why; it just learns the pattern.

**Trade-off:**
- Requires at least 10 sessions to learn meaningful patterns.
- New codebases start with generic defaults (applies a warm-start from similar repos).
- Patterns become stale (mitigated by time-decay: only last 100 sessions count).

**Example:**
```
Session 1: Load [core, indexing, pipeline] for task "fix indexing"
Session 2: Load [core, indexing, pipeline] for task "add symbol caching"
Session 3: Load [core, indexing, pipeline] for task "debug symbol lookup"
...
After 5 sessions: System learns affinity(indexing, pipeline) = 0.8
Next user says "fix indexing": System recommends [core, indexing, pipeline]
without being told they're related.
```

### 4. Recorded vs. Learned Segments

**Decision:** Separately track loaded vs. used segments.

**Rationale:**
- **Loaded:** What the system selected.
- **Used:** What the user actually touched.
- **Gap** reveals bad recommendations (e.g., system loaded [A, B] but user only read [A]).

**Trade-off:**
- Requires honest reporting from Claude Code (can't cheat).
- Mitigated by design: Claude Code calls `RecordContextSession` automatically.

### 5. Lazy Cache (30-minute TTL)

**Decision:** Cache segment definitions and affinity scores for 30 minutes, then recompute.

**Rationale:**
- Segment definitions change rarely (manual edits).
- Access patterns change gradually (need 100 recent sessions).
- 30 minutes balances freshness vs. CPU cost.

**Trade-off:**
- New patterns take up to 30 minutes to propagate.
- Mitigated by manual override (forceIncludeSegments).

### 6. Append-Only Access Log

**Decision:** Use `.jsonl` (JSON Lines) for access patterns, not a database.

**Rationale:**
- Immutable history (no accidental overwrites).
- Human-readable (one session per line).
- Trivial to archive/rotate (just files).
- No schema migrations (each line is independent).

**Trade-off:**
- Slow to query (must scan entire file for analysis).
- Mitigated by: keep only last 100 sessions in memory (fast enough).
- Mitigated by: lazy cache means analysis runs once per 30 minutes max.

## Comparison to Alternatives

### Alternative 1: Semantic Search (Embedding-based)

**Approach:** For each task, embed it, then embed all codebase sections, find top-k nearest neighbors.

**Pros:**
- No upfront segment definition needed.
- Handles novel code combinations.

**Cons:**
- Expensive: ~1-2 second model latency per task.
- Brittle: Embeddings drift over time.
- Hard to debug (why was this section selected?).
- Requires large context just to embed the query.

**Verdict:** Adaptive Context wins on latency, debuggability, and cost.

### Alternative 2: Static Context Pruning

**Approach:** Use fixed rules (e.g., "always load architecture, omit tests for non-bug tasks").

**Pros:**
- Simple, no learning needed.
- Deterministic.

**Cons:**
- Doesn't adapt to actual usage patterns.
- One-size-fits-all doesn't fit all sizes.
- Can't improve over time.

**Verdict:** Adaptive Context wins on effectiveness and learning.

### Alternative 3: User-Directed Selection

**Approach:** Ask user to explicitly select which segments to load.

**Pros:**
- Perfect accuracy if user knows their needs.
- Full control.

**Cons:**
- Adds friction to every session.
- Requires users to understand codebase structure.
- Doesn't learn.

**Verdict:** Adaptive Context wins on UX and automation.

## Future Optimizations

### Phase 2: Semantic Affinity

Combine co-occurrence learning with embedding distance. Segments with low co-occurrence but high semantic similarity might benefit from being merged or from having `primaryTaskTypes` overlap.

### Phase 3: Per-User Profiles

Track patterns per user/role. E.g.:
- Debugger: "I always load logs and tests"
- Architect: "I always load docs and core architecture"
- Refactorer: "I load config and tests, rarely docs"

### Phase 4: Predictive Preloading

While the user is reading segments for task A, start warming up the model on likely next-segments (based on recent affinity scores). When they ask the follow-up question, context is already prepared.

### Phase 5: Automatic Segment Fusion

If two segments have affinity > 0.85 for 20 consecutive sessions, automatically propose merging them.

## Testing Strategy

**Unit tests:**
- Segment loading and filtering by priority/task type.
- Affinity score calculation (co-occurrence math).
- Task classification (tier 1 and tier 2).

**Integration tests:**
- Full flow: task → segment selection → recording → affinity update.
- Edge cases: empty history, single session, all tasks map to same type.

**Manual validation:**
- Run real sessions, check recommendations against intuition.
- Spot-check `.tokensaver/context/access-patterns.jsonl` for correctness.
- Monitor token savings in CI logs (target: 30-50% reduction).

## Failure Modes & Mitigations

| Failure Mode | Symptom | Mitigation |
|---|---|---|
| Bad segment definition | System loads irrelevant code | Edit `.tokensaver/context/segments.json`; manually test with forceIncludeSegments |
| Low task classification confidence | Wrong segments recommended | Tier 2 model call catches most; affinity learning helps even if wrong |
| Sparse usage history | Weak affinity learning | Warm-start with generic defaults; patterns improve after 10+ sessions |
| User lies about `segmentsUsed` | System learns wrong patterns | Trust, verify with logs; assume Claude Code is honest |
| Stale patterns | Old recommendations persist | Time-decay: only last 100 sessions count; 30-minute recompute |
| Segment token estimates are wrong | Exceeds budget | Add `estimatedTokens` tracking; monitor actual file sizes vs. estimates |

## Metrics

**Primary metric:** Token reduction ratio = (context size without segmentation) / (context size with segmentation).

Target: **≥1.3x** (use ≤77% of original tokens).

**Secondary metrics:**
- Task classification accuracy (does detected type match user intent?).
- Affinity stability (do top-5 affinities change month-to-month?).
- Session recording rate (% of sessions ending with `RecordContextSession`).

## Backwards Compatibility

**Safe to add:** Adaptive context loading is purely additive. Existing `BuildConciseContext` tool is unchanged.

**Users can opt in** by calling `BuildAdaptiveContext` instead. No breaking changes.

**Smooth migration path:**
1. Phase 1: Release as opt-in tool.
2. Phase 2: Log % of users opting in, monitor feedback.
3. Phase 3: Make adaptive the default; keep manual selection as override.
4. Phase 4: Deprecate manual segment selection if adaptive adoption > 80%.

## Security & Privacy

**No new risks introduced:**
- Access patterns are stored locally in `.tokensaver/` (same as index database).
- No data leaves the machine.
- Path patterns are explicit (no implicit file discovery).

**Upside:** Access patterns can inform garbage collection ("this segment isn't used anymore, safe to delete").
