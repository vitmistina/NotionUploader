from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.workout import WorkoutLog
from ..notion.application.ports import WorkoutRepository
from ..notion.infrastructure.workout_repository import get_workout_repository

router: APIRouter = APIRouter()


@router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_logged_workouts(
    days: int = Query(7, description="Number of days of logged workouts to retrieve."),
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> List[WorkoutLog]:
    return await repository.list_recent_workouts(days)


@router.post("/workout-logs/{page_id}/fill", response_model=WorkoutLog)
async def fill_workout_metrics(
    page_id: str,
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> WorkoutLog:
    workout = await repository.fill_missing_metrics(page_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


