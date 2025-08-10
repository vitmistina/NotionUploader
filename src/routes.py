from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

from .models import (
    BodyMeasurement,
    DailyNutritionSummary,
    NutritionEntry,
    StatusResponse,
)
from .notion import entries_on_date, submit_to_notion
from .nutrition import get_daily_nutrition_summaries
from .withings import get_measurements

router: APIRouter = APIRouter(prefix="/v2")

@router.post("/nutrition-entries", status_code=201, response_model=StatusResponse)
async def create_nutrition_entry(entry: NutritionEntry) -> StatusResponse:
    return await submit_to_notion(entry)

@router.get("/nutrition-entries/daily/{date}", response_model=List[NutritionEntry])
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format."),
) -> List[NutritionEntry]:
    return await entries_on_date(date)

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
) -> List[DailyNutritionSummary]:
    return await get_daily_nutrition_summaries(start_date, end_date)

@router.get("/body-measurements", response_model=List[BodyMeasurement])
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
) -> List[BodyMeasurement]:
    """
    Get body measurements from Withings scale for the specified number of days.
    Default is 7 days of measurements.
    """
    return await get_measurements(days)

@router.get("/api-schema")
async def get_api_schema(request: Request) -> JSONResponse:
    """Return the OpenAPI schema for this API version."""
    openapi_schema: Dict[str, Any] = request.app.openapi()
    openapi_schema["servers"] = [
        {"url": "https://notionuploader-groa.onrender.com"}
    ]
    return JSONResponse(openapi_schema)
