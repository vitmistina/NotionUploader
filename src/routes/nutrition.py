from __future__ import annotations

from typing import List

from fastapi import APIRouter, Path, Query, Depends

from ..models.nutrition import (
    DailyNutritionSummary,
    DailyNutritionSummaryWithEntries,
    NutritionEntry,
    StatusResponse,
    NutritionEntriesResponse,
    NutritionPeriodResponse,
)
from ..models.time import get_local_time
from ..notion import entries_on_date, submit_to_notion
from ..nutrition import build_daily_summary, get_daily_nutrition_summaries
from ..services.interfaces import NotionAPI
from ..services.notion import get_notion_client
from ..settings import Settings, get_settings
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.post("/nutrition-entries", status_code=201, response_model=StatusResponse)
async def create_nutrition_entry(
    entry: NutritionEntry,
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> StatusResponse:
    return await submit_to_notion(entry, settings, client)


@router.get(
    "/nutrition-entries/daily/{date}",
    response_model=NutritionEntriesResponse,
)
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format."),
    timezone: str = timezone_query,
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> NutritionEntriesResponse:
    entries: List[NutritionEntry] = await entries_on_date(date, settings, client)
    summary: DailyNutritionSummary = build_daily_summary(date, entries)
    local_time, part = get_local_time(timezone)
    return NutritionEntriesResponse(
        entries=entries, summary=summary, local_time=local_time, part_of_day=part
    )


@router.get(
    "/nutrition-entries/period",
    response_model=NutritionPeriodResponse,
)
async def list_nutrition_entries_by_period(
    start_date: str = Query(
        ..., description="Start date (inclusive) in YYYY-MM-DD format.",
    ),
    end_date: str = Query(
        ..., description="End date (inclusive) in YYYY-MM-DD format.",
    ),
    timezone: str = timezone_query,
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> NutritionPeriodResponse:
    summaries: List[DailyNutritionSummaryWithEntries] = await get_daily_nutrition_summaries(
        start_date, end_date, settings, client
    )
    local_time, part = get_local_time(timezone)
    return NutritionPeriodResponse(
        nutrition=summaries, local_time=local_time, part_of_day=part
    )
