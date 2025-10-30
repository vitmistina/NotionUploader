from __future__ import annotations

import base64
import gzip
import json
from typing import Any, AsyncIterator

import httpx
from fastapi import Depends, HTTPException

from ...models import MetricResults, StravaActivity
from ...notion.application.ports import WorkoutRepository
from ...notion.infrastructure.workout_repository import get_workout_repository
from ...services.redis import RedisClient, get_redis
from ...settings import Settings, get_settings
from ..domain.metrics import compute_activity_metrics
from ..infrastructure.client import StravaAuthError, StravaClient


class StravaActivityCoordinator:
    """Coordinates Strava ingestion between client, metrics, and persistence."""

    def __init__(
        self,
        client: StravaClient,
        workout_repository: WorkoutRepository,
    ) -> None:
        self._client = client
        self._workouts = workout_repository

    async def fetch_activity(self, activity_id: int) -> StravaActivity:
        payload = await self._client.get_activity(activity_id)
        return StravaActivity.model_validate(payload)

    async def fetch_athlete(self) -> dict[str, Any]:
        return await self._workouts.fetch_latest_athlete_profile()

    def compute_metrics(
        self, activity: StravaActivity, athlete: dict[str, Any]
    ) -> MetricResults:
        return compute_activity_metrics(activity, athlete)

    async def persist_activity(
        self, activity: StravaActivity, metrics: MetricResults
    ) -> None:
        detail = activity.model_dump()
        minified = json.dumps(detail, separators=(",", ":"))
        compressed = gzip.compress(minified.encode("utf-8"))
        attachment = base64.b64encode(compressed).decode("utf-8")
        await self._workouts.save_workout(
            detail,
            attachment,
            metrics.hr_drift,
            metrics.vo2,
            tss=metrics.tss,
            intensity_factor=metrics.intensity_factor,
        )

    async def process_activity(self, activity_id: int) -> None:
        try:
            activity = await self.fetch_activity(activity_id)
        except StravaAuthError as exc:  # pragma: no cover - exercised via HTTPException
            raise HTTPException(status_code=500, detail={"error": "Auth failure"}) from exc

        athlete = await self.fetch_athlete()
        metrics = self.compute_metrics(activity, athlete)
        await self.persist_activity(activity, metrics)


async def get_strava_activity_coordinator(
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    workout_repository: WorkoutRepository = Depends(get_workout_repository),
) -> AsyncIterator[StravaActivityCoordinator]:
    async with httpx.AsyncClient() as http_client:
        client = StravaClient(http_client=http_client, redis=redis, settings=settings)
        coordinator = StravaActivityCoordinator(client, workout_repository)
        yield coordinator


__all__ = [
    "StravaActivityCoordinator",
    "compute_activity_metrics",
    "get_strava_activity_coordinator",
]
