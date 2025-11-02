import sys
from pathlib import Path
from typing import Dict, Optional

import httpx
import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.settings import Settings
from src.strava.application.ports import StravaAuthError
from src.strava.infrastructure.client import StravaClient


class RecordingRedis:
    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self.store: Dict[str, str] = dict(initial or {})
        self.expirations: Dict[str, Optional[int]] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self.store[key] = value
        self.expirations[key] = ex


TEST_SETTINGS = Settings(
    api_key="key",
    notion_secret="secret",
    notion_database_id="db",
    notion_workout_database_id="workout-db",
    notion_athlete_profile_database_id="profile-db",
    strava_verify_token="verify",
    wbsapi_url="https://withings.example.com",
    upstash_redis_rest_url="https://redis.example.com",
    upstash_redis_rest_token="token",
    withings_client_id="withings-client",
    withings_client_secret="withings-secret",
    strava_client_id="strava-client",
    strava_client_secret="strava-secret",
)


@pytest.mark.asyncio
async def test_strava_client_refreshes_access_token_on_401() -> None:
    redis = RecordingRedis(
        {
            "strava_access_token": "expired",
            "strava_refresh_token": "refresh-token",
        }
    )
    get_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 120,
                },
            )

        get_calls["count"] += 1
        if get_calls["count"] == 1:
            return httpx.Response(401, json={"message": "expired"})

        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json={"id": 42, "name": "Morning Ride"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        strava_client = StravaClient(client, redis, TEST_SETTINGS)
        activity = await strava_client.get_activity(42)

    assert activity["id"] == 42
    assert redis.store["strava_access_token"] == "new-access"
    assert redis.expirations["strava_access_token"] == 90
    assert redis.store["strava_refresh_token"] == "new-refresh"
    assert redis.expirations["strava_refresh_token"] == 365 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_strava_refresh_access_token_requires_stored_token() -> None:
    redis = RecordingRedis()

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: None)) as client:
        strava_client = StravaClient(client, redis, TEST_SETTINGS)
        with pytest.raises(StravaAuthError):
            await strava_client._refresh_access_token()


@pytest.mark.asyncio
async def test_strava_refresh_access_token_handles_http_error() -> None:
    redis = RecordingRedis({"strava_refresh_token": "refresh-token"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(500, json={"message": "error"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        strava_client = StravaClient(client, redis, TEST_SETTINGS)
        with pytest.raises(StravaAuthError):
            await strava_client._refresh_access_token()


@pytest.mark.asyncio
async def test_strava_refresh_access_token_requires_access_token_in_response() -> None:
    redis = RecordingRedis({"strava_refresh_token": "refresh-token"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json={"refresh_token": "new-refresh"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        strava_client = StravaClient(client, redis, TEST_SETTINGS)
        with pytest.raises(StravaAuthError):
            await strava_client._refresh_access_token()


@pytest.mark.asyncio
async def test_strava_refresh_access_token_without_expires_sets_without_ttl() -> None:
    redis = RecordingRedis({"strava_refresh_token": "refresh-token"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json={"access_token": "new", "expires_in": None})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        strava_client = StravaClient(client, redis, TEST_SETTINGS)
        token = await strava_client._refresh_access_token()

    assert token == "new"
    assert redis.store["strava_access_token"] == "new"
    assert redis.expirations["strava_access_token"] is None
