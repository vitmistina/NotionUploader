"""Canonical workout local-calendar date handling."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from ...models.workout import WorkoutLog


def workout_local_date(workout: WorkoutLog, timezone_name: str) -> date:
    if workout.start_time is not None:
        if workout.start_time.tzinfo is None or workout.start_time.utcoffset() is None:
            raise ValueError("workout start_time must be timezone-aware")
        return workout.start_time.astimezone(ZoneInfo(timezone_name)).date()
    if not isinstance(workout.date, str) or len(workout.date) < 10:
        raise ValueError("workout date is unavailable")
    return date.fromisoformat(workout.date[:10])
