# Plan: auto-documented context DB (systems, features, docs, functions) for the index

## Context
The TokenSaver index today tracks folders, files, chunks (semantic), and symbols (code index). It has no
notion of what the code is *for*. Sessions re-derive the same facts (branches, ports, which system owns a
file, which rule applies). The user wants:
1. A docs folder (configurable path) indexed into a Docs table.
2. Systems and Features tracked, with auto-generated documentation.
3. A Functions table whose rows link to Files, Systems and Features.
4. The same index DB to drive context and answer design questions.
5. Redundant data removed (carried over from the schema plan).

Earlier plans in this session (schema relink, semantic refresh skill) depend on this schema, so this plan
comes first.

## Context notes gathered from old transcripts (three read-only Haiku agents)
Source ids are transcript prefixes under `C:\Users\rsper\.claude\projects\`.

**Systems named in transcripts:** VideoForensics (Ring evidence capture, analysis, export: WebApp Blazor
port 5162, `Ui.Shared` Razor components, `data/core` MediaAnalysisService/RetentionService/UnitOfWork,
`providers/ring` ffmpeg tagger, MAUI client); TokenSaver (MCP service `TokenSaverMCP`, semantic index,
code index, debugger, config); SimpleModelServer (router 11435, Ollama 11434, `/admin/config`); Common
repo (shared contracts as local NuGet packages).

**Ports and paths:** Ollama 11434; SimpleModelServer router 11435; TokenSaver service owns 11436 (decided by user;
SimpleModelServer `/mcp` port still to verify against running services). Production: `C:\ProgramData\VideoForensics\` (Keys, CrashDumps),
DB `G:\VideoForensics\Database\videoforensics.db`, media `E:\VideoForensics`. TokenSaver installs at
`C:\Program Files\TokenSaver`.

**Decisions:** shared contracts in `Common` as local NuGet packages; DraftModel archived; TokenSaver reads
router config from SimpleModelServer `/admin/config`; index DB is per root (`<root>/.tokensaver/index.db`);
git safety helpers refuse `main`/`dev`; logs in a local `logs.db` with a retention job (not Cosmos).

**User rules:** config in settings files, never environment variables; execute without step-by-step
prompting; ask before commit or push; auto-fix CI, conflicts, and review comments under standing approval;
stop and report on a dirty checkout; verify results before reporting success; no nested boxes in settings
UI; black-on-gray text not allowed; keep worktree paths short; every project references
Microsoft.CodeAnalysis; stored paths relative to the media root, no backward-compat code.

**Conflicting rule (needs your confirmation):** one note says "DO NOT USE SONNET UNDER ANY CONDITION";
another says "ask sonnet to review all plans". Working reading: Haiku for implementation, Sonnet only for
read-only plan review, when you say so.

**Root causes that shaped the design:** per-root concurrent index passes re-summarized files (fixed by a
per-root single-flight gate); search against the wrong root opened an empty index (route to the right
root); baseline advanced before indexing finished (commit after success); a missing DI registration broke
a time-lapse check; a stale 15-minute validation cache; index tables had duplicated stamp columns.

**Domain facts (forensics):** EventIntegrityHash and ApiSourceHash are over the raw Ring payload, so they
cannot be rechecked from the DB alone; remote export never sets ArchiveSha256Hash; only the retention job
may set IsPurged and write the MediaPurged audit entry; never write to the live DB, use a read-only copy;
chain-of-custody page `/analyze/chain-of-custody`; original keys must be SHA-256 verified before deletion.

**Process flags:** the VideoForensics A agent reported writing a scratch file during a read-only task and
deleting it afterward. Its findings are used only where another source confirms them. Agent outputs that
arrived with harness flags for instruction-shaped text were treated as data.

## Target schema (SUPERSEDED by U1–U4 in Implementation plan; kept for history)
Keep from the relink plan: `Folders` (self-FK tree), `Files` (`FolderId` FK, many-to-one), `Chunks` with
`FileId` FK and no file-stamp columns, `Symbols` with `FileId` and no copied `LastModified`.

New tables:
1. **Docs**: `Id`, `Path` (unique, relative to the configured docs root), `Title`, `Kind`
   (`design` | `plan` | `rule` | `decision` | `note`), `Summary`, `ContentHash`, `UpdatedAt`. Rows come from
   a folder scan of the configured docs root.
2. **Systems**: `Id`, `Name` (unique), `Description`, `UpdatedAt`.
3. **Features**: `Id`, `Name` (unique), `Description`, `Status`, `UpdatedAt`, plus `SystemId` FK if
   many-to-one is chosen (see open decision 2).
4. **Functions**: reuse `Symbols` (already one row per function, with `FileId`). Adds `Summary` (from XML
   docs, else the function summary) and `Kind`. A separate table would duplicate `Symbols`, so this plan
   extends it. Open decision 3 confirms this.
5. **Link tables (many-to-many)**:
   - `FileSystems(FileId, SystemId)`, `FileFeatures(FileId, FeatureId)`
   - `SymbolSystems(SymbolId, SystemId)`, `SymbolFeatures(SymbolId, FeatureId)`
   - `DocSystems(DocId, SystemId)`, `DocFeatures(DocId, FeatureId)`
   - `DocLinks(DocId, FileId | SymbolId)` for doc-to-code references, optional.

Chunks link to systems through `Files`, so no chunk-level link table.

## Auto-documentation pipeline
1. **Docs root** is a config key `docs.root` in `.tokensaver/config.json` (default `docs/`). Changing it
   needs no code change.
2. **Frontmatter is the source of truth** for systems and features. Each doc may declare
   `system: [...]` and `feature: [...]`. The scanner upserts `Systems`/`Features` and the `Doc*` link rows.
3. **Folder defaults** fill links the frontmatter leaves out: a file under a configured folder maps to a
   system by path prefix (config `systems.paths`). Explicit frontmatter wins.
4. **Function docs**: the scan writes `Symbols.Summary` from XML docs when present. Target state after U5:
   the scan makes no model calls; undocumented functions are summarised later by U11 jobs.
5. **Triggers**: runs at the end of `code_index scan` (incremental) and on docs-root changes. Reuses the
   file-change hook from the refresh plan.
6. **Queries the context builder answers**: which system or feature owns a file or function; which
   functions and docs touch a feature; which docs are stale (hash mismatch); which files have no system.

## Units (SUPERSEDED by the Implementation plan U1–U15; kept for history)
1. Schema tests (red): Docs path unique; link tables cascade on delete of Docs, Files, Symbols, Systems,
   Features; a file can have several systems; `Symbols` has no `LastModified`.
2. Entities and `OnModelCreating` for Docs, Systems, Features, Doc*/File*/Symbol* link tables; remove
   redundant columns from the relink plan's list.
3. Docs scanner: reads the configured root, parses frontmatter, upserts Docs and link rows; tests use a temp
   folder with fixtures for frontmatter, folder defaults, and conflicts.
4. Functions summary write from XML docs during scan; test with a fixture file.
5. Context queries (service + tests): owner of a file or function, feature members, stale docs, unowned files.
6. Surface in `build_concise_context` (one-liner: counts and unowned files) and a `docs` action on
   `code_index` (contract doc and tests updated in the same change).
7. Rebuild the affected DB (the schema relink plan's rebuild step), then run the eight-query test.

## Verification
- Tests in `TokenSaver.CodeHelper.Tests`, `TokenSaver.TokenEconomy.Tests`, `TokenSaver.MCP.Tests` green.
- On the VideoForensics solution: Docs rows equal the files under `docs.root`; every system defined in this root
  has at least one file (systems defined in another root are exempt, see Fable review); a doc edit changes its `ContentHash` and marks it stale until the next scan.
- Context query "which system owns `EvidenceRetentionPolicy.cs`" returns the configured system.

## Fable review (16 findings; blockers first)
Verified against code: (a) `WorkspaceIndexService.cs` deletes all of a file's Symbols and re-adds them on
rescan (lines ~684–726), so any link or summary stored on a symbol is wiped each time (finding 2 confirmed).
(b) The code index and the semantic index share one `index.db` through two accessors (finding 3 resolved:
cross-table FKs are valid).

Blockers:
- Code-side links have no source. Add `files:` globs and `symbols:` names to feature docs, plus an XML-doc
  tag on symbols, so `FileFeatures`, `SymbolFeatures` get populated.
- Symbol identity: give Symbols a stable key (FileId + qualified name + signature hash) and upsert on rescan
  instead of delete-and-add. Apply the same to Files on rename.

Major:
- Docs duplicates Files: `Docs(Id, FileId unique FK, Title, Kind, Summary)`. Docs root outside the index
  root is forbidden.
- Drop `SymbolSystems`; derive a symbol's system from its file. Keep `SymbolFeatures` for overrides only.
- Replace polymorphic `DocLinks` with `DocFiles` and `DocSymbols`, both in the first cut.
- Link tables get composite PKs, reverse indexes, and `Source` (`frontmatter` | `path` | `code`), so
  removing an entry on an incremental scan can be implemented.
- Frontmatter drift: one defining doc per system or feature (`Kind`, `DefiningDocId`). Unknown names in other
  docs are scan warnings, not inserts. Match names case-insensitively on a slug.
- "Stale" is defined by content: store the linked content hash on each link row; a doc is stale when a linked
  file or symbol changed after the doc's hash last changed.
- Summaries: keep LLM summaries on chunks only. Symbols keep XML-doc text. `Docs.Summary` comes from
  frontmatter `summary:` or the first paragraph.
- Scope: this plan ingests only. Add a unit that writes or refreshes a per-system doc section between markers,
  a query returning doc summaries with owning symbols, and FTS5 over doc title and body.
- Systems are per root (each root has its own DB). Relax "every system has a file" for systems defined in
  another root, or add a shared registry.
Minor: CHECK constraints on `Kind` and `Status`; `Features` unique on `(SystemId, Name)`; a `Functions` view
filtered by `Kind`; scanner rules (longest-prefix match for `systems.paths`, Windows path normalization,
malformed YAML, deleted docs, forced rescan on `docs.root` change); ordering: relink schema → this plan →
refresh, or one combined migration with one rebuild.

## Extension ideas (Fable, proposals; not yet decided)
Goal: new providers without core changes.
1. Provider manifest: each provider declares `Id`, `Kind` (extractor, doc-source, summarizer, embedder,
   checker, renderer), `Version`, `Inputs`, `Outputs`, `RequiresModel`. Registered by DI scan. Derived rows
   carry `ProviderId`. First step: wrap the current symbol extractor as provider 1.
2. Typed sink: providers write through `IIndexSink` (UpsertSymbol, UpsertLink, UpsertFact). Untyped output goes
   to `Facts(SubjectKind, SubjectId, Predicate, Value, ProviderId, SourceHash)`. Risk: a dumping ground.
3. Pipeline order from declarations: topological sort by Inputs and Outputs. `RequiresModel` providers run
   only in refresh, so scan stays LLM-free by construction. A `Version` bump invalidates only that provider's rows.
4. Conformance kit: a base test class asserting idempotent re-run, delete-input-removes-rows, writes stay inside
   declared outputs, cancellation, and a truthful `RequiresModel`. Scaffold template for new providers.

Goal: answer design questions.
5. `ask` action returns an evidence pack: resolve the question to entities (FTS, symbol names, slugs), expand
   one or two link hops, return bounded rows with `path:line` and hash. The answer must cite row ids; gaps are listed.
6. Questions as rows: `Questions` and `QuestionEvidence`. An answered question becomes a `decision` doc with an
   `answers:` key. A cited row changing hash flags the decision for re-check.

Goal: reduce design effort.
7. Design brief: `brief <feature | file set>` returns owning system, applicable `rule` docs, prior decisions,
   recorded root causes, dependents, and open questions. Replaces transcript mining for new plans.
8. Scan digest: per-provider row counts in `ProviderRuns`; the scan reports only the delta.

Goal: find issues automatically.
9. `Findings(RuleId, Severity, Subject, Message, Fingerprint, FirstSeen, LastSeen, ProviderId)` plus
   `Suppressions`. SQL-only checks on scan: unowned files; features with no symbols; dangling doc links;
   undeclared cross-system dependencies and cycles; duplicate facts with different values; provider health
   (zero rows or a sharp drop). Note: the transcript notes give port 11436 to both SimpleModelServer `/mcp` and
   the TokenSaver service. Verify before relying on that port fact.

Goal: generated docs and diagrams.
10. Mermaid renderers from rows: system context, feature map, doc-to-code matrix, ER diagram from the EF model,
    provider pipeline graph. Generated blocks store a hash, so a hand edit becomes a finding, not an overwrite.
11. Provider catalogue page generated from manifests and `Providers`.

Suggested order: 1, 2, 4 (everything else becomes a provider), then 9, 5, 10.

## Initial load: staged, resumable (Fable proposal; costs are unmeasured estimates)
Goal: usable context in minutes, full coverage over time, bounded spend.

Stages (unmeasured; the `index plan` dry run replaces any cost figures before a stage is scheduled):

| Stage | Unlocks | Model cost |
|---|---|---|
| 0. Facts | ownership, navigation, XML docs, project graph, docs, FTS5 | 0 tokens |
| 1. File summaries (gated) | "what is this file for" for undocumented code | measured by dry run |
| 2. Chunk summaries on demand | body-level answers for the feature being asked about | measured by dry run |
| 3. Backfill | full coverage | measured by dry run; idle only |

- **Stage 0:** syntax-only parse (no compilation). Folders, files, symbols with stable keys, XML docs,
  `.csproj` references, docs frontmatter, `systems.paths`. FTS5 over names, XML docs and doc bodies. Commit
  per file; advance the baseline only on success.
- **Stage 1:** skip generated files, types already fully XML-documented, and trivial files. Input is the
  skeleton (signatures plus XML docs), not bodies. Order by owning feature, then in-degree. Conflict: the
  plan says LLM summaries are on chunks only. Decided: relaxed; file-level skeleton summaries are allowed, stored as kind `file-skeleton`.
- **Stage 2:** `ask` or `brief` resolves entities and raises pending jobs in scope.
- **Stage 3:** lowest priority, idle only, daily token cap in `config.json`. Skip rules may cut the 28k
  chunks to ~8–12k (to check with a dry run).
- **Resumability:** `SummaryJobs(SubjectKind, SubjectId, ContentHash, ProviderId, ProviderVersion, Stage,
  Priority, State, Attempts)`, one transaction per item; the per-root single-flight gate prevents duplicate
  passes; `ProviderRuns` records tokens spent.
- **Answering mid-load:** `ask` returns a coverage block over entities in scope (for example
  `facts 100%; file summaries 31/48; chunk summaries 12/410; stale 3`), tags each evidence row by tier
  (`fact`, `xml-doc`, `file-summary`, `chunk-summary`, `raw`), lists gaps and bumps their priority, and
  falls back to the raw signature plus `path:line` where no summary exists. Optional `fillBudgetMs`.

Cost-cutting ideas:
- Content-addressed summary cache keyed on hash(normalised text + prompt version + model), stored outside the
  per-root DB. Worktrees, branch switches and DB rebuilds cost zero calls. Likely the largest saving.
- Normalise before hashing (whitespace, comments, `using` order), so reformatting invalidates nothing.
- Skip rules as a provider: `*.g.cs`, `*.Designer.cs`, migrations, `obj/`, auto-properties. Store a
  "nothing to add" result so skipped items are never retried.
- `index plan` dry run: planned calls and estimated tokens per stage before spending.
- Chunk on symbol boundaries, so an edit invalidates one chunk (sliding windows shift every later chunk).
- Two hashes per symbol: body-only edits redo one chunk; the file skeleton is redone only when signatures change.
- Roll-up early cutoff: regenerate a feature or system summary only when a child summary's text changed.
- Change detection from `git diff --name-only <baseline>` plus status, not hashing 2,810 files.
- Summarise on commit or idle, not on save; coalesce repeated edits by replacing the pending job row.
- Serve stale summaries flagged `Stale=1` until replaced; coverage reports them.
- Dependents get a flag from link-row hashes, not a model call.
- Prompt-version bumps mark rows outdated and refresh lazily, never all at once.
- Per-edit budget guard: a mass rename or merge over N jobs drops to backfill and is reported.

## Corrections from code (Fable implementation review)
- No EF migrations exist. `WorkspaceIndexContextFactory.InitializeSchemaAsync` uses `EnsureCreatedAsync` plus hand-written
  `CREATE TABLE IF NOT EXISTS`. "One migration" means one schema-version bump (`PRAGMA user_version = 2`) and one rebuild.
- `SymbolEntity.Id` = SHA1(FilePath+Name+Line), so it changes when a line moves. `IndexOneFileAsync` deletes and re-adds
  symbols, and `RemoveFileAsync` and the bulk prune also delete. Symbol links and summaries are wiped on each rescan.
- `IndexOneFileAsync` calls `GetFileDescriptionAsync` (an LLM call) on every changed file. The scan is not LLM-free today.
- Chunks are keyed on `(RelativePath, StartLine, EndLine)`, also unstable. `RepoIndexer` copies file stamps onto every chunk.

## Implementation plan (ordered; test first; record each red run)
Order: U1–U7 are one schema change with one rebuild (after U7). Commits inside that span may be red until U7 lands
(U2 removes columns that U5/U6 still read); each unit is still one commit and must say so in its message.
Summary-stage order, to avoid the U5 regression (file descriptions stop before U11 exists): U5 keeps the
`GetFileDescriptionAsync` call behind a flag until U11 is green, then removes it. U7's provider wrap of the symbol
extractor is folded into U5, not a separate step. U8–U11 follow. U10 tests that need summary rows use fixtures;
U11 acceptance (dry run) runs after U11a/U11b split below. U12 (refresh) needs U7 and U11.

**U1. Schema version gate.** `WorkspaceIndexContextFactory.cs`, new `IndexSchemaVersion.cs`, `ChunkSchemaRecovery.cs`
generalised. Tests: `CreateAsync_FreshDb_SetsUserVersion2`, `CreateAsync_OldVersionDb_ThrowsSchemaOutdated`,
`Rebuild_OldVersionDb_WritesBackupAndRecreates`, `Rebuild_OldVersionDb_PreservesTokenSavings`.
Accept: opening a v1 DB never mutates it.

**U2. Relinked core entities.** `FileEntity`, `SymbolEntity`, `ChunkEntity`, `SymbolReferenceEntity`,
`WorkspaceIndexContext`, factory DDL.
- Files: add `FileKey` (unique GUID).
- Symbols: add `SymbolKey` (unique), `QualifiedName`, `SignatureHash`, `BodyHash`, `Summary`; drop `LastModified`.
- Chunks: add `FileId` FK (cascade) and nullable `SymbolId`; drop `RelativePath`, `FileLastModified`, `FileSize`,
  `FileHash`; unique `(FileId, ChunkKey)`.
- `SymbolReferences` keyed on `SymbolKey`; `Functions` view filtered by `Kind`.
Tests: `Symbols_Schema_HasNoLastModified`, `Chunks_Schema_HasFileIdAndNoFileStamps`,
`Files_DeleteFile_CascadesChunksAndSymbols`, `Symbols_DuplicateSymbolKey_Throws`,
`FunctionsView_MixedKinds_ReturnsOnlyFunctions`, `Schema_FactoryDdl_MatchesEfModel`.

**U3. Context tables.** Entities `Doc` (`FileId` unique FK, `Title`, `Kind`, `Summary`, `BodyHash`), `System`
(`Slug` unique, `DefiningDocId`), `Feature` (`SystemId` NOT NULL, unique `(SystemId, Slug)`, `DefiningDocId`).
Link tables `FileSystems`, `FileFeatures`, `SymbolFeatures`, `DocSystems`, `DocFeatures`, `DocFiles`, `DocSymbols`,
each with composite PK, reverse index, `Source` (`frontmatter|path|code`), `LinkedHash`. CHECK constraints on `Kind`,
`Status`, `Source`. FTS5 `DocsFts(title, body)`, `SymbolsFts(name, summary)`. No `SymbolSystems`; no polymorphic `DocLinks`.
Tests: `Docs_DuplicateFileId_Throws`, `Features_SameNameDifferentSystem_Allowed`, `Features_NullSystemId_Throws`,
`FileSystems_FileInTwoSystems_Allowed`, `Links_DeleteSystem_CascadesLinkRows`.

**U4. Operational tables.** `Providers`, `ProviderRuns`, `SummaryJobs(SubjectKind, SubjectId, ContentHash, ProviderId,
ProviderVersion, Stage, Priority, State, Attempts)` unique `(SubjectKind, SubjectId, ProviderId)`, `Findings`
(`Fingerprint`, `FirstSeen`, `LastSeen`), `Suppressions`, `Summaries(SubjectKind, SubjectId, Kind, Text, CacheKey, Stale)`. Single home per tier: XML-doc text lives
on `Symbols.Summary`; frontmatter/first-paragraph text on `Docs.Summary`; LLM output (chunk and `file-skeleton` tiers
only) lives in `Summaries`. No other summary columns.
Tests: `SummaryJobs_DuplicateSubject_ReplacesPendingRow`, `Findings_SameFingerprint_UpdatesLastSeen`.

**U5. Stable keys and upsert (`WorkspaceIndexService.cs`).** `IndexOneFileAsync`, `RemoveFileAsync`, the prune
(~L537), `RebuildReferencesAsync`. New `SymbolKeyBuilder`, `SymbolUpserter`. `SymbolEntry` gains signature and body hashes.
Remove the `GetFileDescriptionAsync` call from the scan; enqueue a `SummaryJobs` row instead.
- `SymbolKey` = SHA1(`FileKey` | `Kind` | `QualifiedName` | `SignatureHash`). Overloads distinguished by normalised parameter types.
- Upsert: load existing rows by key, update matches in place (`Line`, `Col`, `BodyHash`), insert new keys, delete only absent keys.
- Rename: if exactly one key removed and one added with equal `BodyHash`, rekey in place so links survive.
Tests: `IndexFile_LineShiftOnly_KeepsSymbolKeysAndLinks`, `IndexFile_BodyEdit_UpdatesBodyHashOnly`,
`IndexFile_SymbolRemoved_DeletesRowAndCascadesLinks`, `IndexFile_RenamedFileSameContent_KeepsFileIdAndSymbols`,
`IndexFile_Scan_MakesNoModelCalls`, `IndexFile_OverloadedMethods_GetDistinctKeys`.
File rename: match by `RelativePath`, then by unmatched path with equal `ContentHash`; `git diff --name-status -M` if a baseline exists.
Deletion of unmatched files happens only at the end of the scan.

**U6. `RepoIndexer` on `FileId`.** Symbol-boundary chunking; `ChunkKey` = `SymbolKey` or heading slug. Delete `StampChunksAsync`;
stamps read from `Files`. Tests: `IndexRepo_InsertLinesAbove_DoesNotResummarizeLaterChunks`,
`IndexRepo_UnchangedFile_ReadsNoBytes`, `IndexRepo_FileNotInFiles_CreatesFileRow`,
`IndexRepo_ExtensionFilteredRun_KeepsOtherChunks`. Accept: a second run on an unchanged repo makes zero model calls.

**U7. Provider manifest, typed sink, conformance kit.** `IIndexProvider` (`Id, Kind, Version, Inputs, Outputs,
RequiresModel`), `IIndexSink` (`UpsertSymbol`, `UpsertLink`, `UpsertSummary`, `RaiseFinding`), `ProviderPipeline`
(topological sort), `ProviderConformanceTests<T>`. Wrap the symbol extractor as provider 1, skip rules as provider 2.
Tests: `Pipeline_CyclicDeclarations_Throws`, `Pipeline_ScanMode_SkipsRequiresModelProviders`,
`Sink_WriteOutsideDeclaredOutputs_Throws`, `Provider_VersionBump_InvalidatesOnlyOwnRows`, `Provider_RunTwice_IsIdempotent`,
`Provider_InputDeleted_RemovesRows`. **Rebuild once after U7.**

**U8. Docs scanner provider.** Config `docs.root` (must lie under the index root) and `systems.paths`. Frontmatter keys
`system`, `feature`, `kind`, `summary`, `defines`, `files` (globs), `symbols`. Reads XML-doc `<feature>` for `Source=code`.
Tests: `Scan_DefiningDoc_UpsertsSystem`, `Scan_UnknownSystemInNonDefiningDoc_RaisesFindingNoInsert`,
`Scan_NestedSystemPaths_UsesLongestPrefix`, `Scan_FrontmatterAndPathConflict_FrontmatterWins`,
`Scan_MalformedYaml_RaisesFindingKeepsDocRow`, `Scan_EntryRemovedFromFrontmatter_DeletesOnlyFrontmatterLink`,
`Scan_DocsRootOutsideIndexRoot_Throws`, `Scan_DocsRootChanged_ForcesFullDocRescan`.
Accept: on VideoForensics, Docs row count equals the file count under `docs.root`.

**U9. Context queries and checks.** `ContextQueryService` (`OwnerOf`, `FeatureMembers`, `StaleDocs`, `UnownedFiles`),
`ChecksProvider`. Tests: `OwnerOf_SymbolWithoutOverride_ReturnsFileSystem`, `StaleDocs_LinkedSymbolHashChanged_ReturnsDoc`,
`StaleDocs_DocEditedAfterChange_ReturnsNone`, `Checks_FileWithoutSystem_RaisesUnownedFinding`,
`Checks_SuppressedFingerprint_NotReported`. Accept: `OwnerOf("EvidenceRetentionPolicy.cs")` returns the configured system.

**U10. `ask` action and evidence pack.** `code_index` actions `ask`, `docs`; `build_concise_context` one-liner; contract doc.
`EvidencePackBuilder`: FTS, names, slugs; up to two hops; rows carry `path:line`, hash, tier.
Tests: `Ask_KnownFeature_ReturnsRowsWithPathLineAndHash`, `Ask_NoSummaryYet_FallsBackToRawSignatureTier`,
`Ask_PartialLoad_ReportsCoverageBlock`, `Ask_Gaps_BumpsJobPriority`, `Ask_OverRowLimit_TruncatesAndListsGaps`.
Accept: MCP contract tests green; no model call when `fillBudgetMs=0`; `Ask_FillBudgetZero_MakesNoModelCall`;
the eight-query test (Verification thresholds) runs against the rebuilt forensics DB and is recorded here.
Summary-row tests use fixtures until U11a exists.

**U11a. Summary cache and staged loader.** `SummaryCache` (SQLite at `%LOCALAPPDATA%\TokenSaver\summary-cache.db`, key =
SHA256(normalised text | prompt version | model)), `TextNormalizer`, `SummaryJobRunner` (stages 1–3, one transaction per
item, daily token cap, existing per-root gate and `IndexPauseGate`).
Tests: `Cache_SameTextDifferentWhitespace_Hits`, `Cache_PromptVersionBump_Misses`,
`Runner_CancelledMidItem_ResumesWithoutDuplicateCalls`, `Runner_DailyCapReached_StopsAndRecordsRun`,
`Runner_SkipRuleMatch_StoresNothingToAddAndNeverRetries`, `Runner_RepeatedEdits_CoalescesToOneJob`,
`Runner_MassChangeOverBudget_DropsToBackfill`, `Runner_AfterRebuild_AllCacheHits`. Accept: rebuild then reload makes
zero model calls.

**U11b. Acceptance and stage enablement.** Runs the dry run (below) on the golden set, then enables stages only if
the Verification thresholds pass. Stage 3 stays off by default.

**U12. Refresh skill and hooks.** File-change hook → `IndexPathsAsync` → enqueue jobs. The skill runs `index plan` first.
Tests: `Hook_FileSaved_EnqueuesJobWithoutModelCall`, `Refresh_FailureMidRun_DoesNotAdvanceBaseline`.
Accept: an edit shows `Stale=1` in `ask` until refresh runs.

**U13. Migrate both `docs/pitfalls.md` files.** Convert each `###` entry to the structured form (`id:`, `theme:`, `symptom:`, `cause:`, `rule:`, `enforcedBy:`, `seen:`). Entry counts are asserted by a test, not fixed here. Assign `id:` and `theme:` to existing entries using the initial `lessons.themes` and `lessons.causeKeys` lists committed in this unit; `enforcedBy: none-yet` is allowed (`State=unenforced`). `CLAUDE.md` machine facts are mirrored to `ToolIncompat` in this unit; `CLAUDE.md` itself is not changed here.
Tests: `Scan_SameEntryTwice_OccurrencesUnchanged`, `Rebuild_PreservesOccurrenceCounts`, `Fingerprint_RewordedCause_SameId`.

**U14. Gotchas, promotion, landing.** `Gotchas`, `GotchaApprovals`, `GotchaOccurrences`, `Repos` identity (git common dir plus remote URL, falling back to common dir when no remote), proposal promotion, global write deny rule, export contract (field map, validator call, id assignment per C5).
Tests: `Promotion_TwoWorktreesOneRepo_NoGlobalRow`, `Promotion_Proposed_CopiesNoLocalText`, `GlobalWrite_ContainsRootPath_Rejected`, `Scan_UnknownCauseKey_RaisesFinding`.

**U15. Hooks, spool, capture allowlist, gate.** Spool writer, service drain, known-pattern error table, `lessons-check` gate with waivers.
Tests: `Capture_SecretInArg_StoredAsPlaceholder`, `Capture_UnmatchedErrorLine_Discarded`, `Hook_DbLocked_SpoolsAndExitsZero`, `Hook_ColdStart_UnderBudget` (replaced by a measured p95 in `HookRuns`; see Verification), `SessionStart_UnapprovedRow_NotInjected`, `LessonsCheck_ThemePathsChangedNoLesson_Fails`, `LessonsCheck_WhitespaceRuleEdit_Fails`, `LessonsCheck_UnknownWaiverCode_Fails`, `LessonsCheck_UnmappedPath_RaisesFinding`.
Accept: each R16 and Global §2/§4 rule is tied to one of these tests (R16 requires an enforcing check).

**Dry run (`code_index plan`).** Run after U7 and U11a on the forensics subset; it replaces the estimate table. Writes
nothing except a `ProviderRuns` row with `State=dry`. Reports per stage: candidates, skips by rule, cache hits, planned
calls after batching, input tokens (real tokenizer, real prompts), output tokens (median and p90 from a 30-item live sample),
seconds per call, projected wall time, projected days under the daily cap. Also chunk count before and after skip rules.
No stage is scheduled until these numbers are in.

**Rollback.** Backup with `VACUUM INTO index.db.v1-<timestamp>.bak`; build v2 as `index.db.new`, copy `TokenSavings`,
swap by rename, with the service stopped (WAL checkpointed first). `TokenSavings` is copied into v2 `index.db`; it is
not moved to `global.db`. Roll back by stopping the service, restoring the `.bak`, and reinstalling the previous build.
The `user_version` check ships in U1, before any schema change, so binaries from this release onward refuse a
mismatched DB. Earlier binaries have no check and must not be pointed at a v2 DB. The summary cache lives outside the DB, so rollback or a second
rebuild costs no model calls. Keep the backup until the eight-query test passes.
`global.db` has its own `user_version` and a `VACUUM INTO` backup. `hooks.capture.enabled=false` is the kill switch. Decided: promotion writes a proposal row in `global.db`. An explicit `gotcha_draft` export later moves an approved row into gotcha-db. Decided: authored state is exported to a JSONL file before any delete or rollback, and restored from that file.
Only derived rows rebuild from `pitfalls.md`. Authored state (approvals, `LessonWaivers`, `ToolIncompat` workarounds, `HookRuns`) cannot be rebuilt, so it must be exported to a text file before any delete or rollback. The earlier "deleting `global.db` is safe" claim was wrong.

**Out of scope for the first release.** `Facts` table; `Questions` and `QuestionEvidence`; `brief`; Mermaid renderers and
catalogue page; generated doc sections; cross-root system registry (info finding only); cross-system dependency and cycle
checks; feature and system roll-up summaries; stage 3 idle scheduling (jobs exist, runner off by default);
in-place migration of v1 rows.

## Practices (Fable review)
Intake lives in `SimpleModelServer\.claude\task_failure_log.md`; resolved causes live in the two `docs/pitfalls.md` files. The `mcp` repo has no task log. Past failures below come from the plan's root causes.

### Required (every change)
- R1 Scan paths make no model calls; model work is enqueued as `SummaryJobs`. Enforced by `IndexFile_Scan_MakesNoModelCalls`.
- R2 Rows use stable keys (`FileKey`, `SymbolKey`, `ChunkKey`), never line or position. Past failure: symbol links wiped on rescan.
- R3 Writes are idempotent upserts; delete only keys absent after a full pass. Enforced by the conformance kit.
- R4 One index pass per root, through the per-root gate. Code review for new entry points (no named gate test yet).
- R5 Advance the baseline only after success. Enforced by `Refresh_FailureMidRun_DoesNotAdvanceBaseline`.
- R6 Every query resolves its root explicitly. Past failure: wrong root returned an empty index. Proposed test: an unindexed root errors.
- R7 No copied stamp or content columns; read through the FK. Enforced by schema tests.
- R8 Schema change bumps `user_version` and rebuilds; old DBs are never mutated. Enforced by U1 tests.
- R9 Providers write only declared outputs, through `IIndexSink`. Enforced by `Sink_WriteOutsideDeclaredOutputs_Throws`.
- R10 Staleness comes from content hashes, never a time cache. Past failure: 15-minute validation cache.
- R11 Unknown system or feature names raise a finding, not an insert.
- R12 A new service has a test that resolves it from the real DI container. Past failure: missing registration. Proposed.
- R13 Test first; record the red run; the tool contract doc changes in the same commit.
- R14 Gate builds with `ENFORCE_CODE_QUALITY=true` (warnings-as-errors is off by default).
- R15 Read-only tasks write nothing, scratch files included. Past failure: an agent wrote and deleted a scratch file. Proposed: `git status` unchanged after the task.
- R16 Failure-to-rule loop: a fix for a theme or pattern issue adds or updates the rule that stops it recurring, in the same change, and that rule names its enforcing check.
  - Mechanism: the `Gotchas` table (Global §2). `Lessons` is a view. Entries come from `lessons.sources` (`id:`, `theme:`, `rule:`, `enforcedBy:`, `seen:` per heading). Repeats add `GotchaOccurrences` rows, not counter increments.
  - `EnforcedBy` must resolve to a test, analyzer id, or gate step; a `ChecksProvider` finding fires when it does not. Legacy entries may be `enforcedBy: none-yet`, which sets `State=unenforced` (info finding, gate passes).
  - Gate step `lessons-check` keys on the diff, not the commit prefix. Map `git diff --name-only <base>...HEAD` to themes via `lessons.themes`. A PR touching theme paths passes only if (a) an entry's non-whitespace content hash changed and its `enforcedBy` test is added or modified in the same diff, or (b) it carries `Lesson: none (<code>: <text>)`, where code is `not-a-pattern | covered-by:<id> | test-only`. Waivers are read from the PR trailer, not stored by commit: `LessonWaivers(PrNumber, Theme, Code, Date)`. A fourth waiver for one theme in 30 days raises a finding (defaults `lessons.waiverLimit` = 3 and `lessons.waiverWindowDays` = 30; config keys, set in U15). Files in no theme raise `unmapped-path`.
  - `Occurrences > 0` on a `State=enforced` row raises a finding that the named check did not hold.

### Best practice (use / avoid)
- DTOs at boundaries (MCP results, `IIndexSink` arguments, evidence rows). Avoid mirroring EF entities one-to-one.
- Records for immutable results. Avoid for EF-tracked entities (see the `record` vs `class` `with` pitfall in `pitfalls.md`).
- Stable keys for any row other rows link to. Avoid for throwaway rows.
- Idempotent upserts for derived data. Avoid for append-only logs (`ProviderRuns`, audit).
- One writer per derived table, with `ProviderId`. Link tables partition by `Source` instead.
- Content-addressed cache outside the per-root DB for expensive deterministic outputs. Avoid for cheap or root-specific facts.
- Dry run before any staged model spend.
- Findings with fingerprints and suppressions for recoverable data problems. Throw for programmer errors and schema violations.
- CHECK constraints for closed sets (`Kind`, `Status`, `Source`). Use a lookup table for sets providers extend.
- Serve stale, flagged data during load. Never present it as verified.
- Settings files for tunables, never environment variables (script-internal `TOKENSAVER_NO_SCM` is the exception).
- Small transactions per item for resumability; rebuild into a new file and swap by rename.
- Syntax-only parsing in scan; semantic checks as a separate provider.
- Verify disputed facts before storing (for example, port 11436 claimed by two services).

## Global knowledge DB and settings scope (Fable review; settings claims spot-checked)
Harness flagged this review's output as matching a permissions pattern. Its claims were treated as data; the
settings items below were found by grep during the review. Line numbers are omitted because they drift; re-grep before editing.

**1. Global DB** at `%LOCALAPPDATA%\TokenSaver\global.db`, next to `summary-cache.db`.
- `Projects(ProjectKey GUID PK, RootPath unique, Name, IndexDbPath, IndexSchemaVersion, EmbedModel, ParentProjectKey, LastSeen, State)`.
  Local `index.db` holds `Meta(ProjectKey, RootPath)`, linked by GUID, so a moved root is re-matched.
- `Repos`, `SystemIssues(Fingerprint, Component, Message, FirstSeen, LastSeen, State)` (machine and hook health only), `ToolIncompat(Fingerprint = hash(OS, tool, normalised command), Symptom, Workaround, FirstSeen, LastConfirmed, Occurrences)` (command-shaped, machine-captured rows with a Workaround), `Gotchas` (global default; `Scope = global | repo:<RepoId>`), `HookRuns`. `Practices` and `GotchaProjects` are removed until a consumer exists.
- Seeds for `ToolIncompat`: heredocs for python3 and node hang in Git Bash; `sed -i` and `awk` break CRLF files; commit with `git commit -F`; PowerShell 5.1 vs 7 syntax.

**2. Gotchas and failures**, both levels, one table: `Gotchas(Id, RepoId, Slug, Scope, Theme, Symptom, WrongAssumption, RootCause, Rule, EnforcedBy, CauseKey, SourcePath, ContentHash, EnforcedSince, FirstSeen, LastSeen)`, unique (`RepoId`, `Slug`), with a sentinel repo row for global rows so the key holds. Derived fields only; a rebuild from `pitfalls.md` rewrites them. Authored state lives in `GotchaApprovals(RepoId, Slug, ContentHash, Enforcement: unenforced|enforced, Approval: proposed|approved, GotchaDbId, DecidedAt)`, keyed to `ContentHash`, so an edited `Rule` needs re-approval. The two axes are separate columns. `EnforcedSince` limits "check did not hold" findings to occurrences after enforcement. `Scope` is `global | repo:<RepoId>`, where `RepoId` comes from `Repos`, not `ProjectKey`, so worktrees of one repo share a scope. `GotchaDbId` is the shard id once the gotcha exists in gotcha-db. `Lessons` is a view (`Gotchas WHERE Rule IS NOT NULL`). Local adds `PromotedGlobalId`. Occurrences are rows: `GotchaOccurrences(GotchaId, ProjectKey, Date, SourceLine)`, parsed from dated lines in the source doc (no commit SHA: squash merges break it). Counts are derived from that table, so R8 rebuilds keep them.
- **Scanned sources (decided):** `lessons.sources` lists two files, one per repo: `F:\source\mcp\docs\pitfalls.md` (the `mcp` repo) and `F:\source\mcp\SimpleModelServer\docs\pitfalls.md` (the submodule). Each gets its own `Repos` row. Entries today are a `###` heading with prose symptom, cause, and fix. They have no `id:`, `theme:`, or `enforcedBy:` fields, so the scanner needs those added (U13). `F:\source\mcp\.claude\rules\pitfalls.md` is a path-scoped pointer and is not scanned.
- **Landing rule (revised):** a gotcha goes in `global.db` with `Scope=global` by default. It is stored as `Scope=repo:<RepoId>` when it names a project path, drive, port, or local system or feature slug, or the authored entry is marked project-specific. Ambiguous rows land as `repo:` (fail closed), with a test for drive, port, and slug cases. OS, shell, and git tool-quirk cases go to `ToolIncompat`, not `Gotchas`.
- **Fingerprint and identity:** the authored `id:` slug, unique per repo. Cross-project matching uses an optional `cause-key:` from the controlled list in `lessons.causeKeys`. A text hash only raises a `possible-duplicate` finding and never merges.
- **Promotion (review round 3):** "distinct" means distinct `Repos` rows (git common dir plus normalised remote URL). Worktrees, clones, and submodules of one repo count once. A `repo:<RepoId>` row that recurs in two distinct repos, and that has a `cause-key:`, is proposed for `Scope=global`. Rows without `cause-key:` are never promoted. The proposal holds only `CauseKey`, `Theme`, and `Rule`. The user approves it; local `Symptom` and `RootCause` text is never copied.
- **Findings and issues:** `Findings` stay separate (recomputed each scan). `SystemIssues` holds machine and hook health only.
- **Intake log:** `F:\source\mcp\SimpleModelServer\.claude\task_failure_log.md` is intake (`date | phase | what failed | cause | fix`) and is not parsed into rows. Resolved entries move to a pitfalls file at phase review. `ChecksProvider` raises `unpromoted-failures` when that log changed after the pitfalls files and has entries older than N days. No `failure_log.md` exists; the earlier plan reference was wrong.

**3. Settings scope**: moved to `C:\Users\rsper\.claude\plans\settings-scope.md`.

**4. Auto-update.** Hooks only append one JSONL line to a spool, with a 300 ms target and no DB open. The TokenSaver service drains the spool, upserts `Projects`, probes tool versions, and runs promotion. SessionStart reads a precomputed one-liner file.
- **SessionStart:** read the precomputed one-liner of `State=approved` rows only, injected as id plus `Rule`. Check that root and index paths exist; report a missing path as a `SystemIssues` row.
- **PostToolUse Bash/PowerShell:** on failure or timeout, spool the capture allowlist only: tool, subcommand, flag names, exit code. Arguments become typed placeholders. The error is an error class matched against a known-pattern table (`CS\d+`, git fatal templates); unmatched lines are discarded. A repeated fingerprint proposes a candidate; a later success after a changed command proposes a `Workaround`. Approval is manual.
- **PostToolUse Edit/Write:** spool the path (plan U12). Changes to rule or pitfall docs are picked up by the scan, not by the hook.
- **Stop:** the service flushes the spool, runs promotion, updates `LastConfirmed`, writes `HookRuns`.
- **Never captured:** output bodies, environment values, file contents, error text outside the known-pattern table; token-like strings, `Authorization` headers, URLs with credentials; paths under `Keys`, `.ssh`, `.env*`; email addresses; forensic media or live DB content. Promotion, `Rule` and `EnforcedBy` text, approval, and pruning are manual. A disabled hook is reported on the next SessionStart.
- **Hook error:** exit 0, never block the tool, spool to JSONL. Three consecutive failures disable the hook and raise a `SystemIssues` row.
- **DB locked:** WAL, 500 ms busy timeout, one writer. On timeout, spool and drain at the next Stop or SessionStart.
- **Stale registry:** a missing root sets `State=missing` and is never auto-deleted; a known key at a new path sets `moved`; a row is pruned only after `registry.pruneDays` (default 90), with a finding.

## Decisions (answered)
- Systems and features: defined by defining docs; `systems.paths` only links files.
- Feature to system: many-to-one (`SystemId` NOT NULL, unique `(SystemId, Name)`).
- Functions: extend `Symbols` with stable keys and add a `Functions` view.
- Summary rule: relaxed. File-level `file-skeleton` summaries are allowed alongside chunk summaries.
- Cost figures: measure first. Before any stage is scheduled, run a dry run on the forensics subset
  (`index plan`) and replace the Fable estimates with measured per-stage numbers.

## Decisions (gotcha repo reconciliation, answered)
- **C1:** the "gotcha-db / gotcha-ingest / gotcha-mcp" split is removed. Our work is the **lessons loop** inside TokenSaver (U13–U15).
- **C2:** split by purpose. Reusable knowledge (language, dependency, platform) lives in `gotcha-db`. Process lessons (`Rule`, `EnforcedBy`, occurrences, waivers) stay in TokenSaver.
- **C3:** `docs/pitfalls.md` files are the authored source for lessons. SQLite is a derived cache rebuilt from them. `gotcha-db` shards hold only reusable records.
- **C6 (revised by user):** `Gotchas` stay in `global.db`, so the global DB is the default home for gotchas. A gotcha specific to one project is stored at repo level, scoped by `RepoId`. The scope field is `Scope = global | repo:<RepoId>`. (`GotchaProjects` is removed; see §1.)

## Reconciliation with the gotcha repo plans (Fable, verified against files)
Design A = repo plans (`mcp/plans/gotcha-system.md`, `TokenSaver/plans/nosql.md`, `gotcha-db/`, `gotcha-ingest/`, `gotcha-mcp/` PLAN + phase files). Design B = this plan.

Verified facts: `docs/pitfalls.md` has 16 entries (mcp root) and `SimpleModelServer/docs/pitfalls.md` has 14. The `SimpleModelServer/.claude/task_failure_log.md` intake log exists. `gotcha-db` holds 17 gotchas, 4 snippets, 2 patterns, 2 error mappings. `gotcha-mcp` is scaffold-only (no C# yet). `gotcha-ingest` has core plus one source module. None of the three repos appears in `.gitmodules`. `gotcha.schema.json` is `additionalProperties: false` with no lesson fields (`theme`, `rule`, `enforcedBy`, `causeKey`, `state`, occurrences). `nosql.md` §3.1 says 15 seed records were already extracted from `mcp/docs/pitfalls.md`.

Where each B item lands:
- TokenSaver: `Gotchas`, `GotchaOccurrences`, `LessonWaivers`, `Repos`, `global.db`, `lessons-check` gate, hook spool and capture allowlist, intake-log finding, SessionStart injection.
- gotcha-db: the deny rule (paths, ports, slugs), in `validate.py` and mirrored in Gotcha.Core. Goes in `gotcha-db/plans/phase-4-contrib-security.md`, with test vectors under Phase 3. The 17 existing records need a check against it first.
- gotcha-ingest: no `pitfalls.md` source module (removed; the U14 export is the only path into gotcha-db).
- gotcha-mcp: promotion-to-draft becomes `gotcha_draft` (Phase 4). Upstreaming is Phase 5, behind the security gate.

Conflicts (decide before any code):
- **C1 BLOCKER (name collision):** B's "gotcha-db / gotcha-ingest / gotcha-mcp" split names clash with A's three repos. Recommended: delete the B "Gotcha components (split)" section and call B's work the lessons loop in TokenSaver.
- **C2 BLOCKER (standalone vs TokenSaver):** Recommended split by purpose. Reusable knowledge (language, dependency, platform) stays in gotcha-db. Process lessons (`Rule`, `EnforcedBy`, occurrences, waivers) stay in TokenSaver. Alternative: fold everything into A.
- **C3 BLOCKER (source of truth):** A is git JSON shards plus zstd snapshot, and rejected SQLite. Recommended: `pitfalls.md` is the authored source for lessons, with SQLite as a derived cache. gotcha-db shards are the source for reusable records.
- **C6 (superseded by the user's revision above):** the recommendation to drop global gotcha tables no longer applies.
- **C4 MAJOR (double ingest):** U13 adds an optional `gotcha:` cross-reference (shard id) per entry. No gotcha-ingest module reads `pitfalls.md` (see review round 3).
- **C5 MAJOR (identity):** the authored slug stays local. A promoted row takes a shard-path id at draft time.
- **C7 MAJOR (validation):** the TokenSaver scanner validates lesson fields only. Anything headed to gotcha-db goes through Gotcha.Core.
- **C8 MAJOR (contribution gate):** promotion stops at a local draft. Upstreaming stays behind gotcha-mcp Phase 5.
- **C9 MAJOR (ingest language):** accept both. The scanner is C#, the ingest is Python, and they feed different stores.
- **C10 MAJOR (hooks scope):** hooks, gate, and SessionStart stay out of A's repos, in TokenSaver U15.
- **C11 MINOR (dedupe):** no change. difflib in A and the hash-flag-only rule in B are compatible.
- **C12 MINOR (ports):** no conflict. 11437 is uncontested.
- **C13 MINOR (stale text):** `nosql.md` §5 says "5 tools" but lists 6. `mcp/CLAUDE.md` says two submodules, but `.gitmodules` has three. Fix both when wiring the repos.

Unchanged: no A item is made unnecessary by B.

Placement order (review round 3): U13 (structured `pitfalls.md`) after U8, no gotcha-repo dependency. A new `global.db` unit (schema, `user_version`, single writer, JSONL export and import) comes before U14. U14 (`Gotchas`, `GotchaApprovals`, proposals) follows it. The gotcha-db export needs only the Gotcha.Core validator (gotcha-mcp Phase 1) and the deny rule, not gotcha-mcp Phase 4. U15 (spool, gate, SessionStart) after U12 and U14.

## Review round 3 (Fable, all plans) — status
Decided by the user: remove the gotcha-ingest `pitfalls.md` source module (the U14 export is the only path into gotcha-db). Move the Settings scope section to its own plan file.
Applied in this plan: scope key is `RepoId` everywhere; authored state split into `GotchaApprovals`; `Enforcement` and `Approval` are separate columns; `EnforcedSince` for legacy entries; `cause-key:` required for promotion; the `global.db` unit precedes U14; the export is decoupled from gotcha-mcp Phase 4; C6 marked superseded.

Still to apply (mechanical, no decision needed):
- `lessons-check` is stateless: diff plus PR trailers. `CommitSha` is dropped everywhere (squash merges break it); waivers come from trailers.
- `unpromoted-failures` uses entry dates, not file mtimes (R10). `lessons.intake` is a list.
- Keep always-loaded machine facts in `CLAUDE.md`; mirror them to `ToolIncompat` only (U13 and Settings §3).
- Split the SimpleModelServer Inno entry into three causes; promote the root "PowerShell 7" preamble to an entry; update counts.
- gotcha-db `source` values cite the stable `id:`, not `pitfalls.md#…` anchors.
- Fix the `phase-1-foundation.md` claim "CI runs it on every PR": the vectors are not run by `validate.py`; add a vector runner (gotcha-db Phase 3).
- Settings `autoMode` and the other settings items move to their own plan.
- Add: draft shadowing rule (reject a draft whose id exists in the base; tag draft results unreviewed); metrics in `HookRuns` (spool depth, drain lag, discarded lines, hook p95 against 300 ms); U15 length cap on injected rule text.
- Repo-relative paths in `lessons.sources`.
- Done in this revision: `Practices` and `GotchaProjects` removed; `CommitSha` removed; superseded lists marked. Still to do: the auto-proposed `Workaround` is removed from the spec (manual approval only).

## Local model budget (1–2B concise contexts; Fable review)
- One local chat model of 1–2B parameters produces all summaries, skeleton summaries, and evidence-pack text. Roles `summary.chunk`, `summary.fileSkeleton`, and `evidence.gloss` share it. First candidate `qwen2.5-coder:1.5b`; alternates `qwen3:1.7b` and `deepseek-coder:1.3b`, chosen by the dry run. `embed` = `qwen3-embedding:0.6b`. `sorc/qwen3.5` is never requested.
- Budget: `num_ctx` 4096; chat model at most 2 GB VRAM; p50 at most 3 s per item. Code defaults outside this band (`summarize` = qwen2.5-coder:7b, `rerank` = qwen2.5-coder:3b, `embed` = nomic-embed-text, per `TokenEconomyConfig.cs`) are replaced by this budget.
- Embed model change (nomic to qwen3-embedding, different dimension) forces a full re-embed; mixed vectors raise a finding.
- Token estimates from the Initial load table are void until re-measured with the chosen model's tokenizer.

## Output contract and token caps (U11a, before U11)
- Requests use Ollama `format` with a JSON schema: `{purpose: string ≤160 chars, inputs: string[] ≤5, effects: string[] ≤5, nothingToAdd: bool}`. `temperature` 0, fixed seed, `num_predict` 120. One item per call.
- Validator rejects invalid JSON, over-length fields, a purpose that echoes the symbol name or prompt, identifiers absent from the input, and identical output for different inputs. One retry, then store tier `raw` (signature plus `path:line`) with `State=rejected`. Rejected text is never stored or cached. R17: model output is stored only after schema validation.
- Tests: `Summary_InvalidJson_FallsBackToRawSignature`, `Summary_OverLength_Rejected`, `Summary_InventedIdentifier_Rejected`, `Summary_EchoesName_Rejected`, `Summary_Rejected_NotCached`, `Summary_Request_UsesTemperatureZeroAndSchema`.
- Config: `summaries.maxInputTokens` 2500 (larger items use the skeleton, not the body; replaces the blind 4096-byte read), `summaries.maxOutputTokens` 120, `context.conciseTokenCap` 2000, `ask.maxRows`.
- The model never receives a whole context. `EvidencePackBuilder` and `build_concise_context` assemble it in code, capped at 2000 tokens. Fill order: fact, xml-doc, file-summary, chunk-summary, raw; drop from the bottom tier first and list dropped items as gaps. `contextSizeLimit` (120000) stays for the cloud pipeline; fix its unit in the contract doc.
- Tests: `Ask_OverTokenCap_DropsLowestTierFirst`, `Runner_ItemOverInputCap_UsesSkeleton`.

## Extra data for small models (user decision)
- **Precomputed file skeletons:** signatures plus XML doc comments per file, built with no model in the scan (Stage 0). Summaries start from this text. The model rewrites it into the schema; it does not invent the signatures.
- **Glossary of project terms:** a small file (`.tokensaver/glossary.json`, in the repo) mapping project nouns (for example "chain of custody", "retention") to the symbols and files that implement them. The model glosses only terms the glossary links. Entries come from the docs and XML docs, and a term with no link raises an info finding.
- Not chosen: hand-written frontmatter summaries; the model keeps writing summaries from the code and docs the index already has.
- Tests: `Skeleton_BuiltWithoutModelCall`, `Glossary_TermWithoutLink_RaisesFinding`, `Summary_UsesSkeletonAsInput`.

## Model lifecycle and gates
- `SummaryJobRunner` uses exactly one chat model per run and never switches mid-run. `keep_alive` 10 m while jobs are pending, 0 on the last item. Before a run it checks free VRAM against the model's measured footprint; if short it does not start and records a `SystemIssues` row. Embeddings run as a separate phase; `embed.device=cpu` when both do not fit. The runner yields to interactive requests via `IndexPauseGate`.
- Stage 1 is gated: `gemma3:1b` is excluded from candidates, and stage 1 is not scheduled, until the router reload has a recorded cause. The dry run counts model loads per run; more than one load is a failure.
- Summary cache key = SHA256(normalised text | prompt version | output-schema version | model name | model digest | num_ctx). `Summaries` gains `Model` and `PromptVersion`. A configured-model change marks rows `Stale=1` and re-queues lazily. Tests: `Cache_ModelChanged_Misses`, `Cache_ModelDigestChanged_Misses`, `Runner_ModelSwitched_RequeuesLazily`.

## Verification thresholds (eight-query test defined)
- Eight-query test: eight named queries over the forensics subset, each with an expected file or symbol, stored in the test project. Golden set: 30 items with required keywords.
- Dry run runs each candidate on the golden set and reports schema-valid rate, rejection rate, keyword hit rate, retrieval, p50/p90 seconds per item, peak VRAM, and model loads per run.
- Accept a model at: schema-valid ≥95%; rejection ≤10% (stop above 25%); keyword hit ≥80%; eight-query top-1 ≥6/8 and top-3 8/8; no duplicate summaries; p50 ≤3 s.
- If no candidate passes, stage 1 stays off and tiers remain fact, xml-doc, raw.
- Run the dry run in U11b, before any stage is enabled.
- Hook budget: the 300 ms target is unmeasured. Measure hook p95 on this machine first (U15), then set the budget in config.
- Open before U1 (database-access section): the index database location and owning project in `TokenSaver` are unconfirmed.

## Single point of database access
Moved to `C:\Users\rsper\.claude\plans\single-point-db-access.md`. Answered decisions are recorded there.

## U13 initial lists (approved)
Themes: `wix-msi`, `wix-build-race`, `windows-service`, `http-localhost`, `csharp-config`, `csharp-nullable`,
`csharp-warnings`, `ps7-syntax`, `ps-null-order`, `ps-pipeline`, `ps-paths`, `ps-exit-codes`, `model-config`,
`installer-config`, `router-warmup`, `nuget-versions`, `ci-test-discovery`, `inno-setup`, `ps-args`.

Cause keys: `msiexec-no-elevation`, `wix-cab-concurrent`, `wix-debug-build-scope`, `svc-scm-env`,
`svc-session0-logging`, `svc-port-in-use`, `http-sys-urlacl`, `json-jsonc-parse`, `record-with`, `null-suppressed`,
`warnings-conditional`, `ps51-defaults`, `ps-null-left`, `ps-unwrap`, `ps-hardcoded-path`, `exit-code-unchecked`,
`ps-automatic-var`, `model-keepalive-zero`, `warmup-timeout-short`, `stream-read-cancelled`, `json-enum-number`,
`config-not-written`, `self-referential-model`, `nuget-downgrade`, `slnx-project-unlisted`, `sdk-vstest-unsupported`,
`inno-numeric-version`.

## Superseded open-decision list (answered above)
1. Where systems and features are defined: frontmatter in docs (recommended) only, or also inferred from
   folders (`systems.paths` defaults)?
2. Feature to system: many-to-one (each feature in one system) or many-to-many?
3. Functions: extend `Symbols` (recommended, no duplicate table) or add a separate Functions table?
4. Sonnet: "DO NOT USE SONNET" or "ask sonnet to review all plans"? I'll use Haiku unless you say otherwise.
