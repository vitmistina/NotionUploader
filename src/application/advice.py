from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Awaitable, Callable, List, Sequence, Tuple

from ..domain.body_metrics.regression import linear_regression
from ..domain.nutrition.summaries import get_daily_nutrition_summaries
from ..models.advice import SummaryAdvice
from ..models.body import BodyMeasurement, BodyMetricTrends
from ..models.nutrition import DailyNutritionSummaryWithEntries
from ..models.time import get_local_time
from ..notion.application.ports import NutritionRepository, WorkoutRepository
from ..withings.application import WithingsMeasurementsPort, fetch_withings_measurements

NutritionSummariesFetcher = Callable[
    [str, str, NutritionRepository],
    Awaitable[List[DailyNutritionSummaryWithEntries]],
]
MeasurementsFetcher = Callable[[WithingsMeasurementsPort, int], Awaitable[List[BodyMeasurement]]]
RegressionCalculator = Callable[[Sequence[BodyMeasurement]], dict]
TimeProvider = Callable[[str], Tuple[str, str]]


@dataclass
class GetSummaryAdviceUseCase:
    """Aggregate nutrition, workout, and body data into a summary advice DTO."""

    withings_port: WithingsMeasurementsPort
    nutrition_repository: NutritionRepository
    workout_repository: WorkoutRepository
    measurements_fetcher: MeasurementsFetcher = fetch_withings_measurements
    nutrition_fetcher: NutritionSummariesFetcher = get_daily_nutrition_summaries
    regression_calculator: RegressionCalculator = linear_regression
    time_provider: TimeProvider = get_local_time

    async def __call__(self, days: int, timezone: str) -> SummaryAdvice:
        end = date.today()
        start = end - timedelta(days=days - 1)
        nutrition_coro = self.nutrition_fetcher(
            start.isoformat(), end.isoformat(), self.nutrition_repository
        )
        metrics_coro = self.measurements_fetcher(self.withings_port, days)
        workouts_coro = self.workout_repository.list_recent_workouts(days)
        athlete_coro = self.workout_repository.fetch_latest_athlete_profile()
        nutrition, metrics, workouts, athlete_metrics = await asyncio.gather(
            nutrition_coro, metrics_coro, workouts_coro, athlete_coro
        )
        trends = BodyMetricTrends(**self.regression_calculator(metrics))
        local_time, part = self.time_provider(timezone)
        return SummaryAdvice(
            nutrition=nutrition,
            metrics=metrics,
            metric_trends=trends,
            workouts=workouts,
            athlete_metrics=athlete_metrics,
            local_time=local_time,
            part_of_day=part,
        )


__all__ = ["GetSummaryAdviceUseCase"]
