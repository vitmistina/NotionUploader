from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ..domain.body_metrics.hr import estimate_if_tss_from_hr
from ..models.responses import OperationStatus
from ..models.workout import ManualWorkoutSubmission, WorkoutLog
from ..notion.application.ports import WorkoutRepository

Estimator = Callable[
    [
        Optional[float],
        Optional[float],
        Optional[int],
        Optional[float],
        Optional[float],
        Optional[float],
    ],
    Optional[Tuple[float, float]],
]


class WorkoutNotFoundError(Exception):
    """Raised when attempting to operate on a missing workout."""


@dataclass
class ListWorkoutsUseCase:
    """Return recent workouts from the configured repository."""

    repository: WorkoutRepository

    async def __call__(self, days: int) -> List[WorkoutLog]:
        return await self.repository.list_recent_workouts(days)


@dataclass
class SyncWorkoutMetricsUseCase:
    """Fill missing workout metrics via the configured repository."""

    repository: WorkoutRepository

    async def __call__(self, page_id: str) -> OperationStatus:
        workout = await self.repository.fill_missing_metrics(page_id)
        if workout is None:
            raise WorkoutNotFoundError(f"Workout {page_id} not found")
        return OperationStatus(status="updated")


@dataclass
class CreateManualWorkoutUseCase:
    """Persist a manual workout submission and estimate metrics when missing."""

    repository: WorkoutRepository
    estimator: Estimator = estimate_if_tss_from_hr

    async def __call__(self, submission: ManualWorkoutSubmission) -> OperationStatus:
        detail = submission.to_notion_detail()

        intensity_factor = submission.intensity_factor
        tss = submission.tss

        if intensity_factor is None or tss is None:
            athlete = await self.repository.fetch_latest_athlete_profile()
            estimate = self.estimator(
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

        hr_drift = submission.hr_drift_percent or 0.0
        vo2max = submission.vo2max_minutes or 0.0

        await self.repository.save_workout(
            detail,
            attachment="",
            hr_drift=hr_drift,
            vo2max=vo2max,
            tss=tss,
            intensity_factor=intensity_factor,
        )

        return OperationStatus(status="ok", id=detail["id"])


__all__ = [
    "CreateManualWorkoutUseCase",
    "ListWorkoutsUseCase",
    "SyncWorkoutMetricsUseCase",
    "WorkoutNotFoundError",
]
