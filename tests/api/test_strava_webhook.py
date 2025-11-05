"""Strava webhook contract tests."""

from __future__ import annotations

import httpx
import pytest

from platform.config import Settings
from tests.api.helpers import encode_signed_strava_event, make_strava_event
from tests.conftest import StravaCoordinatorSpy

pytestmark = pytest.mark.asyncio


async def test_strava_webhook_verification(client: httpx.AsyncClient, settings: Settings) -> None:
    """Returns the challenge token when verification succeeds."""

    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "abc",
        "hub.verify_token": settings.strava_verify_token,
    }

    response = await client.get("/strava-webhook", params=params)

    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc"}


async def test_strava_webhook_event(
    client: httpx.AsyncClient, settings: Settings, strava_coordinator_spy: StravaCoordinatorSpy
) -> None:
    """Triggers activity processing when receiving a create event."""

    event = make_strava_event(object_id=42)
    body, signature = encode_signed_strava_event(event, client_secret=settings.strava_client_secret)
    strava_coordinator_spy.expect_process_activity(activity_id=42)

    response = await client.post(
        "/strava-webhook",
        content=body,
        headers={"X-Strava-Signature": signature},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(42)


async def test_strava_webhook_event_update(
    client: httpx.AsyncClient, settings: Settings, strava_coordinator_spy: StravaCoordinatorSpy
) -> None:
    """Triggers activity processing for update events."""

    event = make_strava_event(aspect_type="update", object_id=43)
    body, signature = encode_signed_strava_event(event, client_secret=settings.strava_client_secret)
    strava_coordinator_spy.expect_process_activity(activity_id=43)

    response = await client.post(
        "/strava-webhook",
        content=body,
        headers={"X-Strava-Signature": signature},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(43)


async def test_manual_strava_processing(
    client: httpx.AsyncClient, settings: Settings, strava_coordinator_spy: StravaCoordinatorSpy
) -> None:
    """Allows manual triggering of Strava activity processing."""

    strava_coordinator_spy.expect_process_activity(activity_id=99)

    response = await client.post(
        "/v2/strava-activity/99",
        headers={"x-api-key": settings.api_key},
    )

    assert response.status_code == 200
    strava_coordinator_spy.assert_last_process_activity(99)
