"""Workout API integration tests."""

from __future__ import annotations

import httpx
import pytest

from src.application.workouts import WorkoutNotFoundError
from src.platform.wiring import get_sync_workout_metrics_use_case
from src.settings import Settings
from tests.conftest import NotionAPIStub

pytestmark = pytest.mark.asyncio


async def test_get_workout_logs(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Returns workouts enriched with athlete profile metrics."""

    workout_page = {
        "id": "workout-page",
        "properties": {
            "Name": {"title": [{"text": {"content": "Run"}}]},
            "Date": {"date": {"start": "2023-01-01"}},
            "Duration [s]": {"number": 3600},
            "Distance [m]": {"number": 10000},
            "Elevation [m]": {"number": 50},
            "Type": {"select": {"name": "Run"}},
            "Average Cadence": {"number": 80},
            "Average Watts": {"number": 200},
            "Weighted Average Watts": {"number": 210},
            "Kilojoules": {"number": 500},
            "Kcal": {"number": 480},
            "Average Heartrate": {"number": 150},
            "Max Heartrate": {"number": 180},
            "HR drift [%]": {"number": 5.0},
            "VO2 MAX [min]": {"number": 10.0},
            "TSS": {"number": 50.0},
            "IF": {"number": 0.85},
            "Notes": {"rich_text": [{"text": {"content": "Great ride"}}]},
        }
    }
    profile_page = {
        "properties": {
            "FTP Watts": {"number": 250},
            "Weight Kg": {"number": 70},
            "Max HR": {"number": 190},
        }
    }
    notion_api_stub.expect_query(
        database_id=settings.notion_workout_database_id,
        returns={"results": [workout_page]},
    )
    notion_api_stub.expect_query(
        database_id=settings.notion_athlete_profile_database_id,
        returns={"results": [profile_page]},
    )

    response = await client.get(
        "/v2/workout-logs",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    data = response.json()

    assert data[0]["page_id"] == "workout-page"
    assert data[0]["name"] == "Run"
    assert data[0]["hr_drift_percent"] == 5.0
    assert data[0]["tss"] == 50.0
    assert data[0]["intensity_factor"] == 0.85
    assert data[0]["notes"] == "Great ride"


class _SyncUseCaseStub:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.calls: list[str] = []

    async def __call__(self, page_id: str):  # type: ignore[override]
        self.calls.append(page_id)
        if self.raises:
            raise WorkoutNotFoundError("missing")
        return {"status": "updated"}


async def test_sync_workout_metrics_not_found(
    client: httpx.AsyncClient, app: "FastAPI", settings: Settings
) -> None:
    """Translates ``WorkoutNotFoundError`` to a 404 response."""

    use_case = _SyncUseCaseStub(raises=True)
    app.dependency_overrides[get_sync_workout_metrics_use_case] = lambda: use_case

    response = await client.post(
        "/v2/workout-logs/page123/sync",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 404
    assert use_case.calls == ["page123"]

    app.dependency_overrides.pop(get_sync_workout_metrics_use_case, None)
