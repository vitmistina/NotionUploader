from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..application.workouts import (
    CreateManualWorkoutUseCase,
    ListWorkoutsUseCase,
    SyncWorkoutMetricsUseCase,
    WorkoutNotFoundError,
)
from ..models.responses import OperationStatus
from ..models.workout import ManualWorkoutSubmission, WorkoutLog
from ..platform.wiring import (
    get_create_manual_workout_use_case,
    get_list_workouts_use_case,
    get_sync_workout_metrics_use_case,
)

router: APIRouter = APIRouter()


@router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_logged_workouts(
    days: int = Query(7, description="Number of days of logged workouts to retrieve."),
    use_case: ListWorkoutsUseCase = Depends(get_list_workouts_use_case),
) -> List[WorkoutLog]:
    return await use_case(days)


@router.post("/workout-logs/{page_id}/sync", response_model=OperationStatus)
async def sync_workout_metrics(
    page_id: str,
    use_case: SyncWorkoutMetricsUseCase = Depends(get_sync_workout_metrics_use_case),
) -> OperationStatus:
    try:
        return await use_case(page_id)
    except WorkoutNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "Workout not found"}) from exc


@router.post(
    "/workout-logs/manual",
    response_model=OperationStatus,
    status_code=201,
)
async def create_manual_workout(
    submission: ManualWorkoutSubmission,
    use_case: CreateManualWorkoutUseCase = Depends(
        get_create_manual_workout_use_case
    ),
) -> OperationStatus:
    return await use_case(submission)
