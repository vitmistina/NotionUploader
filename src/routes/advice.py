from __future__ import annotations

import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from ..models.advice import ComplexAdvice
from ..models.body import BodyMetricTrends
from ..models.time import get_local_time
from ..nutrition import get_daily_nutrition_summaries
from ..services.interfaces import NotionAPI
from ..services.notion import get_notion_client
from ..services.redis import RedisClient, get_redis
from ..settings import Settings, get_settings
from ..withings import get_measurements
from ..metrics import linear_regression
from ..workout_notion import (
    fetch_latest_athlete_profile,
    fetch_workouts_from_notion,
)
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.get("/complex-advice", response_model=ComplexAdvice)
async def get_complex_advice(
    days: int = Query(7, description="Number of days of data to retrieve."),
    timezone: str = timezone_query,
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> ComplexAdvice:
    end: date = date.today()
    start: date = end - timedelta(days=days - 1)
    nutrition_coro = get_daily_nutrition_summaries(
        start.isoformat(), end.isoformat(), settings, client
    )
    metrics_coro = get_measurements(days, redis, settings)
    workouts_coro = fetch_workouts_from_notion(days, settings, client)
    athlete_coro = fetch_latest_athlete_profile(settings, client)
    nutrition, metrics, workouts, athlete_metrics = await asyncio.gather(
        nutrition_coro, metrics_coro, workouts_coro, athlete_coro
    )
    trends = BodyMetricTrends(**linear_regression(metrics))
    local_time, part = get_local_time(timezone)
    return ComplexAdvice(
        nutrition=nutrition,
        metrics=metrics,
        metric_trends=trends,
        workouts=workouts,
        athlete_metrics=athlete_metrics,
        local_time=local_time,
        part_of_day=part,
    )
