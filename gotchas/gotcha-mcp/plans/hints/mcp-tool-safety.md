# Hint: MCP tool safety (all inputs are AI-supplied)

Every tool parameter arrives from an AI client. Treat as untrusted:

1. **`gotcha_draft` writes to disk.** The record `id` becomes a file path. Guard:
   id must match `^[a-z0-9_/-]+$` (schema already enforces), and the resolved path
   `Path.GetFullPath(Path.Combine(draftsRoot, id + ".json"))` must start with
   `Path.GetFullPath(draftsRoot) + Path.DirectorySeparatorChar` (ordinal). Reject
   otherwise. Cap record JSON at 64KB. Drafts may contain `detection` regexes —
   they run later with matchTimeout (see snapshot hint #5), which is why that
   timeout is non-negotiable.
2. **Input caps**: `gotcha_error` 32KB, `gotcha_check` diff 1MB, everything else
   16KB. Over cap → clean tool error naming the cap, not truncation.
3. **Diff parsing** (`gotcha_check`): only lines starting `+` inside hunks, skip
   `+++` headers; track file path from `+++ b/<path>` and line numbers from hunk
   headers `@@ -a,b +c,d @@`. Malformed diff → error result listing what was
   expected, never an exception. Don't run detection regexes on removed (`-`) lines.
4. **Regex execution over input**: every DB/detection regex already carries
   matchTimeout 1s; additionally wrap the per-tool scan loop in a 10s budget and
   return partial results + warning if exceeded.
5. **Error results, not exceptions**: tools return structured
   `{ ok: false, error: "..." }` payloads. An unhandled exception in one tool call
   must not affect the server (host pattern from TokenSaver.MCP handles this —
   verify with a test that throws inside a tool).
6. **No secrets in responses**: scanner/bootstrap may read config files; tool
   responses must only ever contain DB records, rendered templates, and derived
   metadata — never raw file contents from the user's project.
