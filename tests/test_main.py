import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import json
import hmac
import hashlib
import pytest
import respx
from fastapi import FastAPI
from openapi_spec_validator import validate

# Set environment variables before importing the app
os.environ["API_KEY"] = "test-key"
os.environ["LLM_Update"] = "notion-secret"
os.environ["NOTION_DATABASE_ID"] = "db123"
os.environ["WBSAPI_URL"] = "https://wbs.example.com"
os.environ["UPSTASH_REDIS_REST_URL"] = "https://redis.example.com"
os.environ["UPSTASH_REDIS_REST_TOKEN"] = "token"
os.environ["WITHINGS_CLIENT_ID"] = "client-id"
os.environ["WITHINGS_CLIENT_SECRET"] = "client-secret"
os.environ["CLIENT_ID"] = "oauth-client-id"
os.environ["CUSTOMER_SECRET"] = "oauth-secret"
os.environ["STRAVA_CLIENT_ID"] = "strava-client-id"
os.environ["STRAVA_CLIENT_SECRET"] = "strava-client-secret"
os.environ["NOTION_WORKOUT_DATABASE_ID"] = "workout-db123"
os.environ["NOTION_ATHLETE_PROFILE_DATABASE_ID"] = "profile-db123"
os.environ["STRAVA_VERIFY_TOKEN"] = "verify-token"

# Ensure the repository root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import main

app: FastAPI = main.app


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
    data: List[Dict[str, Any]] = response.json()
    assert len(data) == 1
    assert data[0]["food_item"] == "Apple"


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
    data: List[Dict[str, Any]] = response.json()
    assert len(data) == 2
    day1: Dict[str, Any] = data[0]
    assert day1["date"] == "2023-01-01"
    assert day1["calories"] == 300
    assert day1["protein_g"] == 30
    assert len(day1["entries"]) == 2
    day2: Dict[str, Any] = data[1]
    assert day2["date"] == "2023-01-02"
    assert day2["calories"] == 300
    assert len(day2["entries"]) == 1
    request_json: Dict[str, Any] = json.loads(respx_mock.calls[0].request.content)
    assert request_json["filter"]["and"][0]["date"]["on_or_after"] == "2023-01-01"
    assert request_json["filter"]["and"][1]["date"]["on_or_before"] == "2023-01-02"





class FakeRedis:
    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_get_workouts(respx_mock: respx.MockRouter) -> None:
    from src import strava as strava_module

    fake = FakeRedis()
    fake.set("strava_refresh_token", "refresh123")
    strava_module.redis = fake

    activity: Dict[str, Any] = {
        "id": 1,
        "name": "Morning Ride",
        "distance": 25000.0,
        "moving_time": 3600,
        "elapsed_time": 3700,
        "total_elevation_gain": 500.0,
        "type": "Ride",
        "start_date": "2023-01-01T10:00:00Z",
        "average_speed": 6.9,
        "max_speed": 12.3,
        "average_watts": 210.0,
        "kilojoules": 756.0,
        "device_watts": True,
        "average_heartrate": 150.0,
        "max_heartrate": 190.0,
    }

    respx_mock.get("https://www.strava.com/api/v3/athlete/activities").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json=[activity]),
        ]
    )
    respx_mock.post("https://www.strava.com/api/v3/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "newtoken",
                "refresh_token": "refresh456",
                "expires_in": 3600,
            },
        )
    )

    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v2/workouts", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["kilojoules"] == 756.0
    assert fake.get("strava_access_token") == "newtoken"

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

    async def fake_process(activity_id: int, *, update: bool = False) -> None:
        called["id"] = activity_id
        called["update"] = update

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
    assert called["update"] is False


@pytest.mark.asyncio
async def test_strava_webhook_event_update(monkeypatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_process(activity_id: int, *, update: bool = False) -> None:
        called["id"] = activity_id
        called["update"] = update

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
    assert called["update"] is True


@pytest.mark.asyncio
async def test_manual_strava_processing(monkeypatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_process(activity_id: int) -> None:
        called["id"] = activity_id

    from src import routes as routes_module

    monkeypatch.setattr(routes_module, "process_activity", fake_process)

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

    async def fake_fetch_activity(activity_id: int) -> Dict[str, Any]:
        return {
            "splits_metric": [
                {"average_heartrate": 100, "moving_time": 60},
                {"average_heartrate": 100, "moving_time": 60},
            ],
            "laps": [
                {"average_heartrate": 171, "moving_time": 60},
                {"average_heartrate": 171, "moving_time": 60},
                {"average_heartrate": 171, "moving_time": 60},
            ],
            "weighted_average_watts": 210,
            "moving_time": 180,
            "description": "desc",
        }

    async def fake_fetch_profile() -> Dict[str, Any]:
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
        update: bool = False,
    ) -> None:
        called["vo2"] = vo2
        called["tss"] = tss
        called["if"] = intensity_factor
        called["notes"] = detail.get("description")

    monkeypatch.setattr(sa, "fetch_activity", fake_fetch_activity)
    monkeypatch.setattr(sa, "fetch_latest_athlete_profile", fake_fetch_profile)
    monkeypatch.setattr(sa, "save_workout_to_notion", fake_save)

    await sa.process_activity(1)

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

    await wn.save_workout_to_notion(detail, "", 0.0, 0.0, update=True)

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

    await wn.save_workout_to_notion(detail, "", 0.0, 0.0, update=True)

    assert post_route.called
