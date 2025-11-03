"""FastAPI dependency wiring for application use cases."""

from __future__ import annotations

from typing import AsyncIterator

import httpx
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
from ..notion.infrastructure.nutrition_repository import create_notion_nutrition_adapter
from ..notion.infrastructure.workout_repository import create_notion_workout_adapter
from ..services.interfaces import NotionAPI
from ..services.notion import get_notion_client
from .clients import RedisClient, get_redis
from .config import Settings, get_settings
from ..strava.application import StravaActivityCoordinator
from ..strava.infrastructure.client import create_strava_client_adapter
from ..withings.application import WithingsMeasurementsPort
from ..withings.infrastructure import create_withings_measurements_adapter


def provide_nutrition_port(
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> NutritionRepository:
    return create_notion_nutrition_adapter(settings=settings, client=client)


def provide_workout_port(
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> WorkoutRepository:
    return create_notion_workout_adapter(settings=settings, client=client)


def provide_withings_port(
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> WithingsMeasurementsPort:
    return create_withings_measurements_adapter(redis=redis, settings=settings)


async def provide_strava_activity_coordinator(
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    workout_repository: WorkoutRepository = Depends(provide_workout_port),
) -> AsyncIterator[StravaActivityCoordinator]:
    async with httpx.AsyncClient() as http_client:
        client = create_strava_client_adapter(
            http_client=http_client, redis=redis, settings=settings
        )
        coordinator = StravaActivityCoordinator(client, workout_repository)
        yield coordinator


def get_list_workouts_use_case(
    repository: WorkoutRepository = Depends(provide_workout_port),
) -> ListWorkoutsUseCase:
    return ListWorkoutsUseCase(repository)


def get_sync_workout_metrics_use_case(
    repository: WorkoutRepository = Depends(provide_workout_port),
) -> SyncWorkoutMetricsUseCase:
    return SyncWorkoutMetricsUseCase(repository)


def get_create_manual_workout_use_case(
    repository: WorkoutRepository = Depends(provide_workout_port),
) -> CreateManualWorkoutUseCase:
    return CreateManualWorkoutUseCase(repository)


def get_create_nutrition_entry_use_case(
    repository: NutritionRepository = Depends(provide_nutrition_port),
) -> CreateNutritionEntryUseCase:
    return CreateNutritionEntryUseCase(repository)


def get_daily_nutrition_entries_use_case(
    repository: NutritionRepository = Depends(provide_nutrition_port),
) -> GetDailyNutritionEntriesUseCase:
    return GetDailyNutritionEntriesUseCase(repository)


def get_nutrition_entries_by_period_use_case(
    repository: NutritionRepository = Depends(provide_nutrition_port),
) -> GetNutritionEntriesByPeriodUseCase:
    return GetNutritionEntriesByPeriodUseCase(repository)


def get_list_body_measurements_use_case(
    port: WithingsMeasurementsPort = Depends(provide_withings_port),
) -> ListBodyMeasurementsUseCase:
    return ListBodyMeasurementsUseCase(port)


def get_summary_advice_use_case(
    withings_port: WithingsMeasurementsPort = Depends(provide_withings_port),
    nutrition_repository: NutritionRepository = Depends(provide_nutrition_port),
    workout_repository: WorkoutRepository = Depends(provide_workout_port),
) -> GetSummaryAdviceUseCase:
    return GetSummaryAdviceUseCase(
        withings_port=withings_port,
        nutrition_repository=nutrition_repository,
        workout_repository=workout_repository,
    )


__all__ = [
    "provide_nutrition_port",
    "provide_workout_port",
    "provide_withings_port",
    "provide_strava_activity_coordinator",
    "get_list_workouts_use_case",
    "get_sync_workout_metrics_use_case",
    "get_create_manual_workout_use_case",
    "get_create_nutrition_entry_use_case",
    "get_daily_nutrition_entries_use_case",
    "get_nutrition_entries_by_period_use_case",
    "get_list_body_measurements_use_case",
    "get_summary_advice_use_case",
]
