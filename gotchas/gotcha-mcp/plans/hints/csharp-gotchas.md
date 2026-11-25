# Hint: C# in this repo (read before writing any)

Inherited from TokenSaver/mcp pitfalls — these have bitten before:

1. Parsing external JSON config (VS Code settings, claude configs): they're JSONC.
   Always `JsonDocumentOptions { CommentHandling = Skip, AllowTrailingCommas = true }`.
   BUT gotcha-db records are strict JSON — validate those WITHOUT tolerant options,
   or the C# validator accepts files the Python one rejects (parity break).
2. Types used with `with { ... }` must be `record`, not `class`.
3. CS0246 on a primary-constructor parameter type = missing `using`, not missing
   package.
4. Nullable is on solution-wide. Don't `!`-suppress; config-bound and deserialized
   fields ARE nullable — handle it.
5. `TreatWarningsAsErrors` may be conditional on env var `ENFORCE_CODE_QUALITY`
   (copy TokenSaver's Directory.Build.props behavior); build with it set before
   calling anything clean.
6. Regex: compile once, store in static/field with `RegexOptions.Compiled`. Set
   `matchTimeout` (1s) on regexes that run over user/AI-supplied input — DB regexes
   are semi-trusted (drafts!) and catastrophic backtracking is a DoS.
7. Paths: always `Path.GetFullPath` + ordinal comparison when checking containment;
   `Path.Combine(root, userInput)` with `..` escapes the root silently.
8. `HttpListener`/URL prefixes: `localhost` vs `127.0.0.1` are DIFFERENT http.sys
   registrations (see mcp/docs/pitfalls.md). Kestrel avoids this — use Kestrel like
   TokenSaver.MCP does; keep health-probe host and bind host in agreement.
