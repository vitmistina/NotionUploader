"""Nutrition API integration tests."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest
from fastapi import HTTPException

from src.settings import Settings
from tests.api.helpers import (
    assert_nutrition_entry,
    build_nutrition_create_payload,
    make_nutrition_page,
    make_nutrition_payload,
)
from tests.conftest import NotionAPIStub

pytestmark = pytest.mark.asyncio


async def test_log_nutrition_success(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Creates a Notion page when provided a valid nutrition payload."""

    payload = make_nutrition_payload(meal_type="During-workout")
    expected_create = build_nutrition_create_payload(settings, payload)
    notion_api_stub.expect_create(payload=expected_create, returns={"id": "page123"})

    response = await client.post(
        "/v2/nutrition-entries",
        json=payload,
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}


async def test_log_nutrition_error(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Propagates repository errors when creating a nutrition entry fails."""

    payload = make_nutrition_payload()
    notion_api_stub.expect_create(
        payload=build_nutrition_create_payload(settings, payload),
        raises=HTTPException(status_code=500, detail={"error": "boom"}),
    )

    response = await client.post(
        "/v2/nutrition-entries",
        json=payload,
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 500


async def test_get_foods_by_date(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Returns a daily nutrition summary with parsed entries."""

    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        returns={
            "results": [
                make_nutrition_page(food_item="Apple", meal_type="Snack"),
                {"properties": {}},
            ]
        },
    )

    response = await client.get(
        "/v2/nutrition-entries/daily/2023-01-01",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    data = response.json()

    assert "local_time" in data
    assert datetime.fromisoformat(data["local_time"]).tzinfo is not None
    assert data["days"][0]["daily_calories_sum"] == 95

    entries = data["days"][0]["entries"]
    assert len(entries) == 1
    assert_nutrition_entry(
        entries[0],
        page_id="page-apple",
        food_item="Apple",
        calories=95,
        protein_g=0.5,
        carbs_g=25,
        fat_g=0.3,
        meal_type="Snack",
    )


async def test_get_foods_range(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Aggregates paginated nutrition entries into daily totals."""

    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        payload={
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": "2023-01-01"}},
                    {"property": "Date", "date": {"on_or_before": "2023-01-02"}},
                ]
            }
        },
        returns={
            "results": [
                make_nutrition_page(
                    food_item="A", calories=100, protein_g=10, carbs_g=20, fat_g=5
                )
            ],
            "has_more": True,
            "next_cursor": "cursor1",
        },
    )
    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        payload={
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": "2023-01-01"}},
                    {"property": "Date", "date": {"on_or_before": "2023-01-02"}},
                ]
            },
            "start_cursor": "cursor1",
        },
        returns={
            "results": [
                make_nutrition_page(
                    food_item="B",
                    calories=200,
                    protein_g=20,
                    carbs_g=40,
                    fat_g=10,
                ),
                make_nutrition_page(
                    food_item="C",
                    date="2023-01-02",
                    calories=300,
                    protein_g=30,
                    carbs_g=60,
                    fat_g=15,
                ),
            ],
            "has_more": False,
        },
    )

    response = await client.get(
        "/v2/nutrition-entries/period",
        params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["days"][0]["daily_calories_sum"] == 300
    assert payload["days"][1]["daily_calories_sum"] == 300
    assert notion_api_stub.query_history()[1].get("start_cursor") == "cursor1"


async def test_get_foods_by_date_timeout(
    client: httpx.AsyncClient, notion_api_stub: NotionAPIStub, settings: Settings
) -> None:
    """Surfaces repository timeouts when listing daily entries fails."""

    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        raises=HTTPException(status_code=504, detail={"error": "timeout"}),
    )

    response = await client.get(
        "/v2/nutrition-entries/daily/2023-01-01",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 504
