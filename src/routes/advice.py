from __future__ import annotations

import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from ..metrics import linear_regression
from ..models.advice import SummaryAdvice
from ..models.body import BodyMetricTrends
from ..models.time import get_local_time
from ..nutrition import get_daily_nutrition_summaries
from ..services.redis import RedisClient, get_redis
from ..settings import Settings, get_settings
from ..withings import get_measurements
from ..notion.application.ports import NutritionRepository, WorkoutRepository
from ..notion.infrastructure.nutrition_repository import get_nutrition_repository
from ..notion.infrastructure.workout_repository import get_workout_repository
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.get("/summary-advice", response_model=SummaryAdvice)
async def get_summary_advice(
    days: int = Query(7, description="Number of days of data to retrieve."),
    timezone: str = timezone_query,
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    nutrition_repository: NutritionRepository = Depends(get_nutrition_repository),
    workout_repository: WorkoutRepository = Depends(get_workout_repository),
) -> SummaryAdvice:
    end: date = date.today()
    start: date = end - timedelta(days=days - 1)
    nutrition_coro = get_daily_nutrition_summaries(
        start.isoformat(), end.isoformat(), nutrition_repository
    )
    metrics_coro = get_measurements(days, redis, settings)
    workouts_coro = workout_repository.list_recent_workouts(days)
    athlete_coro = workout_repository.fetch_latest_athlete_profile()
    nutrition, metrics, workouts, athlete_metrics = await asyncio.gather(
        nutrition_coro, metrics_coro, workouts_coro, athlete_coro
    )
    trends = BodyMetricTrends(**linear_regression(metrics))
    local_time, part = get_local_time(timezone)
    return SummaryAdvice(
        nutrition=nutrition,
        metrics=metrics,
        metric_trends=trends,
        workouts=workouts,
        athlete_metrics=athlete_metrics,
        local_time=local_time,
        part_of_day=part,
    )
