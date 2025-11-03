from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from ..application.nutrition import (
    CreateNutritionEntryUseCase,
    GetDailyNutritionEntriesUseCase,
    GetNutritionEntriesByPeriodUseCase,
)
from ..models.nutrition import NutritionEntry, NutritionSummaryResponse
from ..models.responses import OperationStatus
from ..platform.wiring import (
    get_create_nutrition_entry_use_case,
    get_daily_nutrition_entries_use_case,
    get_nutrition_entries_by_period_use_case,
)
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.post("/nutrition-entries", status_code=201, response_model=OperationStatus)
async def create_nutrition_entry(
    entry: NutritionEntry,
    use_case: CreateNutritionEntryUseCase = Depends(
        get_create_nutrition_entry_use_case
    ),
) -> OperationStatus:
    return await use_case(entry)


@router.get(
    "/nutrition-entries/daily/{date}",
    response_model=NutritionSummaryResponse,
)
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format."),
    timezone: str = timezone_query,
    use_case: GetDailyNutritionEntriesUseCase = Depends(
        get_daily_nutrition_entries_use_case
    ),
) -> NutritionSummaryResponse:
    return await use_case(date, timezone)


@router.get(
    "/nutrition-entries/period",
    response_model=NutritionSummaryResponse,
)
async def list_nutrition_entries_by_period(
    start_date: str = Query(
        ..., description="Start date (inclusive) in YYYY-MM-DD format.",
    ),
    end_date: str = Query(
        ..., description="End date (inclusive) in YYYY-MM-DD format.",
    ),
    timezone: str = timezone_query,
    use_case: GetNutritionEntriesByPeriodUseCase = Depends(
        get_nutrition_entries_by_period_use_case
    ),
) -> NutritionSummaryResponse:
    return await use_case(start_date, end_date, timezone)
