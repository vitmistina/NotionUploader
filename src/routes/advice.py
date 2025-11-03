from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..application.advice import GetSummaryAdviceUseCase
from ..models.advice import SummaryAdvice
from ..platform.wiring import get_summary_advice_use_case
from .utils import timezone_query

router: APIRouter = APIRouter()


@router.get("/summary-advice", response_model=SummaryAdvice)
async def get_summary_advice(
    days: int = Query(7, description="Number of days of data to retrieve."),
    timezone: str = timezone_query,
    use_case: GetSummaryAdviceUseCase = Depends(get_summary_advice_use_case),
) -> SummaryAdvice:
    return await use_case(days, timezone)
