# Gotcha System — master index

Design record (decisions, data model, rationale): `TokenSaver/plans/nosql.md`.
Execution plans live in each repo; read only the active phase file + matching hints.

| Repo | Role | Plan entry point |
|---|---|---|
| `gotcha-db/` | Data: sharded JSON records (gotchas, snippets, patterns, errors) | `gotcha-db/plans/PLAN.md` |
| `gotcha-ingest/` | Python: pulls docs, builds/validates records into gotcha-db | `gotcha-ingest/plans/PLAN.md` |
| `gotcha-mcp/` | C#: snapshot compiler + MCP server (6 tools) | `gotcha-mcp/plans/PLAN.md` |

Status (2026-07-07): schemas + 17 gotchas/4 snippets/2 patterns validated;
ingest core ran end-to-end; snapshot format benchmarked (zstd-JSON pack);
gotcha-mcp is scaffold-only — Phase 1 (C# validator) is the next code milestone.
Not yet done: git init/push + submodule wiring (native shell, per FUSE-mount quirks).

---

## OPEN WORKSTREAM — Contribution security (needs its own plan before contrib opens)

Once external contributions are accepted, gotcha-db becomes an attack surface:
records are **executed** in a limited sense (regexes run over user diffs, snippets
are code handed to AI clients to insert into real projects). Before `gotcha
contribute` goes public, plan and build:

1. **Malicious-content scanning on incoming PRs** (CI, blocking):
   - AV scan of all changed files (e.g. ClamAV action) — cheap, catches the dumb
     stuff and satisfies the baseline.
   - **Snippet review is the real risk**: a `.tpl` suggesting `curl | sh`, credential
     exfiltration, weakened crypto, or subtly-wrong security defaults is more
     dangerous than any binary. Needs a deny-pattern lint (network calls to
     hardcoded hosts, base64 blobs, obfuscated strings) + mandatory human review
     on every snippet/pattern change — no auto-merge for those paths, ever.
   - **Regex DoS**: catastrophic-backtracking check on every `detection`/
     `error_signatures`/`match` value (runtime matchTimeout is the backstop;
     CI should reject the pattern outright).
   - **URL allowlist** for `source` fields (docs domains, GitHub) — a gotcha whose
     "source" link is a phishing page gets served to AI clients as authoritative.
2. **Provenance minimum**: require signed commits or verified GitHub accounts on
   contrib PRs; record author in git only (no in-record trust fields yet — schema
   already reserves room).
3. **Blast-radius controls**: contributions land in a `staging/` branch consumed
   only by opt-in snapshots until promoted; MCP clients default to release
   snapshots built from reviewed main.
4. **Client-side hardening already planned** (gotcha-mcp `hints/mcp-tool-safety.md`):
   drafts path-traversal guard, size caps, regex matchTimeout. The items above are
   the server/repo side of the same threat model.

Where it lands: a future `gotcha-db/plans/phase-4-contrib-security.md` +
CI workflow changes; `gotcha contribute` (gotcha-mcp Phase 5) must not ship to
other users before items 1–3 exist. Solo use is unaffected — your own PRs, your
own review.
