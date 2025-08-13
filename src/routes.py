from __future__ import annotations

from typing import Any, Dict, List
from datetime import date, timedelta
import asyncio

from fastapi import APIRouter, Path, Query, Request, Depends
from fastapi.responses import JSONResponse

from .models.body import BodyMeasurement
from .models.nutrition import (
    DailyNutritionSummary,
    NutritionEntry,
    StatusResponse,
)
from .models.workout import ComplexAdvice, WorkoutLog
from .notion import entries_on_date, submit_to_notion
from .nutrition import get_daily_nutrition_summaries
from .withings import get_measurements
from .strava_activity import process_activity
from .workout_notion import fetch_workouts_from_notion, fetch_latest_athlete_profile
from .settings import Settings, get_settings

router: APIRouter = APIRouter(prefix="/v2")

@router.post("/nutrition-entries", status_code=201, response_model=StatusResponse)
async def create_nutrition_entry(
    entry: NutritionEntry, settings: Settings = Depends(get_settings)
) -> StatusResponse:
    return await submit_to_notion(entry, settings)

@router.get("/nutrition-entries/daily/{date}", response_model=List[NutritionEntry])
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format."),
    settings: Settings = Depends(get_settings),
) -> List[NutritionEntry]:
    return await entries_on_date(date, settings)

@router.get(
    "/nutrition-entries/period", response_model=List[DailyNutritionSummary]
)
async def list_nutrition_entries_by_period(
    start_date: str = Query(
        ..., description="Start date (inclusive) in YYYY-MM-DD format.",
    ),
    end_date: str = Query(
        ..., description="End date (inclusive) in YYYY-MM-DD format.",
    ),
    settings: Settings = Depends(get_settings),
) -> List[DailyNutritionSummary]:
    return await get_daily_nutrition_summaries(start_date, end_date, settings)

@router.get("/body-measurements", response_model=List[BodyMeasurement])
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
    settings: Settings = Depends(get_settings),
) -> List[BodyMeasurement]:
    """
    Get body measurements from Withings scale for the specified number of days.
    Default is 7 days of measurements.
    """
    return await get_measurements(days, settings)


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


@router.post("/strava-activity/{activity_id}", include_in_schema=False)
async def trigger_strava_processing(
    activity_id: int, settings: Settings = Depends(get_settings)
) -> Dict[str, str]:
    await process_activity(activity_id, settings)
    return {"status": "ok"}

@router.get("/api-schema")
async def get_api_schema(request: Request) -> JSONResponse:
    """Return the OpenAPI schema for this API version."""
    openapi_schema: Dict[str, Any] = request.app.openapi()
    openapi_schema["servers"] = [
        {"url": "https://notionuploader-groa.onrender.com"}
    ]
    return JSONResponse(openapi_schema)
