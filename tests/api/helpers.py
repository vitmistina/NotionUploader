"""Factories and assertion helpers for API tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict

from src.platform.config import Settings

_SENTINEL = object()


def make_nutrition_payload(**overrides: Any) -> Dict[str, Any]:
    """Return a canonical nutrition request payload with optional overrides."""

    payload: Dict[str, Any] = {
        "food_item": "Apple",
        "date": "2023-01-01",
        "calories": 95,
        "protein_g": 0.5,
        "carbs_g": 25,
        "fat_g": 0.3,
        "meal_type": "Snack",
        "notes": "Fresh",
    }
    payload.update(overrides)
    return payload


def make_nutrition_page(**overrides: Any) -> Dict[str, Any]:
    """Return a Notion page payload resembling a stored nutrition entry."""

    page: Dict[str, Any] = {
        "id": "page-apple",
        "properties": {
            "Food Item": {"title": [{"text": {"content": "Apple"}}]},
            "Date": {"date": {"start": "2023-01-01"}},
            "Calories": {"number": 95},
            "Protein (g)": {"number": 0.5},
            "Carbs (g)": {"number": 25},
            "Fat (g)": {"number": 0.3},
            "Meal Type": {"select": {"name": "Snack"}},
            "Notes": {"rich_text": [{"text": {"content": "Fresh"}}]},
        }
    }
    properties = page["properties"]

    notes_value = overrides.pop("notes", _SENTINEL)
    if notes_value is _SENTINEL:
        pass
    elif notes_value is None:
        properties.pop("Notes", None)
    else:
        properties["Notes"] = {
            "rich_text": [{"text": {"content": notes_value}}],
        }

    for key, value in {
        "food_item": "Food Item",
        "date": "Date",
        "calories": "Calories",
        "protein_g": "Protein (g)",
        "carbs_g": "Carbs (g)",
        "fat_g": "Fat (g)",
        "meal_type": "Meal Type",
    }.items():
        if key in overrides:
            override_value = overrides.pop(key)
            match key:
                case "food_item":
                    properties[value] = {
                        "title": [{"text": {"content": override_value}}]
                    }
                case "date":
                    properties[value] = {"date": {"start": override_value}}
                case "meal_type":
                    properties[value] = {"select": {"name": override_value}}
                case _:
                    properties[value] = {"number": override_value}

    page["id"] = overrides.pop("id", page["id"])
    page.update(overrides)
    return page


def build_nutrition_create_payload(
    settings: Settings, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the Notion create payload expected from a nutrition request."""

    properties: Dict[str, Any] = {
        "Food Item": {"title": [{"text": {"content": payload["food_item"]}}]},
        "Date": {"date": {"start": payload["date"]}},
        "Calories": {"number": payload["calories"]},
        "Protein (g)": {"number": payload["protein_g"]},
        "Carbs (g)": {"number": payload["carbs_g"]},
        "Fat (g)": {"number": payload["fat_g"]},
        "Meal Type": {"select": {"name": payload["meal_type"]}},
    }
    notes = payload.get("notes")
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    return {
        "parent": {"database_id": settings.notion_database_id},
        "properties": properties,
    }


def assert_nutrition_entry(entry: Dict[str, Any], **expected: Any) -> None:
    """Assert the API response entry matches the provided expectations."""

    for key, value in expected.items():
        assert entry.get(key) == value, f"Expected entry {key}={value!r}, saw {entry.get(key)!r}"


def make_strava_event(**overrides: Any) -> Dict[str, Any]:
    """Return a canonical Strava webhook event."""

    event: Dict[str, Any] = {
        "aspect_type": "create",
        "event_time": 1,
        "object_id": 42,
        "object_type": "activity",
        "owner_id": 1,
        "subscription_id": 1,
    }
    event.update(overrides)
    return event


def encode_signed_strava_event(
    event: Dict[str, Any], *, client_secret: str
) -> tuple[bytes, str]:
    """Serialize an event and compute the Strava signature."""

    body = json.dumps(event, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(client_secret.encode(), body, hashlib.sha256).hexdigest()
    return body, signature
