from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ..intervals_icu.application import (
    IntervalsApiError,
    IntervalsSyncCoordinator,
    IntervalsSyncResult,
)
from ..platform.wiring import provide_intervals_sync_coordinator

router = APIRouter(prefix="/intervals", tags=["intervals"])


@router.post(
    "/sync", response_model=IntervalsSyncResult, responses={502: {"model": IntervalsSyncResult}}
)
async def sync_intervals(
    lookback_days: Annotated[int | None, Query(ge=1, le=365)] = None,
    coordinator: IntervalsSyncCoordinator = Depends(provide_intervals_sync_coordinator),
) -> IntervalsSyncResult | JSONResponse:
    try:
        result = await coordinator.sync_recent(lookback_days=lookback_days)
    except IntervalsApiError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "INTERVALS_API_ERROR",
                "message": str(exc),
                "status_code": exc.status_code,
            },
        ) from exc
    if result.failed:
        return JSONResponse(status_code=502, content=result.model_dump(mode="json"))
    return result
