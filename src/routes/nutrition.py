from __future__ import annotations

from typing import List

from fastapi import APIRouter, Path, Query, Depends

from ..models.nutrition import (
    DailyNutritionSummary,
    NutritionEntry,
    StatusResponse,
)
from ..notion import entries_on_date, submit_to_notion
from ..nutrition import get_daily_nutrition_summaries
from ..settings import Settings, get_settings

router: APIRouter = APIRouter()


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


@router.get("/nutrition-entries/period", response_model=List[DailyNutritionSummary])
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
