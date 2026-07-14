from datetime import date

import httpx
import pytest

from platform.config import Settings
from src.intervals_icu.application import (
    IntervalsApiError,
    IntervalsAuthError,
    IntervalsPayloadError,
)
from src.intervals_icu.infrastructure import IntervalsClientAdapter


def settings(**overrides):
    data = (
        dict(
            api_key="key",
            notion_secret="n",
            notion_database_id="db",
            notion_workout_database_id="w",
            notion_athlete_profile_database_id="p",
            wbsapi_url="https://w",
            upstash_redis_rest_url="https://r",
            upstash_redis_rest_token="rt",
            withings_client_id="wc",
            withings_client_secret="ws",
            intervals_api_key="intervals-secret",
        )
        | overrides
    )
    return Settings(**data)


@pytest.mark.asyncio
async def test_list_activities_uses_basic_auth_and_dates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/athlete/0/activities"
        assert request.url.params["oldest"] == "2026-07-07"
        assert request.headers["Accept"] == "application/json"
        assert request.headers["Authorization"].startswith("Basic ")
        return httpx.Response(200, json=[{"id": "i1"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await IntervalsClientAdapter(http, settings()).list_activities(
            oldest=date(2026, 7, 7), newest=date(2026, 7, 14)
        )
    assert result == [{"id": "i1"}]


@pytest.mark.asyncio
async def test_intervals_404_and_missing_are_empty():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(404))
    ) as http:
        assert await IntervalsClientAdapter(http, settings()).get_activity_intervals("i1") == []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    ) as http:
        assert await IntervalsClientAdapter(http, settings()).get_activity_intervals("i1") == []


@pytest.mark.asyncio
async def test_errors_do_not_include_api_key():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(401, json={}))
    ) as http:
        with pytest.raises(IntervalsAuthError) as exc:
            await IntervalsClientAdapter(http, settings()).list_activities(
                oldest=date.today(), newest=date.today()
            )
    assert "intervals-secret" not in str(exc.value)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500, json={}))
    ) as http:
        with pytest.raises(IntervalsApiError):
            await IntervalsClientAdapter(http, settings()).get_activity_intervals("i1")


@pytest.mark.asyncio
async def test_payload_validation():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"bad": True}))
    ) as http:
        with pytest.raises(IntervalsPayloadError):
            await IntervalsClientAdapter(http, settings()).list_activities(
                oldest=date.today(), newest=date.today()
            )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"icu_intervals": [1]}))
    ) as http:
        with pytest.raises(IntervalsPayloadError):
            await IntervalsClientAdapter(http, settings()).get_activity_intervals("i1")
