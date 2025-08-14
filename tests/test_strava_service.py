import sys
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import MetricResults, StravaActivity
from src.services.strava_activity import StravaActivityService
from src.services.notion import NotionClient
from src.settings import Settings


class DummyRedis:
    def __init__(self) -> None:
        self.store: Dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str) -> None:
        self.store[key] = value


settings = Settings(
    api_key="key",
    notion_secret="secret",
    notion_database_id="db",
    notion_workout_database_id="workout-db123",
    notion_athlete_profile_database_id="profile-db123",
    strava_verify_token="verify-token",
    wbsapi_url="https://wbs.example.com",
    upstash_redis_rest_url="https://redis.example.com",
    upstash_redis_rest_token="token",
    withings_client_id="client-id",
    withings_client_secret="client-secret",
    strava_client_id="strava-client-id",
    strava_client_secret="strava-client-secret",
)

notion_client = NotionClient(settings=settings)


@pytest.mark.asyncio
async def test_fetch_activity_returns_model() -> None:
    redis = DummyRedis()
    redis.set("strava_access_token", "abc")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer abc"
        return httpx.Response(200, json={"splits_metric": [], "laps": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = StravaActivityService(client, notion_client, settings, redis)
        activity = await service.fetch_activity(1)
    assert isinstance(activity, StravaActivity)
    assert activity.splits_metric == []


@pytest.mark.asyncio
async def test_compute_metrics() -> None:
    service = StravaActivityService(None, notion_client, settings, DummyRedis())
    activity = StravaActivity(
        splits_metric=[{"average_heartrate": 100, "moving_time": 60}],
        laps=[
            {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
            {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
            {"average_heartrate": 190, "moving_time": 60, "max_heartrate": 190},
        ],
        weighted_average_watts=210,
        moving_time=180,
    )
    athlete = {"max_hr": 190, "ftp": 200}
    metrics = service.compute_metrics(activity, athlete)
    assert metrics.vo2 == pytest.approx(3.0)
    assert metrics.intensity_factor == pytest.approx(1.05)
    assert metrics.tss == pytest.approx(5.5125)


@pytest.mark.asyncio
async def test_persist_to_notion(monkeypatch) -> None:
    service = StravaActivityService(None, notion_client, settings, DummyRedis())
    activity = StravaActivity(description="ride")
    metrics = MetricResults(hr_drift=1.0, vo2=2.0, tss=3.0, intensity_factor=0.5)

    called: Dict[str, Any] = {}

    async def fake_save(
        detail: Dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2: float,
        *,
        tss: float | None,
        intensity_factor: float | None,
        settings: Settings,
        client: NotionClient,
    ) -> None:
        called["detail"] = detail
        called["hr_drift"] = hr_drift
        called["vo2"] = vo2
        called["tss"] = tss
        called["if"] = intensity_factor

    monkeypatch.setattr("src.services.strava_activity.save_workout_to_notion", fake_save)

    await service.persist_to_notion(activity, metrics)
    assert called["detail"]["description"] == "ride"
    assert called["hr_drift"] == 1.0
    assert called["vo2"] == 2.0
    assert called["tss"] == 3.0
    assert called["if"] == 0.5
