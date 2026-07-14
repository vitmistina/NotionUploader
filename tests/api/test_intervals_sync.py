from datetime import date

import pytest

from src.intervals_icu.application import IntervalsSyncResult


@pytest.mark.asyncio
async def test_sync_endpoint_success(client, intervals_sync_coordinator_spy):
    result = IntervalsSyncResult(
        status="ok",
        oldest=date(2026, 7, 7),
        newest=date(2026, 7, 14),
        lookback_days=7,
        discovered=1,
        eligible=1,
        processed=1,
        skipped=0,
        failed=0,
    )
    intervals_sync_coordinator_spy.expect_sync(lookback_days=7, returns=result)
    response = await client.post(
        "/v2/intervals/sync?lookback_days=7", headers={"x-api-key": "test-key"}
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1
    intervals_sync_coordinator_spy.assert_last_sync(7)


@pytest.mark.asyncio
async def test_sync_endpoint_auth_and_validation(client):
    assert (await client.post("/v2/intervals/sync")).status_code == 401
    assert (
        await client.post("/v2/intervals/sync", headers={"x-api-key": "bad"})
    ).status_code == 401
    assert (
        await client.post("/v2/intervals/sync?lookback_days=0", headers={"x-api-key": "test-key"})
    ).status_code == 422
    assert (
        await client.post("/v2/intervals/sync?lookback_days=366", headers={"x-api-key": "test-key"})
    ).status_code == 422


@pytest.mark.asyncio
async def test_sync_endpoint_partial_failure_returns_502(client, intervals_sync_coordinator_spy):
    result = IntervalsSyncResult(
        status="partial_failure",
        oldest=date(2026, 7, 7),
        newest=date(2026, 7, 14),
        lookback_days=7,
        discovered=1,
        eligible=1,
        processed=0,
        skipped=0,
        failed=1,
        failures=[{"activity_id": "i1", "error": "boom"}],
    )
    intervals_sync_coordinator_spy.expect_sync(lookback_days=None, returns=result)
    response = await client.post("/v2/intervals/sync", headers={"x-api-key": "test-key"})
    assert response.status_code == 502
    assert response.json()["failed"] == 1


@pytest.mark.asyncio
async def test_strava_routes_removed(client):
    assert (await client.get("/strava-webhook")).status_code == 404
    assert (
        await client.post("/v2/strava-activity/1", headers={"x-api-key": "test-key"})
    ).status_code == 404
