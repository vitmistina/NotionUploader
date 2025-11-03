from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Path, Query

from ..models.nutrition import (
    DailyNutritionSummary,
    DailyNutritionSummaryWithEntries,
    NutritionEntry,
    NutritionSummaryResponse,
)
from ..models.responses import OperationStatus
from ..models.time import get_local_time
from ..notion.application.ports import NutritionRepository
from ..notion.infrastructure.nutrition_repository import get_nutrition_repository
from ..domain.nutrition.summary import build_daily_summary
from ..domain.nutrition.summaries import get_daily_nutrition_summaries
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.post("/nutrition-entries", status_code=201, response_model=OperationStatus)
async def create_nutrition_entry(
    entry: NutritionEntry,
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> OperationStatus:
    await repository.create_entry(entry)
    return OperationStatus(status="ok")


@router.get(
    "/nutrition-entries/daily/{date}",
    response_model=NutritionSummaryResponse,
)
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format."),
    timezone: str = timezone_query,
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> NutritionSummaryResponse:
    entries: List[NutritionEntry] = await repository.list_entries_on_date(date)
    summary: DailyNutritionSummary = build_daily_summary(date, entries)
    day_summary = DailyNutritionSummaryWithEntries(
        **summary.model_dump(), entries=entries
    )
    local_time, part = get_local_time(timezone)
    return NutritionSummaryResponse(
        days=[day_summary],
        local_time=local_time,
        part_of_day=part,
    )


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
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> NutritionSummaryResponse:
    summaries: List[DailyNutritionSummaryWithEntries] = await get_daily_nutrition_summaries(
        start_date, end_date, repository
    )
    local_time, part = get_local_time(timezone)
    return NutritionSummaryResponse(
        days=summaries,
        local_time=local_time,
        part_of_day=part,
    )
