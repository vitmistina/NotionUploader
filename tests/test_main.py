from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import pytest
from fastapi import HTTPException
from openapi_spec_validator import validate

from src.models.body import BodyMeasurement
from src.models.workout import WorkoutLog
from src.notion.application.ports import NutritionRepository, WorkoutRepository
from src.notion.infrastructure.nutrition_repository import get_nutrition_repository
from src.notion.infrastructure.workout_repository import (
    NotionWorkoutRepository,
    get_workout_repository,
)
from src.routes import advice as advice_routes
from src.settings import Settings
from tests.conftest import NotionAPIStub, WithingsPortFake

pytestmark = pytest.mark.asyncio


async def test_auth_missing_key(client: httpx.AsyncClient) -> None:
    response = await client.get("/v2/api-schema")
    assert response.status_code == 401


async def test_auth_wrong_key(client: httpx.AsyncClient) -> None:
    response = await client.get("/v2/api-schema", headers={"x-api-key": "wrong"})
    assert response.status_code == 401


async def test_auth_correct_key(client: httpx.AsyncClient, settings: Settings) -> None:
    response = await client.get(
        "/v2/api-schema", headers={"x-api-key": settings.api_key}
    )
    assert response.status_code == 200


async def test_log_nutrition_success(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    notion_api_stub.expect_create(returns={"id": "page123"})

    payload: Dict[str, Any] = {
        "food_item": "Apple",
        "date": "2023-01-01",
        "calories": 95,
        "protein_g": 0.5,
        "carbs_g": 25,
        "fat_g": 0.3,
        "meal_type": "During-workout",
        "notes": "Fresh",
    }

    response = await client.post(
        "/v2/nutrition-entries",
        json=payload,
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}

    created_payload = notion_api_stub.last_create_payload()
    assert created_payload is not None
    assert created_payload["parent"]["database_id"] == settings.notion_database_id
    properties = created_payload["properties"]
    assert properties["Food Item"]["title"][0]["text"]["content"] == "Apple"
    assert properties["Calories"]["number"] == 95
    assert properties["Protein (g)"]["number"] == 0.5


async def test_log_nutrition_error(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    notion_api_stub.expect_create(
        raises=HTTPException(status_code=500, detail={"error": "boom"})
    )

    response = await client.post(
        "/v2/nutrition-entries",
        json={
            "food_item": "Apple",
            "date": "2023-01-01",
            "calories": 95,
            "protein_g": 0.5,
            "carbs_g": 25,
            "fat_g": 0.3,
            "meal_type": "During-workout",
            "notes": "Fresh",
        },
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 500


async def test_get_foods_by_date(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    valid_page: Dict[str, Any] = {
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
    malformed_page: Dict[str, Any] = {"properties": {}}
    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        returns={"results": [valid_page, malformed_page]},
    )

    response = await client.get(
        "/v2/nutrition-entries/daily/2023-01-01",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "local_time" in data
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert "part_of_day" in data
    days = data["days"]
    assert len(days) == 1
    entries = days[0]["entries"]
    assert len(entries) == 1
    assert entries[0]["food_item"] == "Apple"
    assert days[0]["daily_calories_sum"] == 95


async def test_get_foods_range(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    first_page: Dict[str, Any] = {
        "properties": {
            "Food Item": {"title": [{"text": {"content": "A"}}]},
            "Date": {"date": {"start": "2023-01-01"}},
            "Calories": {"number": 100},
            "Protein (g)": {"number": 10},
            "Carbs (g)": {"number": 20},
            "Fat (g)": {"number": 5},
            "Meal Type": {"select": {"name": "Snack"}},
            "Notes": {"rich_text": [{"text": {"content": "note"}}]},
        }
    }
    second_page: Dict[str, Any] = {
        "properties": {
            "Food Item": {"title": [{"text": {"content": "B"}}]},
            "Date": {"date": {"start": "2023-01-01"}},
            "Calories": {"number": 200},
            "Protein (g)": {"number": 20},
            "Carbs (g)": {"number": 40},
            "Fat (g)": {"number": 10},
            "Meal Type": {"select": {"name": "Snack"}},
            "Notes": {"rich_text": [{"text": {"content": "note"}}]},
        }
    }
    third_page: Dict[str, Any] = {
        "properties": {
            "Food Item": {"title": [{"text": {"content": "C"}}]},
            "Date": {"date": {"start": "2023-01-02"}},
            "Calories": {"number": 300},
            "Protein (g)": {"number": 30},
            "Carbs (g)": {"number": 60},
            "Fat (g)": {"number": 15},
            "Meal Type": {"select": {"name": "Snack"}},
            "Notes": {"rich_text": [{"text": {"content": "note"}}]},
        }
    }
    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        returns={
            "results": [first_page],
            "has_more": True,
            "next_cursor": "cursor1",
        },
    )
    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        returns={
            "results": [second_page, third_page],
            "has_more": False,
        },
    )

    response = await client.get(
        "/v2/nutrition-entries/period",
        params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["days"]) == 2
    first_day = data["days"][0]
    second_day = data["days"][1]
    assert first_day["daily_calories_sum"] == 300
    assert second_day["daily_calories_sum"] == 300
    history = notion_api_stub.query_history()
    assert history[1].get("start_cursor") == "cursor1"


async def test_get_foods_by_date_timeout(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        raises=HTTPException(status_code=504, detail={"error": "timeout"}),
    )

    response = await client.get(
        "/v2/nutrition-entries/daily/2023-01-01",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 504


async def test_openapi_schema(client: httpx.AsyncClient, settings: Settings) -> None:
    response = await client.get(
        "/v2/api-schema", headers={"x-api-key": settings.api_key}
    )
    assert response.status_code == 200
    schema = response.json()
    validate(schema)
    assert (
        schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"]
        == "x-api-key"
    )
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "parameters" in operation:
                assert all(p["name"] != "x-api-key" for p in operation["parameters"])


async def test_strava_webhook_verification(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "abc",
        "hub.verify_token": settings.strava_verify_token,
    }

    response = await client.get("/strava-webhook", params=params)

    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc"}


async def test_strava_webhook_event(
    client: httpx.AsyncClient,
    settings: Settings,
    strava_coordinator_spy,
) -> None:
    strava_coordinator_spy.expect_process_activity(activity_id=42)

    payload = {
        "aspect_type": "create",
        "event_time": 1,
        "object_id": 42,
        "object_type": "activity",
        "owner_id": 1,
        "subscription_id": 1,
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.strava_client_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    response = await client.post(
        "/strava-webhook",
        content=body,
        headers={"X-Strava-Signature": signature},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(42)


async def test_strava_webhook_event_update(
    client: httpx.AsyncClient,
    settings: Settings,
    strava_coordinator_spy,
) -> None:
    strava_coordinator_spy.expect_process_activity(activity_id=43)

    payload = {
        "aspect_type": "update",
        "event_time": 1,
        "object_id": 43,
        "object_type": "activity",
        "owner_id": 1,
        "subscription_id": 1,
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.strava_client_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    response = await client.post(
        "/strava-webhook",
        content=body,
        headers={"X-Strava-Signature": signature},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(43)


async def test_manual_strava_processing(
    client: httpx.AsyncClient,
    settings: Settings,
    strava_coordinator_spy,
) -> None:
    strava_coordinator_spy.expect_process_activity(activity_id=99)

    response = await client.post(
        "/v2/strava-activity/99",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(99)


async def test_get_workout_logs(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    workout_page = {
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
        "/v2/workout-logs", headers={"x-api-key": settings.api_key}
    )

    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "Run"
    assert data[0]["hr_drift_percent"] == 5.0
    assert data[0]["tss"] == 50.0
    assert data[0]["intensity_factor"] == 0.85
    assert data[0]["notes"] == "Great ride"


async def test_fill_workout_metrics(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    workout_id = "page-fill"
    retrieve_payload = {
        "id": workout_id,
        "properties": {
            "Name": {"title": [{"text": {"content": "Gym"}}]},
            "Date": {"date": {"start": "2023-01-01"}},
            "Duration [s]": {"number": 3600},
            "Distance [m]": {"number": 0},
            "Elevation [m]": {"number": 0},
            "Type": {"rich_text": []},
            "Average Heartrate": {"number": 150},
            "Max Heartrate": {"number": 175},
            "TSS": {"number": None},
            "IF": {"number": None},
        },
    }
    notion_api_stub.expect_retrieve(page_id=workout_id, returns=retrieve_payload)
    notion_api_stub.expect_update(
        page_id=workout_id,
        returns={"id": workout_id},
    )

    response = await client.post(
        f"/v2/workout-logs/{workout_id}/sync",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "updated"}
    notion_api_stub.assert_last_update(page_id=workout_id)


async def test_manual_workout_validation_error(
    client: httpx.AsyncClient,
    settings: Settings,
    app,
) -> None:
    class ManualRepo(WorkoutRepository):
        async def list_recent_workouts(self, days: int) -> List[WorkoutLog]:  # pragma: no cover
            return []

        async def fetch_latest_athlete_profile(self) -> Dict[str, Any]:  # pragma: no cover
            return {}

        async def save_workout(
            self,
            detail: Dict[str, Any],
            attachment: str,
            hr_drift: float,
            vo2max: float,
            *,
            tss: Optional[float] = None,
            intensity_factor: Optional[float] = None,
        ) -> None:  # pragma: no cover - validation should fail before call
            raise AssertionError("save_workout should not be called")

        async def fill_missing_metrics(self, page_id: str) -> Optional[WorkoutLog]:  # pragma: no cover
            return None

    app.dependency_overrides[get_workout_repository] = lambda: ManualRepo()

    try:
        response = await client.post(
            "/v2/workout-logs/manual",
            headers={"x-api-key": settings.api_key},
            json={
                "name": "Strength Session",
                "start_time": "2025-02-01T10:00:00Z",
                "duration_minutes": 60,
                "average_heartrate": None,
                "max_heartrate": 168,
                "notes": "Superset upper body and core work.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_workout_repository, None)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "average_heartrate"]
    assert "Input should be a valid number" in detail[0]["msg"]


async def test_process_activity_uses_laps_and_computes_metrics(
    settings: Settings,
    notion_api_stub: NotionAPIStub,
) -> None:
    from src.services.interfaces import NotionAPI
    from src.strava import StravaActivityCoordinator

    class FakeStravaClient:
        async def get_activity(self, activity_id: int) -> Dict[str, Any]:
            return {
                "id": activity_id,
                "name": "Ride",
                "splits_metric": [
                    {"average_heartrate": 100, "moving_time": 60},
                    {"average_heartrate": 100, "moving_time": 60},
                ],
                "laps": [
                    {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
                    {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
                    {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
                ],
                "weighted_average_watts": 210,
                "moving_time": 180,
                "description": "desc",
            }

    class FakeNotionClient(NotionAPI):
        def __init__(self) -> None:
            self.created: Dict[str, Any] | None = None

        async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            if database_id == settings.notion_athlete_profile_database_id:
                return {
                    "results": [
                        {
                            "properties": {
                                "FTP Watts": {"number": 200},
                                "Max HR": {"number": 190},
                            }
                        }
                    ]
                }
            return {"results": []}

        async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            self.created = payload
            return {"id": "page"}

        async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
            return {"id": page_id}

        async def retrieve(self, page_id: str) -> Dict[str, Any]:  # pragma: no cover
            return {"id": page_id, "properties": {}}

    notion = FakeNotionClient()
    repository = NotionWorkoutRepository(settings=settings, client=notion)

    coordinator = StravaActivityCoordinator(FakeStravaClient(), repository)

    await coordinator.process_activity(1)

    assert notion.created is not None
    props = notion.created["properties"]
    assert props["VO2 MAX [min]"]["number"] == pytest.approx(3.0)
    assert props["IF"]["number"] == pytest.approx(1.05)
    assert props["TSS"]["number"] == pytest.approx(5.5125)
    assert props["Notes"]["rich_text"][0]["text"]["content"] == "desc"


async def test_save_workout_to_notion_updates_existing(
    settings: Settings, notion_api_stub: NotionAPIStub
) -> None:
    repository = NotionWorkoutRepository(settings=settings, client=notion_api_stub)
    detail = {"id": 123, "name": "Ride"}

    notion_api_stub.expect_query(
        database_id=settings.notion_athlete_profile_database_id,
        returns={"results": []},
    )
    notion_api_stub.expect_query(
        database_id=settings.notion_workout_database_id,
        returns={"results": [{"id": "page123"}]},
    )
    notion_api_stub.expect_update(page_id="page123", returns={"id": "page123"})

    await repository.save_workout(detail, "", 0.0, 0.0)

    notion_api_stub.assert_last_update(page_id="page123")


async def test_save_workout_to_notion_creates_new(
    settings: Settings, notion_api_stub: NotionAPIStub
) -> None:
    repository = NotionWorkoutRepository(settings=settings, client=notion_api_stub)
    detail = {"id": 321, "name": "Ride"}

    notion_api_stub.expect_query(
        database_id=settings.notion_athlete_profile_database_id,
        returns={"results": []},
    )
    notion_api_stub.expect_query(
        database_id=settings.notion_workout_database_id,
        returns={"results": []},
    )
    notion_api_stub.expect_create(returns={"id": "page321"})

    await repository.save_workout(detail, "", 0.0, 0.0)

    notion_api_stub.assert_last_create()


async def test_body_measurements_endpoint(
    client: httpx.AsyncClient,
    settings: Settings,
    withings_port_fake: WithingsPortFake,
) -> None:
    base = datetime(2023, 1, 1)
    withings_port_fake.expect_fetch_measurements(
        days=7,
        returns=[
            BodyMeasurement.model_construct(
                measurement_time=base,
                weight_kg=70.0,
                fat_mass_kg=10.0,
                muscle_mass_kg=30.0,
                bone_mass_kg=5.0,
                hydration_kg=40.0,
                fat_free_mass_kg=60.0,
                body_fat_percent=14.0,
                device_name="Scale",
            ),
            BodyMeasurement.model_construct(
                measurement_time=base + timedelta(days=2),
                weight_kg=72.0,
                fat_mass_kg=11.0,
                muscle_mass_kg=31.0,
                bone_mass_kg=5.0,
                hydration_kg=40.0,
                fat_free_mass_kg=60.0,
                body_fat_percent=15.0,
                device_name="Scale",
            ),
        ],
    )

    response = await client.get(
        "/v2/body-measurements",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "measurements" in payload
    assert "trends" in payload
    trend = payload["trends"]["weight_kg"]
    assert trend["slope"] == pytest.approx(1.0)
    assert trend["intercept"] == pytest.approx(70.0)
    assert trend["r2"] == pytest.approx(1.0)


async def test_complex_advice_endpoint(
    client: httpx.AsyncClient,
    settings: Settings,
    app,
    withings_port_fake: WithingsPortFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_nutrition(
        start: str, end: str, repository: NutritionRepository
    ) -> List[Dict[str, Any]]:
        return [
            {
                "date": "2023-01-01",
                "daily_calories_sum": 100,
                "daily_protein_g_sum": 10.0,
                "daily_carbs_g_sum": 20.0,
                "daily_fat_g_sum": 5.0,
                "entries": [
                    {
                        "food_item": "Food",
                        "date": "2023-01-01",
                        "calories": 100,
                        "protein_g": 10.0,
                        "carbs_g": 20.0,
                        "fat_g": 5.0,
                        "meal_type": "Lunch",
                        "notes": "note",
                    }
                ],
            }
        ]

    class FakeNutritionRepo(NutritionRepository):
        async def create_entry(self, entry: Any) -> None:  # pragma: no cover - unused
            return None

        async def list_entries_on_date(self, date: str) -> List[Any]:  # pragma: no cover - unused
            return []

        async def list_entries_in_range(
            self, start_date: str, end_date: str
        ) -> List[Any]:  # pragma: no cover - unused
            return []

    class FakeWorkoutRepo(WorkoutRepository):
        async def list_recent_workouts(self, days: int) -> List[WorkoutLog]:
            return [
                WorkoutLog(
                    name="Run",
                    date="2023-01-01",
                    duration_s=3600,
                    distance_m=10000.0,
                    elevation_m=100.0,
                    type="Run",
                )
            ]

        async def fetch_latest_athlete_profile(self) -> Dict[str, Any]:
            return {"ftp": 250.0, "weight": 70.0, "max_hr": 190.0}

        async def save_workout(
            self,
            detail: Dict[str, Any],
            attachment: str,
            hr_drift: float,
            vo2max: float,
            *,
            tss: Optional[float] = None,
            intensity_factor: Optional[float] = None,
        ) -> None:  # pragma: no cover - unused
            return None

        async def fill_missing_metrics(self, page_id: str) -> Optional[WorkoutLog]:  # pragma: no cover - unused
            return None

    monkeypatch.setattr(
        advice_routes,
        "get_daily_nutrition_summaries",
        fake_nutrition,
    )

    app.dependency_overrides[get_nutrition_repository] = lambda: FakeNutritionRepo()
    app.dependency_overrides[get_workout_repository] = lambda: FakeWorkoutRepo()

    base = datetime(2023, 1, 1)
    withings_port_fake.expect_fetch_measurements(
        days=1,
        returns=[
            BodyMeasurement.model_construct(
                measurement_time=base,
                weight_kg=70.0,
                fat_mass_kg=10.0,
                muscle_mass_kg=30.0,
                bone_mass_kg=5.0,
                hydration_kg=40.0,
                fat_free_mass_kg=60.0,
                body_fat_percent=14.0,
                device_name="Scale",
            ),
            BodyMeasurement.model_construct(
                measurement_time=base + timedelta(days=2),
                weight_kg=72.0,
                fat_mass_kg=11.0,
                muscle_mass_kg=31.0,
                bone_mass_kg=5.0,
                hydration_kg=40.0,
                fat_free_mass_kg=60.0,
                body_fat_percent=15.0,
                device_name="Scale",
            ),
        ],
    )

    try:
        response = await client.get(
            "/v2/summary-advice?days=1&timezone=UTC",
            headers={"x-api-key": settings.api_key},
        )
    finally:
        app.dependency_overrides.pop(get_nutrition_repository, None)
        app.dependency_overrides.pop(get_workout_repository, None)

    assert response.status_code == 200
    data = response.json()
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert "nutrition" in data
    assert data["nutrition"][0]["entries"][0]["food_item"] == "Food"
    assert "metric_trends" in data
    trend = data["metric_trends"]["weight_kg"]
    assert trend["slope"] == pytest.approx(1.0)
    assert "workouts" in data
    assert "athlete_metrics" in data
