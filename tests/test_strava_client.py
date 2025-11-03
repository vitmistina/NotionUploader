"""Strava API client behaviour."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, Optional

import httpx
import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.platform.config import Settings
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
@pytest.mark.parametrize(
    "scenario, seed_store, handler",
    [
        pytest.param(
            "missing_token",
            {},
            None,
            id="missing_token",
        ),
        pytest.param(
            "http_error",
            {"strava_refresh_token": "refresh-token"},
            lambda request: httpx.Response(500, json={"message": "error"}),
            id="http_error",
        ),
        pytest.param(
            "missing_access_token",
            {"strava_refresh_token": "refresh-token"},
            lambda request: httpx.Response(
                200, json={"refresh_token": "new-refresh"}
            ),
            id="missing_access_token",
        ),
    ],
)
async def test_strava_refresh_access_token_failure_modes(
    scenario: str,
    seed_store: Dict[str, str],
    handler: Optional[Callable[[httpx.Request], httpx.Response]],
    settings: Settings,
    freeze_time,
    redis_fake: RedisFake,
) -> None:
    """Refreshing the Strava token surfaces storage and HTTP failures."""

    _ = freeze_time
    redis_fake.store.update(seed_store)

    transport_handler = handler or (lambda _: httpx.Response(204))

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as http_client:
        strava_client = StravaClientAdapter(http_client, redis_fake, settings)
        with pytest.raises(StravaAuthError):
            await strava_client._refresh_access_token()

    if scenario == "missing_token":
        assert not redis_fake.expirations


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
