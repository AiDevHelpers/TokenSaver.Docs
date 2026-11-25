"""Pydantic v1/v2 API mismatch gotchas.

Hand-authored from the pydantic migration guide. Also serves as the reference
example of a source module: implement collect() -> list[Record], never touch paths.
"""
from gotcha_ingest.core.records import Gotcha

SOURCE = "https://docs.pydantic.dev/latest/migration/"


def collect() -> list[Gotcha]:
    return [
        Gotcha(
            id="dependencies/python/pydantic/1/no-model-dump",
            title="Pydantic v1 has no model_dump()/model_dump_json()",
            language="python",
            kind="code-pattern",
            severity="error",
            applies_to={"dependency": "pydantic", "version_range": ">=1.0 <2.0"},
            symptoms=["AttributeError at runtime on code copied from v2 docs/examples"],
            bad_pattern="model.model_dump()",
            good_pattern="model.dict()",
            detection={"kind": "regex", "pattern": r"\.model_dump(_json)?\(", "file_glob": "*.py"},
            error_signatures=[r"AttributeError: .* has no attribute 'model_dump'"],
            explanation="model_dump()/model_dump_json() were introduced in pydantic v2. "
                        "On v1 use .dict()/.json(). AI-generated code frequently mixes the two APIs.",
            source=SOURCE,
            related=["dependencies/python/pydantic/2/dict-deprecated"],
        ),
        Gotcha(
            id="dependencies/python/pydantic/2/dict-deprecated",
            title="Pydantic v2 deprecates .dict()/.json() in favor of model_dump()",
            language="python",
            kind="code-pattern",
            severity="warning",
            applies_to={"dependency": "pydantic", "version_range": ">=2.0"},
            symptoms=["PydanticDeprecatedSince20 warnings", "json() argument errors after upgrade"],
            bad_pattern="model.dict()",
            good_pattern="model.model_dump()",
            detection={"kind": "regex", "pattern": r"\.(dict|json)\(\)", "file_glob": "*.py"},
            error_signatures=["PydanticDeprecatedSince20"],
            explanation="v2 renamed .dict() -> model_dump() and .json() -> model_dump_json(). "
                        "The old names emit deprecation warnings and will be removed in v3.",
            source=SOURCE,
            related=["dependencies/python/pydantic/1/no-model-dump"],
        ),
    ]
