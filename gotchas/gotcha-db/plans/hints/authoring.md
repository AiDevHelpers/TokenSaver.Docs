# Authoring hints (read before writing any record)

Mistakes a fast pass tends to make, and the fix:

1. **`id` must equal the file path** minus `.json`, forward slashes, lowercase
   kebab/underscore. Writing the record first and picking the path later causes
   mismatches — decide the path FIRST, copy it into `id`.
2. **Pick `kind` honestly.** If the mistake can't be found by scanning source text,
   it is NOT `code-pattern` — use `environment`/`build`/`runtime`/`config` and put
   the "how to confirm" into `diagnosis`, observable effects into `symptoms`. Do not
   invent a `detection` regex for something that isn't in source code.
3. **Regex portability.** Patterns run under BOTH Python `re` and .NET `Regex`. Stay
   in the common subset: no possessive quantifiers (`*+`), no atomic groups
   (`(?>...)`), no `\p{...}` unicode classes, no inline flags mid-pattern. Lookahead/
   lookbehind are OK. Escape literal dots. Test mentally against a real match AND a
   near-miss.
4. **`detection.pattern` false positives.** A pattern like `\.dict\(\)` matches any
   `.dict()` in any library. Scope with `file_glob` and prefer distinctive API names.
   When in doubt, set `severity: warning`, not `error`.
5. **Snippets:** every `{{variable}}` in the `.tpl` MUST appear in the sidecar
   `variables` map, and vice versa. Variable `kind`: `style` (resolved from style
   chain), `dependency` (from scanned deps), `context` (caller supplies — use this
   when unsure).
6. **Patterns:** `intent_tags` are matched against free-text intent — include the
   words a user would actually say ("weather", "display data", "save to db"), not
   just technology nouns. Minimum 3 tags. Every step `placeholder` needs an exact
   `TODO(gotcha:<placeholder>)` marker in the referenced skeleton .tpl — check both
   directions before committing.
7. **`version_range`** uses semver syntax (`>=1.0 <2.0`). If the ecosystem's native
   range differs (PEP 440, NuGet), put the native string in `applies_to.source_range`
   and the semver normalization in `version_range`.
8. Run `python3 validate.py` after EVERY few files, not once at the end — errors
   compound and the messages are per-file.
