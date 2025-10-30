from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..metrics import estimate_if_tss_from_hr
from ..models.workout import (
    ManualWorkoutResponse,
    ManualWorkoutSubmission,
    WorkoutLog,
)
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


@router.post(
    "/workout-logs/manual",
    response_model=ManualWorkoutResponse,
    status_code=201,
)
async def create_manual_workout(
    submission: ManualWorkoutSubmission,
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> ManualWorkoutResponse:
    detail = submission.to_notion_detail()

    intensity_factor = submission.intensity_factor
    tss = submission.tss

    if intensity_factor is None or tss is None:
        athlete = await repository.fetch_latest_athlete_profile()
        estimate = estimate_if_tss_from_hr(
            hr_avg_session=submission.average_heartrate,
            hr_max_session=submission.max_heartrate,
            dur_s=detail.get("elapsed_time"),
            hr_max_athlete=athlete.get("max_hr"),
            hr_rest_athlete=athlete.get("resting_hr"),
            kcal=submission.calories,
        )
        if estimate:
            if intensity_factor is None:
                intensity_factor = estimate[0]
            if tss is None:
                tss = estimate[1]

    hr_drift = (
        submission.hr_drift_percent
        if submission.hr_drift_percent is not None
        else 0.0
    )
    vo2max = (
        submission.vo2max_minutes
        if submission.vo2max_minutes is not None
        else 0.0
    )

    await repository.save_workout(
        detail,
        attachment="",
        hr_drift=hr_drift,
        vo2max=vo2max,
        tss=tss,
        intensity_factor=intensity_factor,
    )

    return ManualWorkoutResponse(
        id=detail["id"],
        name=detail["name"],
        start_time=submission.start_time,
        duration_s=detail["elapsed_time"],
        intensity_factor=intensity_factor,
        tss=tss,
    )


