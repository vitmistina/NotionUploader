"""FastAPI dependency wiring for application use cases."""

from __future__ import annotations

from fastapi import Depends

from ..application.advice import GetSummaryAdviceUseCase
from ..application.metrics import ListBodyMeasurementsUseCase
from ..application.nutrition import (
    CreateNutritionEntryUseCase,
    GetDailyNutritionEntriesUseCase,
    GetNutritionEntriesByPeriodUseCase,
)
from ..application.workouts import (
    CreateManualWorkoutUseCase,
    ListWorkoutsUseCase,
    SyncWorkoutMetricsUseCase,
)
from ..notion.application.ports import NutritionRepository, WorkoutRepository
from ..notion.infrastructure.nutrition_repository import get_nutrition_repository
from ..notion.infrastructure.workout_repository import get_workout_repository
from ..withings.application import WithingsMeasurementsPort
from ..withings.infrastructure import get_withings_port


def get_list_workouts_use_case(
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> ListWorkoutsUseCase:
    return ListWorkoutsUseCase(repository)


def get_sync_workout_metrics_use_case(
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> SyncWorkoutMetricsUseCase:
    return SyncWorkoutMetricsUseCase(repository)


def get_create_manual_workout_use_case(
    repository: WorkoutRepository = Depends(get_workout_repository),
) -> CreateManualWorkoutUseCase:
    return CreateManualWorkoutUseCase(repository)


def get_create_nutrition_entry_use_case(
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> CreateNutritionEntryUseCase:
    return CreateNutritionEntryUseCase(repository)


def get_daily_nutrition_entries_use_case(
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> GetDailyNutritionEntriesUseCase:
    return GetDailyNutritionEntriesUseCase(repository)


def get_nutrition_entries_by_period_use_case(
    repository: NutritionRepository = Depends(get_nutrition_repository),
) -> GetNutritionEntriesByPeriodUseCase:
    return GetNutritionEntriesByPeriodUseCase(repository)


def get_list_body_measurements_use_case(
    port: WithingsMeasurementsPort = Depends(get_withings_port),
) -> ListBodyMeasurementsUseCase:
    return ListBodyMeasurementsUseCase(port)


def get_summary_advice_use_case(
    withings_port: WithingsMeasurementsPort = Depends(get_withings_port),
    nutrition_repository: NutritionRepository = Depends(get_nutrition_repository),
    workout_repository: WorkoutRepository = Depends(get_workout_repository),
) -> GetSummaryAdviceUseCase:
    return GetSummaryAdviceUseCase(
        withings_port=withings_port,
        nutrition_repository=nutrition_repository,
        workout_repository=workout_repository,
    )


__all__ = [
    "get_list_workouts_use_case",
    "get_sync_workout_metrics_use_case",
    "get_create_manual_workout_use_case",
    "get_create_nutrition_entry_use_case",
    "get_daily_nutrition_entries_use_case",
    "get_nutrition_entries_by_period_use_case",
    "get_list_body_measurements_use_case",
    "get_summary_advice_use_case",
]
