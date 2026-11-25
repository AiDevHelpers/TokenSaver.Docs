# Plan: pick the summary and embedding models for semantic search

Status: research done, index rebuild not started.

## Goal

Semantic search should return good code matches for queries like "select code related to X". Two models decide that:

- **Embedding model** (router `embed`): turns queries and chunks into vectors. It decides which chunks are close to a query. Current: `qwen3-embedding:0.6b` (1024 dims, answers in about 2 s). Previous: `nomic-embed-text` (768 dims). Changing it requires a full index rebuild.
- **Chat / summary model** (router `main`): writes a one-sentence summary per chunk. Summaries are embedded instead of raw code when `tokenEconomy.enableSummaryEmbedding` is on. Current: `gemma3:1b`.

## Findings

### Summary model (sub-2B, same three snippets, one-sentence prompt)

| Model | Replies | Speed | Quality |
|---|---|---|---|
| `gemma3:1b` | one sentence each | 5–6 s | Mostly accurate; one wrong claim about `sealed` |
| `qwen2.5-coder:0.5b` | multi-sentence | 5–6 s after load | Most accurate; verbose |
| `smollm2:1.7b` | one sentence each | 4–8 s | Accurate on two; vague on lockout |
| `deepseek-coder:1.3b` | multi-sentence | 5–9 s | Partly wrong (called C# code Python) |
| `llama3.2:1b` | one sentence each | 5–7 s | Wrong on `Widget` |
| `qwen3:0.6b`, `qwen3:1.7b` | empty | — | Reasoning output used the token budget |
| `codegemma:2b` | `.js` | — | Completion model, not a summarizer |

Chosen for now: `gemma3:1b`. The sample is three snippets, so this is a first pass.

### Earlier results from the repo's own models

- `qwen2.5-coder-1.5b-chat` (previous main): often did not answer within 60–240 s on a busy GPU, and summaries described the prompt instead of the code.
- `sorc/qwen3.5-claude-4.6-opus-q4:2b`: empty reply after 75 s; hung generate calls.

### Embedding model

- `qwen3-embedding:0.6b`: 1024 dims, 2 s per request when idle.
- Not yet compared against `nomic-embed-text` on retrieval quality.

### Retrieval test (partial)

Subset: `src/core/helpers/forensics` (summary embedding on, `qwen3-embedding:0.6b`, `qwen2.5-coder-1.5b-chat`), index partially built at 187 chunks.

| Query | Expected | Top result |
|---|---|---|
| chain of custody log entries for evidence | `ChainOfCustodyLogger.cs` | hit |
| redact personal data from evidence | `EvidencePiiRedactor.cs` | hit |
| how long evidence is retained before deletion | `EvidenceRetentionPolicy.cs` | hit |
| signal jamming detection from RSSI readings | `JammingIncident.cs` | miss (likely not indexed yet) |

## Sources

- [smollm2 on the Ollama registry](https://registry.ollama.ai/library/smollm2)
- [codegemma:2b on the Ollama registry](https://registry.ollama.ai/library/codegemma:2b/blobs/9be8862a3637)
- [yi-coder on the Ollama registry](https://registry.ollama.ai/library/yi-coder)
- [Best Coding Models for Ollama in 2026](https://mljourney.com/?p=6343)
- [Qwen2.5-Coder 1.5B overview](https://localaimaster.com/models/qwen-2-5-coder-1-5b)
- [Ollama model explorer](https://ollama-explorer.vercel.app/models)

The search found no 0.5B coder model besides `qwen2.5-coder:0.5b` (which the test used) and no code-summarization benchmark for small models.

## Open work

1. Raw-text embedding comparison: with `enableSummaryEmbedding` off, chunks are embedded from raw code and no summary call is made (commit `11e44d4`). Compare against summary embedding on the same subset.
2. Embedding comparison: `qwen3-embedding:0.6b` vs `nomic-embed-text`, same subset, same queries.
3. Score all eight queries, not just the four that target the forensics subset.
4. Rebuild the full VideoForensics index with the chosen models. The subset and full index are paused: `F:\VideoForensics` and `F:\VideoForensics\src\core\helpers\forensics`.

## Tooling

- Summary model test script: `F:\mcp-worktrees\model-eval.ps1`, results in `F:\mcp-worktrees\model-eval.txt`.
- Router config backups sit next to `C:\ProgramData\SimpleModelServer\SimpleModelServer.config.json` (`.bak-<timestamp>`).
