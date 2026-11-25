"""Snapshot format benchmark: SQLite vs zstd-compressed JSON pack.

Decides plan §9 open question. Workloads modeled on the MCP server's real access:
  A. cold start -> first lookup (server restart / hot reload)
  B. lookup by id (gotcha_expand, gotcha_snippet)
  C. filter by language+dependency (gotcha_check: deps manifest -> applicable gotchas)
  D. scan all error_signatures (gotcha_error: regex match over signatures)
"""
import json
import os
import random
import sqlite3
import string
import tempfile
import time

import zstandard

random.seed(42)

def make_records(n):
    langs = ["csharp", "python", "powershell", "node", "rust", "go"]
    deps = ["pydantic", "express", "maui", "efcore", "requests", "react", "serde", None, None]
    recs = []
    for i in range(n):
        lang = random.choice(langs)
        dep = random.choice(deps)
        recs.append({
            "schema_version": 1,
            "id": f"languages/{lang}/gotchas/topic{i % 40}/g{i}",
            "title": "".join(random.choices(string.ascii_lowercase + " ", k=60)),
            "language": lang, "kind": "code-pattern", "severity": "warning",
            "applies_to": {"dependency": dep, "version_range": ">=1.0 <2.0"} if dep else {},
            "symptoms": ["".join(random.choices(string.ascii_lowercase + " ", k=80)) for _ in range(2)],
            "error_signatures": [f"Error{i % 500}: .*"] if i % 3 == 0 else [],
            "explanation": "".join(random.choices(string.ascii_lowercase + " ", k=400)),
            "source": "https://example.com/doc",
        })
    return recs

def bench(n):
    recs = make_records(n)
    ids = [r["id"] for r in recs]
    sample = random.sample(ids, 1000)
    tmp = tempfile.mkdtemp()
    out = {"n": n}

    # --- zstd JSON pack ---
    pack_path = os.path.join(tmp, "pack.json.zst")
    t = time.perf_counter()
    blob = zstandard.ZstdCompressor(level=9).compress(json.dumps(recs).encode())
    with open(pack_path, "wb") as f:
        f.write(blob)
    out["pack_build_s"] = time.perf_counter() - t
    out["pack_size_kb"] = os.path.getsize(pack_path) / 1024

    t = time.perf_counter()
    with open(pack_path, "rb") as f:
        loaded = json.loads(zstandard.ZstdDecompressor().decompress(f.read()))
    by_id = {r["id"]: r for r in loaded}
    by_lang_dep = {}
    for r in loaded:
        key = (r["language"], r["applies_to"].get("dependency"))
        by_lang_dep.setdefault(key, []).append(r)
    out["pack_coldload_ms"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    for i in sample: _ = by_id[i]
    out["pack_id_lookup_us"] = (time.perf_counter() - t) * 1e6 / len(sample)

    t = time.perf_counter()
    for _ in range(100): _ = by_lang_dep.get(("python", "pydantic"), [])
    out["pack_filter_us"] = (time.perf_counter() - t) * 1e6 / 100

    # --- SQLite ---
    db_path = os.path.join(tmp, "snap.db")
    t = time.perf_counter()
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE r(id TEXT PRIMARY KEY, language TEXT, dependency TEXT, body TEXT)")
    con.execute("CREATE INDEX ix ON r(language, dependency)")
    con.executemany("INSERT INTO r VALUES (?,?,?,?)",
        [(r["id"], r["language"], r["applies_to"].get("dependency"), json.dumps(r)) for r in recs])
    con.commit(); con.close()
    out["sqlite_build_s"] = time.perf_counter() - t
    out["sqlite_size_kb"] = os.path.getsize(db_path) / 1024

    t = time.perf_counter()
    con = sqlite3.connect(db_path)
    _ = json.loads(con.execute("SELECT body FROM r WHERE id=?", (sample[0],)).fetchone()[0])
    out["sqlite_coldstart_ms"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    for i in sample:
        _ = json.loads(con.execute("SELECT body FROM r WHERE id=?", (i,)).fetchone()[0])
    out["sqlite_id_lookup_us"] = (time.perf_counter() - t) * 1e6 / len(sample)

    t = time.perf_counter()
    for _ in range(100):
        _ = [json.loads(b) for (b,) in con.execute(
            "SELECT body FROM r WHERE language=? AND dependency=?", ("python", "pydantic"))]
    out["sqlite_filter_us"] = (time.perf_counter() - t) * 1e6 / 100
    con.close()
    return out

for n in (5000, 50000):
    r = bench(n)
    print(f"\n=== {n} records ===")
    print(f"size:        pack {r['pack_size_kb']:8.0f} KB   sqlite {r['sqlite_size_kb']:8.0f} KB")
    print(f"cold->first: pack {r['pack_coldload_ms']:8.1f} ms   sqlite {r['sqlite_coldstart_ms']:8.2f} ms")
    print(f"id lookup:   pack {r['pack_id_lookup_us']:8.2f} us   sqlite {r['sqlite_id_lookup_us']:8.2f} us")
    print(f"lang+dep:    pack {r['pack_filter_us']:8.2f} us   sqlite {r['sqlite_filter_us']:8.2f} us")
    print(f"build:       pack {r['pack_build_s']:8.2f} s    sqlite {r['sqlite_build_s']:8.2f} s")
