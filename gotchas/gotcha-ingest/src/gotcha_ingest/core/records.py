"""Record types mirroring gotcha-db's JSON Schemas.

The schemas in gotcha-db/metadata/schema/ are the source of truth; these dataclasses
exist for ergonomic construction in source modules. validate.py is still the gate —
if these drift from the schemas, validation fails, not silently diverges.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, [], {})}


@dataclass
class Gotcha:
    id: str
    title: str
    language: str
    kind: str  # code-pattern | environment | build | runtime | config
    severity: str  # error | warning | info
    explanation: str
    applies_to: dict[str, str] = field(default_factory=dict)
    symptoms: list[str] = field(default_factory=list)
    bad_pattern: str | None = None
    good_pattern: str | None = None
    detection: dict[str, str] | None = None
    error_signatures: list[str] = field(default_factory=list)
    fix_snippet: str | None = None
    diagnosis: str | None = None
    source: str | None = None
    related: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass
class Snippet:
    id: str
    language: str
    description: str
    template: str  # written to the sidecar .tpl
    variables: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        d = _clean(asdict(self))
        d.pop("template")
        return {"schema_version": SCHEMA_VERSION, **d, "variables": self.variables}


@dataclass
class Pattern:
    id: str
    title: str
    language: str
    intent_tags: list[str]
    summary: str
    components: list[dict[str, Any]]
    applies_to: dict[str, str] = field(default_factory=dict)
    gotchas: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    source: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass
class ErrorMapping:
    id: str
    match: str
    gotchas: list[str]
    language: str | None = None
    platform: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **_clean(asdict(self))}


Record = Gotcha | Snippet | Pattern | ErrorMapping
