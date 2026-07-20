from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..application.advice import GetSummaryAdviceUseCase
from ..application.advice_context import GetAdviceContextUseCase
from ..models.advice import SummaryAdvice
from ..models.advice_context import AdviceContext
from ..platform.wiring import get_advice_context_use_case, get_summary_advice_use_case
from .utils import validated_timezone

router: APIRouter = APIRouter()


@router.get("/advice-context", response_model=AdviceContext)
async def get_advice_context(
    days: int = Query(7, ge=1, le=90, description="Inclusive calendar days of analytical context."),
    timezone: str = Depends(validated_timezone),
    include_entries: bool = Query(
        True, description="Include raw nutrition entries in daily evidence."
    ),
    include_workout_details: bool = Query(
        False, description="Include stored interval details when available."
    ),
    use_case: GetAdviceContextUseCase = Depends(get_advice_context_use_case),
) -> AdviceContext:
    """Return deterministic evidence for an advice-generating consumer."""
    return await use_case(
        days=days,
        timezone=timezone,
        include_entries=include_entries,
        include_workout_details=include_workout_details,
    )


@router.get("/summary-advice", response_model=SummaryAdvice)
async def get_summary_advice(
    days: int = Query(7, description="Number of days of data to retrieve."),
    timezone: str = Depends(validated_timezone),
    use_case: GetSummaryAdviceUseCase = Depends(get_summary_advice_use_case),
) -> SummaryAdvice:
    return await use_case(days, timezone)
