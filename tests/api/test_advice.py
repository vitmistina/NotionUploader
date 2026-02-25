"""Summary advice API integration tests."""

from __future__ import annotations

import httpx
import pytest

from platform.config import Settings
from tests.conftest import NotionAPIStub, WithingsPortFake

pytestmark = pytest.mark.asyncio


async def test_summary_advice_returns_friendly_error_on_withings_connection_issue(
    client: httpx.AsyncClient,
    settings: Settings,
    withings_port_fake: WithingsPortFake,
) -> None:
    """Returns a friendly 503 payload when an upstream dependency is unreachable."""

    withings_port_fake.expect_fetch_measurements(
        days=7,
        raises=httpx.ConnectError(
            "[Errno -2] Name or service not known",
            request=httpx.Request("GET", "https://redis.example.com/get/withings_access_token"),
        ),
    )

    response = await client.get(
        "/v2/summary-advice",
        params={"days": 7, "timezone": "Europe/Prague"},
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "UPSTREAM_CONNECTION_FAILED",
        "message": (
            "Could not connect to an upstream dependency service. "
            "Please try again shortly."
        ),
        "upstream_host": "redis.example.com",
    }


async def test_nutrition_route_also_uses_friendly_connection_error_response(
    client: httpx.AsyncClient,
    notion_api_stub: NotionAPIStub,
    settings: Settings,
) -> None:
    """Applies the same user-friendly response across routes dependent on external APIs."""

    notion_api_stub.expect_query(
        database_id=settings.notion_database_id,
        raises=httpx.ConnectError(
            "connection failed",
            request=httpx.Request("POST", "https://api.notion.com/v1/databases/notion-db/query"),
        ),
    )

    response = await client.get(
        "/v2/nutrition-entries/daily/2023-01-01",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "UPSTREAM_CONNECTION_FAILED",
        "message": (
            "Could not connect to an upstream dependency service. "
            "Please try again shortly."
        ),
        "upstream_host": "api.notion.com",
    }


async def test_summary_advice_success_when_upstreams_are_available(
    client: httpx.AsyncClient,
    settings: Settings,
) -> None:
    """Returns summary payload when dependencies respond normally."""

    response = await client.get(
        "/v2/summary-advice",
        params={"days": 7, "timezone": "Europe/Prague"},
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"] == []
    assert payload["nutrition"] == []
    assert payload["workouts"] == []
