import os
import sys
from pathlib import Path
import pytest
import httpx
import json

# Set environment variables before importing the app
os.environ["API_KEY"] = "test-key"
os.environ["LLM_Update"] = "notion-secret"
os.environ["NOTION_DATABASE_ID"] = "db123"

# Ensure the src directory is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main
app = main.app


@pytest.mark.asyncio
async def test_auth_missing_key():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_wrong_key():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi", headers={"x-api-key": "wrong"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_correct_key():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi", headers={"x-api-key": "test-key"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_log_nutrition_success(respx_mock):
    notion_route = respx_mock.post("https://api.notion.com/v1/pages").mock(
        return_value=httpx.Response(200, json={"id": "page123"})
    )
    payload = {
        "food_item": "Apple",
        "date": "2023-01-01",
        "calories": 95,
        "protein_g": 0.5,
        "carbs_g": 25,
        "fat_g": 0.3,
        "meal_type": "Snack",
        "notes": "Fresh",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/",
            json=payload,
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert notion_route.called
    sent_json = json.loads(notion_route.calls[0].request.content)
    assert sent_json["parent"]["database_id"] == "db123"
    properties = sent_json["properties"]
    assert properties["Food Item"]["title"][0]["text"]["content"] == "Apple"
    assert properties["Calories"]["number"] == 95
    assert properties["Protein (g)"]["number"] == 0.5


@pytest.mark.asyncio
async def test_log_nutrition_error(respx_mock):
    respx_mock.post("https://api.notion.com/v1/pages").mock(
        return_value=httpx.Response(500, text="Server Error")
    )
    payload = {
        "food_item": "Apple",
        "date": "2023-01-01",
        "calories": 95,
        "protein_g": 0.5,
        "carbs_g": 25,
        "fat_g": 0.3,
        "meal_type": "Snack",
        "notes": "Fresh",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/",
            json=payload,
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_get_foods_by_date(respx_mock):
    notion_url = "https://api.notion.com/v1/databases/db123/query"
    valid_page = {
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
    malformed_page = {"properties": {}}
    respx_mock.post(notion_url).mock(
        return_value=httpx.Response(
            200, json={"results": [valid_page, malformed_page]}
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/foods",
            params={"date": "2023-01-01"},
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["food_item"] == "Apple"


@pytest.mark.asyncio
async def test_get_foods_range(respx_mock):
    notion_url = "https://api.notion.com/v1/databases/db123/query"
    respx_mock.post(notion_url).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/foods-range",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200
    request_json = json.loads(respx_mock.calls[0].request.content)
    assert request_json["filter"]["and"][0]["date"]["on_or_after"] == "2023-01-01"
    assert request_json["filter"]["and"][1]["date"]["on_or_before"] == "2023-01-02"


@pytest.mark.asyncio
async def test_openapi_schema():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/openapi", headers={"x-api-key": "test-key"}
        )
    assert response.status_code == 200
    schema = response.json()
    assert schema["servers"][0]["url"] == "https://notionuploader-groa.onrender.com"
    assert (
        schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"]
        == "x-api-key"
    )
