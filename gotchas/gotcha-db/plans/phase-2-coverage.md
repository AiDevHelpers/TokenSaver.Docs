# Phase 2 — Coverage growth

Goal: enough breadth that `gotcha_check`/`gotcha_scaffold` are useful outside this
repo's own stack. Work in small PRs (5–15 records each), one language/topic per PR.

Before writing anything, read `hints/authoring.md`.

## Ordered backlog

1. **Python gotchas** — asyncio (await in wrong context, forgotten `await`), mutable
   default args, `is` vs `==`, requests timeout-missing. Dir:
   `languages/python/gotchas/<topic>/`.
2. **Node/TS gotchas** — floating promises, `??` vs `||`, Express 4→5 changes under
   `dependencies/node/express/4/` and `/5/`.
3. **More patterns + their snippets** — python: `fetch-parse-store` (requests +
   pydantic + repository); csharp: `background-worker-with-channel`. Each pattern
   needs its skeleton snippets in the same PR or validation fails.
4. **Error mappings** — add one for every gotcha that has `error_signatures` (grep
   for gotchas lacking a mapping; mapping ids under `languages/<lang>/errors/` or
   `platforms/<platform>/errors/`).
5. **C# / .NET dependency gotchas** — EF Core tracking vs no-tracking, HttpClient
   socket exhaustion (new-per-request), under `dependencies/dotnet/<package>/<major>/`.

## Acceptance per PR

- `python3 validate.py` → ALL VALID.
- Every new gotcha has `source` set to a real URL or doc path.
- New records link to related existing records (`related`) where sensible.
