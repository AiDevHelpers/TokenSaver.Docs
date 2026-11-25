"""Sharded writer: the only code allowed to place files in a gotcha-db checkout.

Source modules return records; this module derives each file path from the record id
(id == repo-relative path, enforced by gotcha-db CI), writes the batch, then runs
gotcha-db's own validate.py. A failing batch is rolled back — nothing lands.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .records import Record, Snippet


def write_batch(db_root: Path, records: list[Record]) -> list[Path]:
    """Write records into db_root; validate; roll back all of them on failure."""
    written: list[Path] = []
    backups: dict[Path, bytes | None] = {}
    try:
        for rec in records:
            path = db_root / f"{rec.id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            backups[path] = path.read_bytes() if path.exists() else None
            path.write_text(json.dumps(rec.to_json(), indent=2) + "\n", encoding="utf-8")
            written.append(path)
            if isinstance(rec, Snippet):
                tpl = db_root / f"{rec.id}.tpl"
                backups[tpl] = tpl.read_bytes() if tpl.exists() else None
                tpl.write_text(rec.template, encoding="utf-8")
                written.append(tpl)
        _validate(db_root)
        return written
    except Exception:
        for path, original in backups.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise


def _validate(db_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(db_root / "validate.py")],
        cwd=db_root, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"batch failed gotcha-db validation:\n{result.stdout}{result.stderr}")
