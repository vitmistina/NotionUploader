"""Application layer use cases coordinating domain services."""

from .advice import GetSummaryAdviceUseCase
from .metrics import ListBodyMeasurementsUseCase
from .nutrition import (
    CreateNutritionEntryUseCase,
    GetDailyNutritionEntriesUseCase,
    GetNutritionEntriesByPeriodUseCase,
)
from .workouts import (
    CreateManualWorkoutUseCase,
    ListWorkoutsUseCase,
    SyncWorkoutMetricsUseCase,
    WorkoutNotFoundError,
)

__all__ = [
    "CreateManualWorkoutUseCase",
    "ListWorkoutsUseCase",
    "SyncWorkoutMetricsUseCase",
    "WorkoutNotFoundError",
    "CreateNutritionEntryUseCase",
    "GetDailyNutritionEntriesUseCase",
    "GetNutritionEntriesByPeriodUseCase",
    "ListBodyMeasurementsUseCase",
    "GetSummaryAdviceUseCase",
]
