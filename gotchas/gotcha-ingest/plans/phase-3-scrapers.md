# Phase 3 — Doc scrapers

Goal: semi-automated candidate records from changelogs/migration guides. Candidates
are NOT publishable records — a human (or stronger model) reviews the generated PR.

Read `hints/scraping.md` before writing fetch code.

## Design (keep this shape)

```
sources/<lang>/gotchas/<package>_changelog.py
  fetch()    -> raw doc text (cached to .cache/, respect etag)
  extract()  -> list[Candidate]   # breaking-change bullets, deprecations
  collect()  -> list[Gotcha]      # only candidates that map cleanly; set
                                  # severity="info" and title prefix "[candidate]"
```

- `[candidate]` prefix + `info` severity marks records needing review; reviewer
  promotes by editing severity/title in the PR.
- Start with ONE scraper: pydantic changelog (well-structured, known format).
  Second: Express releases. Do not generalize until two concrete scrapers work.
- Extraction heuristics live per-scraper. Do NOT build a generic "changelog parser"
  abstraction first — it will be wrong.

## Acceptance

- Scraper run is idempotent: re-running against unchanged docs produces zero diffs.
- Network failures degrade to cached copy with a warning, not a crash.
- Generated batch passes validate.py like any other.
