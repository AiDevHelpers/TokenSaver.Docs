# Hint: snapshot load + hot reload

The patterns here are easy to get subtly wrong:

1. **Immutable snapshot, atomic swap.** `Snapshot` is fully immutable after
   construction (readonly dictionaries, no lazy init). The server holds
   `private volatile Snapshot _current;`. Reload = build a complete NEW Snapshot on
   a background task, then a single reference assignment. Tools capture
   `var snap = _current;` ONCE at the start of a request and use only `snap` —
   never re-read `_current` mid-request (torn view across a swap).
2. **No locks on the read path.** If you find yourself adding a lock around lookups,
   the design is wrong — reference swap is the whole concurrency story.
3. **FileSystemWatcher fires multiple events per save** (and editors write via
   temp+rename). Debounce: restartable 500ms timer; rebuild once after quiet.
   Also handle the watcher's error event (buffer overflow) by scheduling a rebuild.
4. **ZstdSharp**: `new Decompressor().Unwrap(bytes)` needs the decompressed size in
   the frame header — our compressor writes it by default; still guard with a
   50MB cap before allocating (`Decompressor.GetDecompressedSize`).
5. **Compiled regexes live in the Snapshot** (error signatures, detection patterns),
   compiled once at load with `RegexOptions.Compiled` + 1s matchTimeout. A record
   whose regex fails to compile at load: log + skip that record, don't fail the
   whole load (the DB validated upstream; a draft might not have).
6. **Overlay ordering**: base snapshot records first, then `.gotcha/overrides`, then
   `.gotcha/drafts`, later wins by id. Implement as "last write wins into the same
   dictionary" — do not build three-layer lookup chains.
7. Deserialize with `System.Text.Json` source-generated context (AOT-friendly,
   faster); records are strict JSON — no tolerant options here.
