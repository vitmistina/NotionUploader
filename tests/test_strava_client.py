"""Strava API client behaviour."""

from __future__ import annotations

import sys
from pathlib import Path
import httpx
import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platform.config import Settings
from src.strava.application.ports import StravaAuthError
from src.strava.infrastructure.client import StravaClientAdapter

from tests.builders import make_strava_token_response
from tests.conftest import RedisFake


@pytest.mark.asyncio
async def test_strava_client_refreshes_access_token_on_401(
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """The client refreshes the cached token after a 401 response."""

    _ = freeze_time
    redis_fake.store.update(
        {
            "strava_access_token": "expired",
            "strava_refresh_token": "refresh-token",
        }
    )
    redis_fake.expect_set("strava_access_token", value="new-access", ex=90)
    redis_fake.expect_set(
        "strava_refresh_token",
        value="new-refresh",
        ex=365 * 24 * 60 * 60,
    )
    get_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=make_strava_token_response())

        get_calls["count"] += 1
        if get_calls["count"] == 1:
            return httpx.Response(401, json={"message": "expired"})

        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json={"id": 42, "name": "Morning Ride"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        activity = await strava_client.get_activity(42)

    assert activity["id"] == 42
    assert redis_fake.store["strava_access_token"] == "new-access"
    assert redis_fake.store["strava_refresh_token"] == "new-refresh"
    assert redis_fake.expirations["strava_access_token"] == 90
    assert redis_fake.expirations["strava_refresh_token"] == 365 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_strava_refresh_access_token_without_refresh_token(
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """A missing Strava refresh token fails before touching cached tokens."""

    _ = freeze_time

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(204))
    ) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        with pytest.raises(
            StravaAuthError, match="No Strava refresh token found in Redis"
        ):
            await strava_client._refresh_access_token()

    assert redis_fake.store == {}
    assert redis_fake.expirations == {}


@pytest.mark.asyncio
async def test_strava_refresh_access_token_http_error_preserves_cache(
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """HTTP token-refresh failures do not partially update Redis."""

    _ = freeze_time
    redis_fake.store["strava_refresh_token"] = "refresh-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(500, json={"message": "error"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        with pytest.raises(
            StravaAuthError, match="Failed to refresh Strava access token"
        ):
            await strava_client._refresh_access_token()

    assert redis_fake.store == {"strava_refresh_token": "refresh-token"}
    assert redis_fake.expirations == {}


@pytest.mark.asyncio
async def test_strava_refresh_access_token_missing_access_token_preserves_cache(
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """Malformed token-refresh payloads do not partially update Redis."""

    _ = freeze_time
    redis_fake.store["strava_refresh_token"] = "refresh-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json={"refresh_token": "new-refresh"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        with pytest.raises(
            StravaAuthError,
            match="Strava token refresh response missing access token",
        ):
            await strava_client._refresh_access_token()

    assert redis_fake.store == {"strava_refresh_token": "refresh-token"}
    assert redis_fake.expirations == {}


@pytest.mark.asyncio
async def test_strava_refresh_access_token_without_expires_sets_without_ttl(
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """A missing expires value leaves the cached access token without TTL."""

    _ = freeze_time
    redis_fake.store["strava_refresh_token"] = "refresh-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json=make_strava_token_response(access_token="new", expires_in=None),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        token = await strava_client._refresh_access_token()

    assert token == "new"
    assert redis_fake.store["strava_access_token"] == "new"
    assert redis_fake.expirations["strava_access_token"] is None
