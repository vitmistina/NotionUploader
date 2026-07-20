from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from platform.config import get_settings  # noqa: E402

from notion.infrastructure.workout_schema import (  # noqa: E402
    WORKOUT_EXTENSION_SCHEMA,
    classify_workout_schema,
    notion_property_definition,
)
from services.notion import NotionClient  # noqa: E402


async def main() -> int:
    settings = get_settings()
    client = NotionClient(settings=settings)
    database = await client.retrieve_database(settings.notion_workout_database_id)
    compatibility = classify_workout_schema(database)
    summary: dict[str, Any] = {
        "database": "workout",
        "status": "complete",
        "added": [],
        "already_present": sorted(compatibility.compatible),
        "type_conflicts": sorted(compatibility.type_conflicts),
    }
    if compatibility.type_conflicts:
        summary["status"] = "type_conflict"
        print(json.dumps(summary, sort_keys=True))
        return 1
    if compatibility.missing:
        properties = {
            name: notion_property_definition(WORKOUT_EXTENSION_SCHEMA[name])
            for name in compatibility.missing
        }
        await client.update_database(
                settings.notion_workout_database_id, {"properties": properties}
        )
        final = classify_workout_schema(
            await client.retrieve_database(settings.notion_workout_database_id)
        )
        summary["added"] = sorted(compatibility.missing)
        summary["already_present"] = sorted(final.compatible)
        summary["type_conflicts"] = sorted(final.type_conflicts)
        summary["status"] = "updated"
        if final.missing or final.type_conflicts:
            summary["status"] = "incomplete"
            print(json.dumps(summary, sort_keys=True))
            return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except Exception as exc:
        # Deliberately omit exception messages: HTTP clients and settings
        # validation errors can contain database identifiers or credentials.
        print(
            json.dumps(
                {
                    "database": "workout",
                    "status": "error",
                    "error_code": "NOTION_SCHEMA_OPERATION_FAILED",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        exit_code = 1
    raise SystemExit(exit_code)
