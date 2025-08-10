import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx
import json
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
