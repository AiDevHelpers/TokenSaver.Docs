# Context Builder Evaluation & Self-Tuning

Two complementary mechanisms for answering "is the context builder too narrow or too wide":
an offline/live golden-set eval you run by hand, and a runtime self-tuning service that adjusts
itself from real usage. Neither depends on the other.

## 1. Golden-set evaluation (`docs/retrieval-benchmark/run_eval.py`)

The 332-query labeled set in `docs/retrieval-benchmark/` (`queries.jsonl` + `corpus.jsonl`,
categorized `doc_derived`/`symbol_lookup`/`conceptual`/`adversarial`/`negative` — see that
folder's `README.md` for how it was built) already existed as a benchmark for a *candidate*
embed+rerank pair (`run_benchmark.py`, Qwen3-Embedding/Reranker via llama-cpp-python — see
`RESULTS.md`). `run_eval.py` is a second, separate script that evaluates what's actually
deployed: Ollama's `/api/embed` with the configured `EmbeddingModel` (`nomic-embed-text` by
default), the exact call `SemanticRelevanceFilterStage`/`SemanticSearchService` make in
production. No reranker step — the context builder doesn't have one today.

```powershell
python docs/retrieval-benchmark/run_eval.py                    # full 332-query run
python docs/retrieval-benchmark/run_eval.py --limit 20          # fast smoke test
```

Requires a live embedding endpoint (dev server + Ollama, or the SimpleModelServer router). Embeddings
are cached to `.embed-cache.json` (gitignored) so repeat runs only pay for new queries. Writes
`production-eval-results.json` (raw per-query data) and `PRODUCTION-EVAL.md` (the report) —
**do not confuse these with `RESULTS.md`/`results_*.json`**, which belong to `run_benchmark.py`'s
separate candidate-model evaluation.

### How to read it for "narrow vs. wide"

- **Too narrow** = low `doc_derived`/`symbol_lookup` recall@5 — the filter is dropping or never
  surfacing a file a query should have found. These two categories are the easy case (exact
  name/summary matches); if recall is bad here, real usage will be worse.
- **Too wide** = high negative-query false-positive rate — a query about functionality that
  doesn't exist in the codebase still gets a confident top-1 hit, meaning the context builder
  will happily pull in an irrelevant file rather than say "nothing here."
- **Adversarial discrimination rate** — can embed-only similarity tell two same-named-but-
  different symbols apart (two `Resolve` methods, `CodeChunk` vs `ChunkEntity`, etc.)? Low
  numbers here aren't fixable by threshold tuning — that needs the reranker design in
  `docs/retrieval-design.md`.

### Baseline (2026-07-10, nomic-embed-text, no rerank, full 332 queries)

| Metric | Result | Read |
|---|---|---|
| doc_derived+symbol_lookup recall@5 | 91.1% | decent overall, but symbol_lookup alone is only 46.7% |
| negative-query false-positive rate | **100%** | every "this doesn't exist" query returned a confident top-1 — the context builder cannot currently say "no match" |
| adversarial discrimination rate | 54.5% | worse than the 100% the candidate Qwen3+reranker pair achieved (see `RESULTS.md`) |

**Current verdict: too wide, not too narrow.** Recall is acceptable; the actionable problem is
that nothing here ever abstains. This tracks with `retrieval-design.md`'s "Abstain path (the 20%
problem)" section — that design was scoped against the candidate pair's 20% negative-FP rate;
production's actual rate (no rerank, no abstain threshold) is worse. The abstain-threshold and
conditional-rerank items in that doc's follow-up list are the fix for this, not the runtime
calibration mechanism below (which only ever loosens the threshold from live signal — it has no
lever to reduce false positives).

Re-run after any embedding-model change, `SemanticThreshold` change, or corpus-affecting
refactor, and compare against this baseline rather than eyeballing a single run.

## 2. Runtime self-tuning (`RetrievalCalibrationService`)

`docs/retrieval-benchmark/` measures narrow/wide offline against a fixed label set. This service
measures it online, from what real sessions actually do — no labels needed, but it can only ever
detect and correct *narrowness* (see "why not wide" below).

### The signal

`SemanticRelevanceFilterStage` (`TokenSaver.ContextHelper/Pipeline/Stages/06_...cs`) drops chunks
below a relevance threshold on every `BuildConciseContext` call. If a session's *next* turn
explicitly requests a file (via `requestedFiles`) that wasn't part of what the previous turn
kept, that's direct evidence: the caller needed a file the filter either dropped or never
surfaced. `RetrievalCalibrationService` scores that late file against the current prompt the same
way the filter stage would, and compares it to the previous turn's minimum-kept relevance
(`PreviousMinKeptRelevance`). A gap bigger than `ContextHelperConfig.NarrowFailureMargin` (default
`0.15`) counts as a failure.

### The adjustment

Enough consecutive failures (`CalibrationMinSamplesBeforeAdjust`, default 3) nudge
`RetrievalCalibrationState.ThresholdAdjustment` down by `CalibrationLearningRate` (default 0.02),
bounded by `CalibrationMaxAdjustment` (default 0.15) — this widens the effective threshold
(`SemanticThreshold + ThresholdAdjustment`) so future turns keep more. Enough consecutive clean
turns nudge it back toward 0 (never past the configured baseline). Persisted per workspace at
`.tokensaver/retrieval-calibration.json`; every check appends to
`.tokensaver/retrieval-calibration-outcomes.jsonl` for audit.

### Why this can't detect "too wide"

There's no online signal for "we kept an irrelevant chunk" — a chunk that shouldn't have been
kept doesn't announce itself the way a missing one does via a re-request. Detecting that is what
the golden-set eval above is for. `ThresholdAdjustment` is therefore clamped to `<= 0`: this
mechanism only ever widens from live usage, it never tightens past the configured baseline on its
own.

### Observing it

- `BuildConciseContext`'s response gets an inline `<!-- ⚠ retrieval-calibration: ... -->` comment
  whenever a late request triggers a failure, naming the file, its score, and the bar it missed.
- `ContextDiag(action='calibration')` shows the current adjustment, sample/failure counts, and
  last-updated timestamp for the active workspace.

### Testing

`RetrievalCalibrationServiceTests` (`TokenSaver.Library.Tests`) covers the gap-detection/
adjustment/recovery/persistence logic offline via `FakeOllamaHandler` — deterministic synthetic
embeddings, no live Ollama, same split as the rest of this codebase's test suite (see
`OllamaEndpointRegistryTests`' doc comment for the same offline/live-verification split). It does
not — and can't, offline — verify that real embeddings actually discriminate relevant from
irrelevant text; that's `run_eval.py`'s job.
