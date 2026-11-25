"""CLI: gotcha-ingest run <language> <kind> --db <gotcha-db checkout> [--source NAME]

Discovers source modules under gotcha_ingest.sources.<language>.<kind>, calls each
module's collect(), and hands the records to core.writer.write_batch.
"""
from __future__ import annotations

import argparse
import importlib
import pkgutil
from pathlib import Path

from .core.writer import write_batch


def iter_source_modules(language: str, kind: str, only: str | None = None):
    pkg = importlib.import_module(f"gotcha_ingest.sources.{language}.{kind}")
    for info in pkgutil.iter_modules(pkg.__path__):
        if only and info.name != only:
            continue
        yield importlib.import_module(f"{pkg.__name__}.{info.name}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="gotcha-ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run source modules for one (language, kind) pair")
    run.add_argument("language")
    run.add_argument("kind", choices=["gotchas", "snippets", "patterns", "errors"])
    run.add_argument("--db", type=Path, required=True, help="path to a gotcha-db checkout")
    run.add_argument("--source", help="run a single named source module")
    args = ap.parse_args()

    records = []
    for mod in iter_source_modules(args.language, args.kind, args.source):
        batch = mod.collect()
        print(f"{mod.__name__}: {len(batch)} records")
        records.extend(batch)
    if not records:
        print("no records collected")
        return
    written = write_batch(args.db, records)
    print(f"wrote {len(written)} files (validated)")


if __name__ == "__main__":
    main()
