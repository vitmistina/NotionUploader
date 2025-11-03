"""Builder helpers to express test inputs succinctly."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def notion_number(value: float | None) -> Dict[str, Any]:
    return {"number": value}


def notion_rich_text(content: str | None) -> Dict[str, Any]:
    if content is None:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": content}}]}


def notion_title(content: str) -> Dict[str, Any]:
    return {"title": [{"text": {"content": content}}]}


def make_notion_profile(properties: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Construct a Notion profile payload with optional property overrides."""

    base_properties: Dict[str, Any] = {
        "FTP Watts": notion_number(None),
        "Weight Kg": notion_number(None),
        "Max HR": notion_number(190),
    }
    if properties:
        base_properties.update(properties)
    return {"properties": base_properties}


def make_notion_workout(*, id: str | None = None, properties: Dict[str, Any] | None = None, **overrides: Any) -> Dict[str, Any]:
    """Build a Notion workout page with nested property overrides."""

    base: Dict[str, Any] = {
        "id": id or "workout-1",
        "properties": {
            "Name": notion_title("Workout"),
            "Date": {"date": {"start": "2025-10-08"}},
            "Duration [s]": notion_number(3600),
            "Distance [m]": notion_number(10000),
            "Elevation [m]": notion_number(150),
            "Type": notion_rich_text("Run"),
            "Notes": notion_rich_text(None),
            "Average Heartrate": notion_number(None),
            "Max Heartrate": notion_number(None),
            "TSS": notion_number(None),
            "IF": notion_number(None),
        },
    }
    if properties:
        base["properties"].update(properties)
    merged = _deep_merge(base, overrides)
    return merged


def make_strava_token_response(**overrides: Any) -> Dict[str, Any]:
    """Return a Strava token refresh payload with optional overrides."""

    base = {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 120,
    }
    base.update(overrides)
    return base


def _deep_merge(original: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(original)
    for key, value in overrides.items():
        if key not in result:
            result[key] = value
            continue
        if isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
