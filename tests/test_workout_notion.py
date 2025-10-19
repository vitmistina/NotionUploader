import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.settings import Settings
from src.services.interfaces import NotionAPI
from src.notion.infrastructure.workout_repository import NotionWorkoutRepository


class DummyNotion(NotionAPI):
    def __init__(self, results: List[Dict[str, Any]]) -> None:
        self.results = results

    async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"results": self.results}

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - unused in tests
        return {"id": "dummy"}

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - unused in tests
        return {"id": page_id}


settings = Settings(
    api_key="key",
    notion_secret="secret",
    notion_database_id="db",
    notion_workout_database_id="workout-db123",
    notion_athlete_profile_database_id="profile-db123",
    strava_verify_token="verify-token",
    wbsapi_url="https://wbs.example.com",
    upstash_redis_rest_url="https://redis.example.com",
    upstash_redis_rest_token="token",
    withings_client_id="client-id",
    withings_client_secret="client-secret",
    strava_client_id="strava-client-id",
    strava_client_secret="strava-client-secret",
)


def _notion_number(value: float | None) -> Dict[str, Any]:
    return {"number": value}


def _notion_rich_text(content: str | None) -> Dict[str, Any]:
    if content is None:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": content}}]}


def _notion_title(content: str) -> Dict[str, Any]:
    return {"title": [{"text": {"content": content}}]}


@pytest.mark.asyncio
async def test_fetch_workouts_includes_minimal_entries() -> None:
    notion = DummyNotion(
        [
            {
                "properties": {
                    "Name": _notion_title("Outdoor Run"),
                    "Date": {"date": {"start": "2025-10-08"}},
                    "Duration [s]": _notion_number(3600),
                    "Distance [m]": _notion_number(10000),
                    "Elevation [m]": _notion_number(150),
                    "Type": _notion_rich_text("Run"),
                }
            },
            {
                "properties": {
                    "Name": _notion_title("PT in gym"),
                    "Date": {"date": {"start": "2025-10-09"}},
                    "Duration [s]": _notion_number(None),
                    "Distance [m]": _notion_number(None),
                    "Elevation [m]": _notion_number(None),
                    "Type": _notion_rich_text(None),
                    "Notes": _notion_rich_text("Inclined walk warmup."),
                }
            },
        ]
    )

    repository = NotionWorkoutRepository(settings=settings, client=notion)
    workouts = await repository.list_recent_workouts(7)

    names = [w.name for w in workouts]
    assert "Outdoor Run" in names
    assert "PT in gym" in names
