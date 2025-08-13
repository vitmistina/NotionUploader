from __future__ import annotations

from typing import List
from datetime import date, timedelta
import asyncio

from fastapi import APIRouter, Query, Depends

from ..models.workout import ComplexAdvice, WorkoutLog
from ..nutrition import get_daily_nutrition_summaries
from ..settings import Settings, get_settings
from ..withings import get_measurements
from ..workout_notion import (
    fetch_latest_athlete_profile,
    fetch_workouts_from_notion,
)

router: APIRouter = APIRouter()


@router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_logged_workouts(
    days: int = Query(7, description="Number of days of logged workouts to retrieve."),
    settings: Settings = Depends(get_settings),
) -> List[WorkoutLog]:
    return await fetch_workouts_from_notion(days, settings)


@router.get("/complex-advice", response_model=ComplexAdvice)
async def get_complex_advice(
    days: int = Query(7, description="Number of days of data to retrieve."),
    settings: Settings = Depends(get_settings),
) -> ComplexAdvice:
    end: date = date.today()
    start: date = end - timedelta(days=days - 1)
    nutrition_coro = get_daily_nutrition_summaries(start.isoformat(), end.isoformat(), settings)
    metrics_coro = get_measurements(days, settings)
    workouts_coro = fetch_workouts_from_notion(days, settings)
    athlete_coro = fetch_latest_athlete_profile(settings)
    nutrition, metrics, workouts, athlete_metrics = await asyncio.gather(
        nutrition_coro, metrics_coro, workouts_coro, athlete_coro
    )
    return ComplexAdvice(
        nutrition=nutrition,
        metrics=metrics,
        workouts=workouts,
        athlete_metrics=athlete_metrics,
    )
