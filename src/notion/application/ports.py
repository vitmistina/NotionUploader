from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ...models.nutrition import NutritionEntry
from ...models.workout import WorkoutLog


@runtime_checkable
class NutritionRepository(Protocol):
    """Port defining the nutrition-facing Notion operations."""

    async def create_entry(self, entry: NutritionEntry) -> None:
        """Persist a nutrition entry."""

    async def list_entries_on_date(self, date: str) -> List[NutritionEntry]:
        """Return nutrition entries for a specific date."""

    async def list_entries_in_range(
        self, start_date: date | str, end_date: date | str
    ) -> List[NutritionEntry]:
        """Return nutrition entries between the provided dates (inclusive)."""


@runtime_checkable
class WorkoutRepository(Protocol):
    """Port defining the workout-facing Notion operations."""

    async def list_recent_workouts(self, days: int) -> List[WorkoutLog]:
        """Return workouts recorded within the trailing number of days."""

    async def list_workouts_in_range(
        self, start_date: date, end_date: date, timezone: str
    ) -> List[WorkoutLog]:
        """Return workouts in one explicit inclusive local-date range without writes."""

    async def fetch_latest_athlete_profile(self) -> Dict[str, Any]:
        """Return the most recent athlete profile metrics from Notion."""

    async def save_workout(
        self,
        detail: Dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2max: float,
        *,
        tss: Optional[float] = None,
        intensity_factor: Optional[float] = None,
    ) -> None:
        """Persist or update a workout activity in Notion."""

    async def fill_missing_metrics(self, page_id: str) -> Optional[WorkoutLog]:
        """Estimate and persist missing metrics for a workout by page id."""
