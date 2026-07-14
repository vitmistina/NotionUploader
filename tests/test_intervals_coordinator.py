from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.intervals_icu.application import IntervalsApiError, IntervalsSyncCoordinator


class Client:
    def __init__(self, activities):
        self.activities = activities
        self.list_calls = []
        self.interval_calls = []

    async def list_activities(self, *, oldest: date, newest: date):
        self.list_calls.append((oldest, newest))
        return self.activities

    async def get_activity_intervals(self, activity_id: str):
        self.interval_calls.append(activity_id)
        if activity_id == "i999":
            raise IntervalsApiError("boom secret-free", status_code=503)
        return []


class Repo:
    def __init__(self):
        self.saved = []
        self.fetches = 0

    async def list_recent_workouts(self, days: int):
        return []

    async def fetch_latest_athlete_profile(self):
        self.fetches += 1
        return {"ftp": 200, "max_hr": 190}

    async def save_workout(
        self,
        detail: dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2max: float,
        *,
        tss=None,
        intensity_factor=None,
    ):
        self.saved.append((detail, attachment, hr_drift, vo2max, tss, intensity_factor))

    async def fill_missing_metrics(self, page_id: str):
        return None


def rouvy(id="i1", start="2026-07-12T18:31:22"):
    return {
        "id": id,
        "name": "Ride",
        "source": "OAUTH_CLIENT",
        "oauth_client_name": "ROUVY",
        "start_date_local": start,
        "start_date": "2026-07-12T16:31:22Z",
        "type": "VirtualRide",
        "moving_time": 100,
        "elapsed_time": 100,
        "icu_training_load": 12,
        "icu_intensity": 50,
    }


@pytest.mark.asyncio
async def test_sync_filters_and_processes_sequentially():
    activities = [
        rouvy("i1"),
        rouvy("i1"),
        rouvy("i2") | {"source": "STRAVA"},
        rouvy("i3", "2026-01-01T00:00:00"),
        rouvy("i4")
        | {
            "oauth_client_name": "Intervals Companion",
            "start_date": "2026-07-08T10:49:58Z",
            "type": "Walk",
        },
        rouvy("i5") | {"source": None},
    ]
    client = Client(activities)
    repo = Repo()
    coord = IntervalsSyncCoordinator(
        client,
        repo,
        default_lookback_days=7,
        rouvy_start_date=date(2026, 7, 1),
        clock=lambda: datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    result = await coord.sync_recent()
    assert client.list_calls == [(date(2026, 7, 7), date(2026, 7, 14))]
    assert (
        result.discovered == 6
        and result.eligible == 3
        and result.processed == 3
        and result.failed == 0
    )
    assert result.skipped_by_reason == {
        "duplicate_activity_id": 1,
        "source_strava": 1,
        "before_rouvy_start_date": 1,
    }
    assert repo.fetches == 1
    assert [s[0]["id"] for s in repo.saved] == [-1, 1783507798, -5]
    assert repo.saved[0][4] == 12 and repo.saved[0][5] == 0.5
    assert all(isinstance(s[1], str) and s[1] for s in repo.saved)


@pytest.mark.asyncio
async def test_partial_failure_continues():
    client = Client([rouvy("i999"), rouvy("i2")])
    repo = Repo()
    result = await IntervalsSyncCoordinator(
        client,
        repo,
        default_lookback_days=1,
        rouvy_start_date=None,
        clock=lambda: datetime(2026, 7, 14, tzinfo=timezone.utc),
    ).sync_recent()
    assert result.status == "partial_failure"
    assert result.processed == 1 and result.failed == 1
    assert result.failures[0].activity_id == "i999"


def test_lookback_validation():
    coord = IntervalsSyncCoordinator(
        Client([]), Repo(), default_lookback_days=7, rouvy_start_date=None
    )
    with pytest.raises(ValueError):
        coord._validate_lookback(0)
    with pytest.raises(ValueError):
        coord._validate_lookback(366)
