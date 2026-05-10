"""Tests for committed OpenAPI schema synchronization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.main import app, build_openapi_schema


def test_committed_openapi_schema_matches_generated_contract() -> None:
    """The committed schema stays synchronized with the app contract."""

    cached_schema = app.openapi_schema
    try:
        app.openapi_schema = None
        generated_schema = build_openapi_schema(app)
    finally:
        app.openapi_schema = cached_schema
    committed_schema = json.loads(Path("openapi.json").read_text())

    assert generated_schema == committed_schema


def test_every_committed_openapi_operation_is_non_consequential() -> None:
    """OpenAI action metadata marks every operation as non-consequential."""

    schema = json.loads(Path("openapi.json").read_text())

    for path, method, operation in _iter_operations(schema):
        assert operation["x-openai-isConsequential"] is False, (path, method)
        assert operation["is_consequential"] is False, (path, method)


def _iter_operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    operations: list[tuple[str, str, dict[str, Any]]] = []
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if isinstance(operation, dict):
                operations.append((path, method, operation))
    return operations
