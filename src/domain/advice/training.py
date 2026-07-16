"""Deterministic workout grouping, additive totals, and load provenance."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable

from ...models.advice_context import (
    AnalysisWindow,
    DailyTrainingSummary,
    DataQualityIssue,
    LoadConcentration,
    TrainingAnalysis,
    TrainingWindowSummary,
)
from ...models.workout import WorkoutLog


def analyze_training(
    workouts: Iterable[WorkoutLog], window: AnalysisWindow
) -> tuple[TrainingAnalysis, list[DataQualityIssue]]:
    """Calculate additive workout facts without combining incompatible load families."""
    selected = [
        workout
        for workout in workouts
        if window.start_date <= _workout_date(workout) <= window.end_date
    ]
    daily_by_date: dict[date, list[WorkoutLog]] = defaultdict(list)
    for workout in selected:
        daily_by_date[_workout_date(workout)].append(workout)
    daily = [_daily_summary(day, daily_by_date[day]) for day in sorted(daily_by_date)]
    windows: list[TrainingWindowSummary] = []
    for size in (4, 7, 14, 28):
        if window.requested_days >= size:
            start = window.end_date - timedelta(days=size - 1)
            windows.append(
                _window_summary(
                    start, window.end_date, [w for w in selected if start <= _workout_date(w)]
                ),
            )
    windows.append(_window_summary(window.start_date, window.end_date, selected))
    concentrations = _concentrations(selected, window)
    issues: list[DataQualityIssue] = []
    families = {
        family for workout in selected if (family := _load_family(workout)) != "unknown_load"
    }
    if len(families) > 1:
        issues.append(
            DataQualityIssue(
                code="TRAINING_MIXED_LOAD_FAMILIES",
                domain="training",
                severity="warning",
                message=(
                    "Workouts contain more than one load family; family totals remain separate."
                ),
                details={"load_families": sorted(families)},
            )
        )
    estimated = [workout for workout in selected if _load_family(workout) == "hr_estimated_load"]
    if estimated:
        issues.append(
            DataQualityIssue(
                code="TRAINING_ESTIMATED_METRICS_PRESENT",
                domain="training",
                severity="info",
                message=(
                    "Some workout loads are estimated from heart rate rather than "
                    "supplied by a power provider."
                ),
                affected_record_ids=[workout.page_id for workout in estimated],
            )
        )
    unavailable = [workout.page_id for workout in selected if workout.tss is None]
    if unavailable:
        issues.append(
            DataQualityIssue(
                code="TRAINING_NON_ADDITIVE_METRICS",
                domain="training",
                severity="info",
                message="Some workouts have no available additive training-load value.",
                affected_record_ids=unavailable,
            )
        )
    return TrainingAnalysis(
        daily=daily, workouts=selected, windows=windows, load_concentration=concentrations
    ), issues


def _daily_summary(day: date, workouts: list[WorkoutLog]) -> DailyTrainingSummary:
    loads: dict[str, float] = defaultdict(float)
    for workout in workouts:
        if workout.tss is not None:
            loads[_load_family(workout)] += workout.tss
    kcal_values = [workout.kcal for workout in workouts if workout.kcal is not None]
    return DailyTrainingSummary(
        date=day,
        workout_count=len(workouts),
        duration_s=sum(workout.duration_s for workout in workouts),
        distance_m=sum(workout.distance_m for workout in workouts),
        elevation_m=sum(workout.elevation_m for workout in workouts),
        kcal=sum(kcal_values) if len(kcal_values) == len(workouts) else None,
        load_by_family=loads,
    )


def _window_summary(start: date, end: date, workouts: list[WorkoutLog]) -> TrainingWindowSummary:
    duration: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    loads: dict[str, float] = defaultdict(float)
    for workout in workouts:
        sport = _sport_group(workout)
        duration[sport] += workout.duration_s / 3600
        counts[sport] += 1
        if workout.tss is not None:
            loads[_load_family(workout)] += workout.tss
    kcal_values = [workout.kcal for workout in workouts if workout.kcal is not None]
    training_days = {_workout_date(workout) for workout in workouts}
    return TrainingWindowSummary(
        start_date=start,
        end_date=end,
        calendar_days=(end - start).days + 1,
        training_days=len(training_days),
        duration_hours_by_sport=duration,
        workout_count_by_sport=counts,
        load_by_family=loads,
        exercise_kcal_sum=sum(kcal_values) if kcal_values else None,
        exercise_kcal_coverage_ratio=(len(kcal_values) / len(workouts)) if workouts else 0.0,
        longest_training_streak_days=_longest_training_streak(training_days),
        longest_rest_gap_days=_longest_rest_gap(start, end, training_days),
    )


def _concentrations(workouts: list[WorkoutLog], window: AnalysisWindow) -> list[LoadConcentration]:
    recent_days = 4 if window.requested_days >= 4 else window.requested_days
    recent_start = window.end_date - timedelta(days=recent_days - 1)
    pairs = {
        (_sport_group(workout), _load_family(workout))
        for workout in workouts
        if workout.tss is not None
    }
    result: list[LoadConcentration] = []
    for sport, family in sorted(pairs):
        full = sum(
            workout.tss or 0
            for workout in workouts
            if _sport_group(workout) == sport and _load_family(workout) == family
        )
        recent = sum(
            workout.tss or 0
            for workout in workouts
            if recent_start <= _workout_date(workout)
            and _sport_group(workout) == sport
            and _load_family(workout) == family
        )
        result.append(
            LoadConcentration(
                sport_group=sport,
                load_family=family,
                recent_window_days=recent_days,
                recent_load=recent,
                full_window_load=full,
                recent_share_of_full_window=recent / full if full else None,
            )
        )
    return result


def _workout_date(workout: WorkoutLog) -> date:
    return date.fromisoformat(workout.date[:10])


def _sport_group(workout: WorkoutLog) -> str:
    value = workout.type.casefold()
    if any(token in value for token in ("ride", "cycling", "bike", "virtual")):
        return "cycling"
    if any(token in value for token in ("strength", "gym", "weight", "workout")):
        return "strength"
    if "walk" in value:
        return "walking"
    if any(token in value for token in ("run", "jog")):
        return "running"
    return "other"


def _load_family(workout: WorkoutLog) -> str:
    if workout.load_family:
        return workout.load_family
    if workout.tss_origin == "provider":
        return "provider_training_load"
    if workout.tss_origin == "power_derived":
        return "power_derived_tss"
    if workout.tss_origin == "hr_estimated":
        return "hr_estimated_load"
    return "unknown_load"


def _longest_training_streak(days: set[date]) -> int:
    longest = current = 0
    previous: date | None = None
    for day in sorted(days):
        current = current + 1 if previous is not None and day == previous + timedelta(days=1) else 1
        longest = max(longest, current)
        previous = day
    return longest


def _longest_rest_gap(start: date, end: date, training_days: set[date]) -> int:
    rest = 0
    longest = 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        if day in training_days:
            rest = 0
        else:
            rest += 1
            longest = max(longest, rest)
    return longest


__all__ = ["analyze_training"]
