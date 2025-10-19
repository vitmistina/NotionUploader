import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import MetricResults, StravaActivity
from src.notion.application.ports import WorkoutRepository
from src.settings import Settings
from src.strava import StravaActivityCoordinator
from src.strava.domain.metrics import compute_activity_metrics
from src.strava.infrastructure.client import StravaClient


class DummyRedis:
    def __init__(self) -> None:
        self.store: Dict[str, str] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:  # pragma: no cover - simple store
        self.store[key] = value


class DummyWorkoutRepository(WorkoutRepository):
    def __init__(self) -> None:
        self.saved_payload: Dict[str, Any] | None = None
        self.athlete_profile: Dict[str, Any] = {}
        self.recent_workouts: List[Dict[str, Any]] = []

    async def list_recent_workouts(self, days: int) -> List[Any]:  # pragma: no cover - unused in tests
        return self.recent_workouts

    async def fetch_latest_athlete_profile(self) -> Dict[str, Any]:
        return self.athlete_profile

    async def save_workout(
        self,
        detail: Dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2max: float,
        *,
        tss: Optional[float] = None,
        intensity_factor: Optional[float] = None,
    ) -> None:
        self.saved_payload = {
            "detail": detail,
            "attachment": attachment,
            "hr_drift": hr_drift,
            "vo2max": vo2max,
            "tss": tss,
            "intensity_factor": intensity_factor,
        }


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


@pytest.mark.asyncio
async def test_strava_client_fetches_activity() -> None:
    redis = DummyRedis()
    redis.set("strava_access_token", "abc")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer abc"
        return httpx.Response(
            200,
            json={"id": 1, "name": "Run", "splits_metric": [], "laps": []},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        strava_client = StravaClient(client, redis, settings)
        payload = await strava_client.get_activity(1)

    assert payload["id"] == 1
    assert payload["name"] == "Run"


def test_compute_activity_metrics() -> None:
    activity = StravaActivity(
        id=1,
        name="Ride",
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

    metrics = compute_activity_metrics(activity, athlete)

    assert metrics.vo2 == pytest.approx(3.0)
    assert metrics.intensity_factor == pytest.approx(1.05)
    assert metrics.tss == pytest.approx(5.5125)


def test_compute_activity_metrics_without_heart_rate() -> None:
    activity = StravaActivity(
        id=2,
        name="Ride",
        splits_metric=[
            {"average_heartrate": None, "moving_time": 60},
            {"average_heartrate": None, "moving_time": 60},
        ],
        laps=[
            {
                "average_heartrate": None,
                "moving_time": 120,
                "max_heartrate": None,
            }
        ],
        weighted_average_watts=200,
        moving_time=120,
    )
    athlete = {"max_hr": 190, "ftp": 200}

    metrics = compute_activity_metrics(activity, athlete)

    assert metrics.hr_drift == 0.0
    assert metrics.vo2 == 0.0
    assert metrics.intensity_factor == pytest.approx(1.0)
    assert metrics.tss == pytest.approx(3.3333333333333335)


@pytest.mark.asyncio
async def test_coordinator_persist_to_notion() -> None:
    repository = DummyWorkoutRepository()

    class DummyClient:
        async def get_activity(self, activity_id: int) -> Dict[str, Any]:  # pragma: no cover - unused
            return {}

    coordinator = StravaActivityCoordinator(DummyClient(), repository)  # type: ignore[arg-type]
    activity = StravaActivity(id=1, name="Ride", description="ride")
    metrics = MetricResults(hr_drift=1.0, vo2=2.0, tss=3.0, intensity_factor=0.5)

    await coordinator.persist_activity(activity, metrics)

    assert repository.saved_payload is not None
    assert repository.saved_payload["hr_drift"] == 1.0
    assert repository.saved_payload["vo2max"] == 2.0
    assert repository.saved_payload["tss"] == 3.0
    assert repository.saved_payload["intensity_factor"] == 0.5
    detail = repository.saved_payload["detail"]
    assert detail["description"] == "ride"
    assert isinstance(repository.saved_payload["attachment"], str)
