from __future__ import annotations

import base64
import gzip
import json
from typing import Any, AsyncIterator

import httpx
from fastapi import Depends, HTTPException

from ..settings import Settings, get_settings
from ..strava import refresh_access_token
from ..metrics import hr_drift_from_splits, vo2max_minutes
from ..models import StravaActivity, MetricResults
from ..notion.application.ports import WorkoutRepository
from ..notion.infrastructure.workout_repository import get_workout_repository
from .redis import RedisClient, get_redis


class StravaActivityService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        workout_repository: WorkoutRepository,
        settings: Settings,
        redis: RedisClient,
    ) -> None:
        self.http_client = http_client
        self.workouts = workout_repository
        self.settings = settings
        self.redis = redis

    async def fetch_activity(self, activity_id: int) -> StravaActivity:
        access_token = self.redis.get("strava_access_token")
        if not access_token:
            access_token = await refresh_access_token(self.redis, self.settings)
            if not access_token:
                raise HTTPException(status_code=500, detail="Auth failure")
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = await self.http_client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=headers,
        )
        if resp.status_code == 401:
            access_token = await refresh_access_token(self.redis, self.settings)
            headers["Authorization"] = f"Bearer {access_token}"
            resp = await self.http_client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers=headers,
            )
        resp.raise_for_status()
        return StravaActivity.model_validate(resp.json())

    async def fetch_athlete(self) -> dict[str, Any]:
        return await self.workouts.fetch_latest_athlete_profile()

    def compute_metrics(
        self, activity: StravaActivity, athlete: dict[str, Any]
    ) -> MetricResults:
        splits = [s.model_dump() for s in activity.splits_metric]
        laps = [lap.model_dump() for lap in activity.laps]
        max_hr = athlete.get("max_hr")
        ftp = athlete.get("ftp")
        hr_drift = hr_drift_from_splits(splits)
        splits_for_vo2 = laps if len(laps) > 2 else splits
        vo2 = vo2max_minutes(splits_for_vo2, max_hr) if max_hr else 0.0
        weighted_watts = activity.weighted_average_watts
        moving_time = activity.moving_time
        intensity_factor = None
        tss = None
        if ftp and weighted_watts:
            intensity_factor = weighted_watts / ftp
            if moving_time:
                tss = (
                    moving_time
                    * weighted_watts
                    * intensity_factor
                    / (ftp * 3600)
                    * 100
                )
        return MetricResults(
            hr_drift=hr_drift,
            vo2=vo2,
            tss=tss,
            intensity_factor=intensity_factor,
        )

    async def persist_to_notion(
        self, activity: StravaActivity, metrics: MetricResults
    ) -> None:
        detail = activity.model_dump()
        minified = json.dumps(detail, separators=(",", ":"))
        compressed = gzip.compress(minified.encode("utf-8"))
        attachment = base64.b64encode(compressed).decode("utf-8")
        await self.workouts.save_workout(
            detail,
            attachment,
            metrics.hr_drift,
            metrics.vo2,
            tss=metrics.tss,
            intensity_factor=metrics.intensity_factor,
        )

    async def process_activity(self, activity_id: int) -> None:
        activity = await self.fetch_activity(activity_id)
        athlete = await self.fetch_athlete()
        metrics = self.compute_metrics(activity, athlete)
        await self.persist_to_notion(activity, metrics)


async def get_strava_activity_service(
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    workout_repository: WorkoutRepository = Depends(get_workout_repository),
) -> AsyncIterator[StravaActivityService]:
    async with httpx.AsyncClient() as http_client:
        yield StravaActivityService(http_client, workout_repository, settings, redis)
