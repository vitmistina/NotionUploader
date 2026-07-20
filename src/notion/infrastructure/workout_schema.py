"""Shared Notion workout extension schema manifest and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WORKOUT_EXTENSION_SCHEMA: dict[str, str] = {
    "Start Time": "date",
    "External ID": "rich_text",
    "Provider Source": "rich_text",
    "Provider Client": "rich_text",
    "Device": "rich_text",
    "Payload Key": "rich_text",
    "TSS Origin": "rich_text",
    "Load Family": "rich_text",
}


@dataclass(frozen=True)
class WorkoutSchemaCompatibility:
    compatible: frozenset[str]
    missing: tuple[str, ...]
    type_conflicts: tuple[str, ...]
    unavailable: bool = False


def classify_workout_schema(database: dict[str, Any]) -> WorkoutSchemaCompatibility:
    properties = database.get("properties", {}) if isinstance(database, dict) else {}
    compatible: list[str] = []
    missing: list[str] = []
    conflicts: list[str] = []
    for name, expected_type in WORKOUT_EXTENSION_SCHEMA.items():
        payload = properties.get(name)
        if payload is None:
            missing.append(name)
        elif payload.get("type") == expected_type:
            compatible.append(name)
        else:
            conflicts.append(name)
    return WorkoutSchemaCompatibility(
        compatible=frozenset(compatible),
        missing=tuple(missing),
        type_conflicts=tuple(conflicts),
    )


def notion_property_definition(notion_type: str) -> dict[str, Any]:
    return {notion_type: {}}
