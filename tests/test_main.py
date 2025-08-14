import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
import json
import hmac
import hashlib
import pytest
import respx
from fastapi import FastAPI
from openapi_spec_validator import validate

# Ensure the repository root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import main
from src.services.redis import get_redis
from src.services.notion import NotionClient
from src.settings import Settings, get_settings

test_settings = Settings(
    api_key="test-key",
    notion_secret="notion-secret",
    notion_database_id="db123",
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

app: FastAPI = main.app
app.dependency_overrides[get_settings] = lambda: test_settings


class DummyRedis:
    def __init__(self) -> None:
        self.store: Dict[str, str] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:  # pragma: no cover - expiration unused
        self.store[key] = value


app.dependency_overrides[get_redis] = DummyRedis

test_notion_client = NotionClient(settings=test_settings)


@pytest.mark.asyncio
async def test_auth_missing_key() -> None:
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get("/v2/api-schema")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_wrong_key() -> None:
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/api-schema", headers={"x-api-key": "wrong"}
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_correct_key() -> None:
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/api-schema", headers={"x-api-key": "test-key"}
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_log_nutrition_success(respx_mock: respx.MockRouter) -> None:
    notion_route: respx.Route = respx_mock.post(
        "https://api.notion.com/v1/pages"
    ).mock(return_value=httpx.Response(200, json={"id": "page123"}))
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
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.post(
            "/v2/nutrition-entries",
            json=payload,
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 201
    assert response.json() == {"status": "success"}
    assert notion_route.called
    sent_json: Dict[str, Any] = json.loads(notion_route.calls[0].request.content)
    assert sent_json["parent"]["database_id"] == "db123"
    properties: Dict[str, Any] = sent_json["properties"]
    assert properties["Food Item"]["title"][0]["text"]["content"] == "Apple"
    assert properties["Calories"]["number"] == 95
    assert properties["Protein (g)"]["number"] == 0.5


@pytest.mark.asyncio
async def test_log_nutrition_error(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("https://api.notion.com/v1/pages").mock(
        return_value=httpx.Response(500, text="Server Error")
    )
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
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.post(
            "/v2/nutrition-entries",
            json=payload,
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_get_foods_by_date(respx_mock: respx.MockRouter) -> None:
    notion_url: str = "https://api.notion.com/v1/databases/db123/query"
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
    respx_mock.post(notion_url).mock(
        return_value=httpx.Response(
            200, json={"results": [valid_page, malformed_page]}
        )
    )
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/nutrition-entries/daily/2023-01-01",
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200
    data: Dict[str, Any] = response.json()
    assert "local_time" in data
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert "part_of_day" in data
    entries: List[Dict[str, Any]] = data["entries"]
    assert len(entries) == 1
    assert entries[0]["food_item"] == "Apple"


@pytest.mark.asyncio
async def test_get_foods_range(respx_mock: respx.MockRouter) -> None:
    notion_url: str = "https://api.notion.com/v1/databases/db123/query"
    page1: Dict[str, Any] = {
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
    page2: Dict[str, Any] = {
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
    page3: Dict[str, Any] = {
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
    respx_mock.post(notion_url).mock(
        return_value=httpx.Response(200, json={"results": [page1, page2, page3]})
    )
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/nutrition-entries/period",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200
    data: Dict[str, Any] = response.json()
    assert "local_time" in data
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert "part_of_day" in data
    days: List[Dict[str, Any]] = data["nutrition"]
    assert len(days) == 2
    day1: Dict[str, Any] = days[0]
    assert day1["date"] == "2023-01-01"
    assert day1["calories"] == 300
    assert day1["protein_g"] == 30
    assert len(day1["entries"]) == 2
    day2: Dict[str, Any] = days[1]
    assert day2["date"] == "2023-01-02"
    assert day2["calories"] == 300
    assert len(day2["entries"]) == 1
    request_json: Dict[str, Any] = json.loads(respx_mock.calls[0].request.content)
    assert request_json["filter"]["and"][0]["date"]["on_or_after"] == "2023-01-01"
    assert request_json["filter"]["and"][1]["date"]["on_or_before"] == "2023-01-02"


@pytest.mark.asyncio
async def test_get_foods_by_date_timeout(respx_mock: respx.MockRouter) -> None:
    notion_url: str = "https://api.notion.com/v1/databases/db123/query"
    respx_mock.post(notion_url).mock(side_effect=httpx.ReadTimeout("timeout"))
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/nutrition-entries/daily/2023-01-01",
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 504


@pytest.mark.asyncio
async def test_openapi_schema() -> None:
    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/api-schema", headers={"x-api-key": "test-key"}
        )
    assert response.status_code == 200
    schema: Dict[str, Any] = response.json()
    validate(schema)
    assert (
        schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"]
        == "x-api-key"
    )
    for path_item in schema["paths"].values():
        path: Dict[str, Any] = path_item
        for operation in path.values():
            op: Any = operation
            if isinstance(op, dict) and "parameters" in op:
                assert all(p["name"] != "x-api-key" for p in op["parameters"])


@pytest.mark.asyncio
async def test_strava_webhook_verification() -> None:
    transport = httpx.ASGITransport(app=app)
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "abc",
        "hub.verify_token": "verify-token",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/strava-webhook", params=params)
    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc"}


@pytest.mark.asyncio
async def test_strava_webhook_event(monkeypatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_process(
        activity_id: int,
        redis: DummyRedis,
        settings: Settings,
        client: NotionClient,
    ) -> None:
        called["id"] = activity_id

    from src import strava_webhook as webhook

    monkeypatch.setattr(webhook, "process_activity", fake_process)

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
        b"strava-client-secret", body, hashlib.sha256
    ).hexdigest()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/strava-webhook", content=body, headers={"X-Strava-Signature": signature}
        )
    assert response.status_code == 200
    assert called["id"] == 42


@pytest.mark.asyncio
async def test_strava_webhook_event_update(monkeypatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_process(
        activity_id: int,
        redis: DummyRedis,
        settings: Settings,
        client: NotionClient,
    ) -> None:
        called["id"] = activity_id

    from src import strava_webhook as webhook

    monkeypatch.setattr(webhook, "process_activity", fake_process)

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
        b"strava-client-secret", body, hashlib.sha256
    ).hexdigest()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/strava-webhook", content=body, headers={"X-Strava-Signature": signature}
        )
    assert response.status_code == 200
    assert called["id"] == 43


@pytest.mark.asyncio
async def test_manual_strava_processing(monkeypatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_process(
        activity_id: int,
        redis: DummyRedis,
        settings: Settings,
        client: NotionClient,
    ) -> None:
        called["id"] = activity_id

    from src.routes import strava as strava_routes

    monkeypatch.setattr(strava_routes, "process_activity", fake_process)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v2/strava-activity/99", headers={"x-api-key": "test-key"}
        )
    assert response.status_code == 200
    assert called["id"] == 99


@pytest.mark.asyncio
async def test_get_workout_logs(respx_mock: respx.MockRouter) -> None:
    notion_url = "https://api.notion.com/v1/databases/workout-db123/query"
    page = {
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
    respx_mock.post(notion_url).mock(return_value=httpx.Response(200, json={"results": [page]}))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/v2/workout-logs", headers={"x-api-key": "test-key"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "Run"
    assert data[0]["hr_drift_percent"] == 5.0
    assert data[0]["tss"] == 50.0
    assert data[0]["intensity_factor"] == 0.85
    assert data[0]["notes"] == "Great ride"


@pytest.mark.asyncio
async def test_process_activity_uses_laps_and_computes_metrics(monkeypatch) -> None:
    from src import strava_activity as sa

    async def fake_fetch_activity(activity_id: int, redis: DummyRedis, settings: Settings) -> Dict[str, Any]:
        return {
            "splits_metric": [
                {"average_heartrate": 100, "moving_time": 60},
                {"average_heartrate": 100, "moving_time": 60},
            ],
            "laps": [
                {
                    "average_heartrate": 190,
                    "moving_time": 60,
                    "max_heartrate": 190,
                },
                {
                    "average_heartrate": 190,
                    "moving_time": 60,
                    "max_heartrate": 190,
                },
                {
                    "average_heartrate": 190,
                    "moving_time": 60,
                    "max_heartrate": 190,
                },
            ],
            "weighted_average_watts": 210,
            "moving_time": 180,
            "description": "desc",
        }

    async def fake_fetch_profile(
        settings: Settings, client: NotionClient
    ) -> Dict[str, Any]:
        return {"ftp": 200, "max_hr": 190}

    called: Dict[str, Any] = {}

    async def fake_save(
        detail: Dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2: float,
        *,
        tss: Optional[float] = None,
        intensity_factor: Optional[float] = None,
        settings: Settings,
        client: NotionClient,
    ) -> None:
        called["vo2"] = vo2
        called["tss"] = tss
        called["if"] = intensity_factor
        called["notes"] = detail.get("description")

    monkeypatch.setattr(sa, "fetch_activity", fake_fetch_activity)
    monkeypatch.setattr(sa, "fetch_latest_athlete_profile", fake_fetch_profile)
    monkeypatch.setattr(sa, "save_workout_to_notion", fake_save)

    await sa.process_activity(1, DummyRedis(), test_settings, test_notion_client)

    assert called["vo2"] == pytest.approx(3.0)
    assert called["if"] == pytest.approx(1.05)
    assert called["tss"] == pytest.approx(5.5125)
    assert called["notes"] == "desc"


@pytest.mark.asyncio
async def test_save_workout_to_notion_updates_existing(respx_mock: respx.MockRouter) -> None:
    from src import workout_notion as wn

    detail = {"id": 123, "name": "Ride"}
    query_url = "https://api.notion.com/v1/databases/workout-db123/query"
    respx_mock.post(query_url).mock(
        return_value=httpx.Response(200, json={"results": [{"id": "page123"}]})
    )
    patch_route = respx_mock.patch("https://api.notion.com/v1/pages/page123").mock(
        return_value=httpx.Response(200, json={"id": "page123"})
    )

    await wn.save_workout_to_notion(
        detail, "", 0.0, 0.0, settings=test_settings, client=test_notion_client
    )

    assert patch_route.called


@pytest.mark.asyncio
async def test_save_workout_to_notion_inserts_when_missing(respx_mock: respx.MockRouter) -> None:
    from src import workout_notion as wn

    detail = {"id": 321, "name": "Ride"}
    query_url = "https://api.notion.com/v1/databases/workout-db123/query"
    respx_mock.post(query_url).mock(return_value=httpx.Response(200, json={"results": []}))
    post_route = respx_mock.post("https://api.notion.com/v1/pages").mock(
        return_value=httpx.Response(200, json={"id": "page321"})
    )

    await wn.save_workout_to_notion(
        detail, "", 0.0, 0.0, settings=test_settings, client=test_notion_client
    )

    assert post_route.called


@pytest.mark.asyncio
async def test_complex_advice_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_nutrition(
        start: str, end: str, settings: Settings, client: NotionClient
    ) -> List[Dict[str, Any]]:
        return [
            {
                "date": "2023-01-01",
                "calories": 100,
                "protein_g": 10.0,
                "carbs_g": 20.0,
                "fat_g": 5.0,
                "entries": [],
            }
        ]

    async def fake_metrics(days: int, redis: DummyRedis, settings: Settings) -> List[Dict[str, Any]]:
        return [
            {
                "measurement_time": "2023-01-01T00:00:00",
                "weight_kg": 70.0,
                "fat_mass_kg": 10.0,
                "muscle_mass_kg": 30.0,
                "bone_mass_kg": 5.0,
                "hydration_kg": 40.0,
                "fat_free_mass_kg": 60.0,
                "body_fat_percent": 14.0,
                "device_name": "Scale",
            }
        ]

    async def fake_workouts(
        days: int, settings: Settings, client: NotionClient
    ) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Run",
                "date": "2023-01-01",
                "duration_s": 3600,
                "distance_m": 10000.0,
                "elevation_m": 100.0,
                "type": "Run",
            }
        ]

    async def fake_athlete(
        settings: Settings, client: NotionClient
    ) -> Dict[str, Any]:
        return {"ftp": 250.0, "weight": 70.0, "max_hr": 190.0}

    from src.routes import workouts as workouts_routes

    monkeypatch.setattr(workouts_routes, "get_daily_nutrition_summaries", fake_nutrition)
    monkeypatch.setattr(workouts_routes, "get_measurements", fake_metrics)
    monkeypatch.setattr(workouts_routes, "fetch_workouts_from_notion", fake_workouts)
    monkeypatch.setattr(workouts_routes, "fetch_latest_athlete_profile", fake_athlete)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response: httpx.Response = await client.get(
            "/v2/complex-advice?days=1&timezone=UTC",
            headers={"x-api-key": "test-key"},
        )

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert "part_of_day" in data
    assert "nutrition" in data
    assert "metrics" in data
    assert "workouts" in data
    assert "athlete_metrics" in data
