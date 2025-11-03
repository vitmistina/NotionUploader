import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.settings import Settings
from src.services.interfaces import NotionAPI
from src.notion.infrastructure.workout_repository import NotionWorkoutRepository


class DummyNotion(NotionAPI):
    def __init__(
        self,
        results: List[Dict[str, Any]],
        *,
        profile_result: Dict[str, Any] | None = None,
    ) -> None:
        self.results = results
        self.pages = {item.get("id", f"page-{idx}"): item for idx, item in enumerate(results)}
        self.updated: List[Tuple[str, Dict[str, Any]]] = []
        self.profile_result = profile_result

    async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if database_id == settings.notion_athlete_profile_database_id and self.profile_result:
            return {"results": [self.profile_result]}
        return {"results": self.results}

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - unused in tests
        return {"id": "dummy"}

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - unused in tests
        self.updated.append((page_id, payload))
        if page_id in self.pages:
            self.pages[page_id].setdefault("properties", {}).update(payload.get("properties", {}))
        return {"id": page_id}

    async def retrieve(self, page_id: str) -> Dict[str, Any]:
        return self.pages.get(page_id, {"id": page_id, "properties": {}})


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
    profile = {
        "properties": {
            "FTP Watts": {"number": None},
            "Weight Kg": {"number": None},
            "Max HR": {"number": 190},
        }
    }

    notion = DummyNotion(
        [
            {
                "id": "page-1",
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
                "id": "page-2",
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
        ],
        profile_result=profile,
    )

    repository = NotionWorkoutRepository(settings=settings, client=notion)
    workouts = await repository.list_recent_workouts(7)

    names = [w.name for w in workouts]
    assert "Outdoor Run" in names
    assert "PT in gym" in names
    assert {w.page_id for w in workouts} == {"page-1", "page-2"}


@pytest.mark.asyncio
async def test_list_recent_workouts_backfills_metrics() -> None:
    profile = {
        "properties": {
            "FTP Watts": {"number": None},
            "Weight Kg": {"number": None},
            "Max HR": {"number": 188},
        }
    }

    notion = DummyNotion(
        [
            {
                "id": "page-backfill",
                "properties": {
                    "Name": _notion_title("Gym Session"),
                    "Date": {"date": {"start": "2025-10-10"}},
                    "Duration [s]": _notion_number(2700),
                    "Distance [m]": _notion_number(0),
                    "Elevation [m]": _notion_number(0),
                    "Type": _notion_rich_text(None),
                    "Average Heartrate": _notion_number(140),
                    "Max Heartrate": _notion_number(165),
                    "TSS": _notion_number(None),
                    "IF": _notion_number(None),
                },
            }
        ],
        profile_result=profile,
    )

    repository = NotionWorkoutRepository(settings=settings, client=notion)
    workouts = await repository.list_recent_workouts(7)

    assert workouts[0].type == "Gym"
    assert workouts[0].tss is not None
    assert workouts[0].intensity_factor is not None
    assert workouts[0].page_id == "page-backfill"


@pytest.mark.asyncio
async def test_fill_missing_metrics_updates_notion() -> None:
    profile = {
        "properties": {
            "FTP Watts": {"number": None},
            "Weight Kg": {"number": None},
            "Max HR": {"number": 185},
        }
    }

    notion = DummyNotion(
        [
            {
                "id": "page-fill",
                "properties": {
                    "Name": _notion_title("Gym Session"),
                    "Date": {"date": {"start": "2025-10-10"}},
                    "Duration [s]": _notion_number(3600),
                    "Distance [m]": _notion_number(0),
                    "Elevation [m]": _notion_number(0),
                    "Type": _notion_rich_text(None),
                    "Average Heartrate": _notion_number(150),
                    "Max Heartrate": _notion_number(175),
                    "TSS": _notion_number(None),
                    "IF": _notion_number(None),
                },
            }
        ],
        profile_result=profile,
    )

    repository = NotionWorkoutRepository(settings=settings, client=notion)
    updated = await repository.fill_missing_metrics("page-fill")

    assert updated is not None
    assert updated.page_id == "page-fill"
    assert updated.tss is not None
    assert updated.intensity_factor is not None
    assert notion.updated, "Expected update call to be recorded"
    page_id, payload = notion.updated[-1]
    assert page_id == "page-fill"
    props = payload["properties"]
    assert "TSS" in props and "IF" in props and "Type" in props
