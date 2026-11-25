# Hint: writing a source module

Copy `sources/python/gotchas/pydantic_migration.py` as the template. Rules that
prevent the common mistakes:

1. Module lives at `sources/<language>/<kind>/<topic>.py` and implements exactly
   `collect() -> list[Record]`. No other public API. No side effects at import time.
2. Import records from `gotcha_ingest.core.records`. Do NOT build dicts by hand —
   the dataclasses strip empty fields and pin `schema_version` for you.
3. Choose ids BEFORE writing content: `dependencies/<eco>/<pkg>/<major>/<name>` for
   dependency-version gotchas, `languages/<lang>/gotchas/<topic>/<name>` otherwise.
   The writer derives the file path from the id — a wrong id is a wrongly-placed file.
4. Record-quality rules are in gotcha-db `plans/hints/authoring.md` (regex
   portability, kind selection, false-positive scoping). Follow them — validation
   catches syntax, not judgment.
5. If the module produces Snippets, the `template` field holds the .tpl body; declare
   every `{{var}}` in `variables` with kind `context` unless you're sure it's
   style/dependency.
6. Cross-reference: if two records relate, set `related` in BOTH directions.
