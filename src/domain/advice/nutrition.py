"""Deterministic nutrition coverage, reconciliation, and target analysis."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from ...models.advice_context import (
    AdviceAthleteProfile,
    AnalysisWindow,
    DataQualityIssue,
    NutritionAnalysis,
    NutritionCoverage,
    NutritionDayAnalysis,
    NutritionTargetComparison,
    NutritionTargetMetric,
)
from ...models.nutrition import NutritionEntry
from .statistics import distribution, percentage_difference

MACRO_MISMATCH_MIN_KCAL = 100.0
MACRO_MISMATCH_RATIO = 0.10


def analyze_nutrition(
    entries: Iterable[NutritionEntry],
    window: AnalysisWindow,
    profile: AdviceAthleteProfile | None = None,
    *,
    include_entries: bool = True,
) -> tuple[NutritionAnalysis, list[DataQualityIssue]]:
    """Build one nutrition record for every requested calendar date."""
    grouped: dict[date, list[NutritionEntry]] = defaultdict(list)
    for entry in entries:
        entry_date = entry.date if isinstance(entry.date, date) else date.fromisoformat(entry.date)
        if window.start_date <= entry_date <= window.end_date:
            grouped[entry_date].append(entry)

    daily: list[NutritionDayAnalysis] = []
    issues: list[DataQualityIssue] = []
    for day in window.calendar_days:
        day_entries = grouped.get(day, [])
        has_entries = bool(day_entries)
        calories = sum(entry.calories for entry in day_entries) if has_entries else None
        protein = sum(entry.protein_g for entry in day_entries) if has_entries else None
        carbs = sum(entry.carbs_g for entry in day_entries) if has_entries else None
        fat = sum(entry.fat_g for entry in day_entries) if has_entries else None
        macro_energy = 4 * protein + 4 * carbs + 9 * fat if has_entries else None
        unattributed = (
            calories - macro_energy if calories is not None and macro_energy is not None else None
        )
        ratio = unattributed / calories if unattributed is not None and calories else None
        protein_by_meal: dict[str, float] = defaultdict(float)
        carbs_by_meal: dict[str, float] = defaultdict(float)
        for entry in day_entries:
            protein_by_meal[entry.meal_type] += entry.protein_g
            carbs_by_meal[entry.meal_type] += entry.carbs_g
        daily.append(
            NutritionDayAnalysis(
                date=day,
                has_entries=has_entries,
                is_current_day=day == window.current_local_date,
                entry_count=len(day_entries),
                observed_meal_types=sorted({entry.meal_type for entry in day_entries}),
                calories_kcal=calories,
                protein_g=protein,
                carbs_g=carbs,
                fat_g=fat,
                macro_energy_kcal=macro_energy,
                unattributed_energy_kcal=unattributed,
                unattributed_energy_ratio=ratio,
                protein_by_meal_type_g=dict(sorted(protein_by_meal.items())),
                carbs_by_meal_type_g=dict(sorted(carbs_by_meal.items())),
                entries=day_entries if include_entries else [],
            )
        )
        if unattributed is not None and abs(unattributed) >= max(
            MACRO_MISMATCH_MIN_KCAL, MACRO_MISMATCH_RATIO * max(calories or 0, 0)
        ):
            issues.append(
                DataQualityIssue(
                    code="NUTRITION_MACRO_ENERGY_MISMATCH",
                    domain="nutrition",
                    severity="warning",
                    message="Logged calories do not reconcile with logged macro energy.",
                    affected_dates=[day],
                    details={
                        "logged_calories_kcal": calories,
                        "macro_energy_kcal": macro_energy,
                        "unattributed_energy_kcal": unattributed,
                    },
                )
            )

    missing_dates = [day for day in window.calendar_days if not grouped.get(day)]
    if missing_dates:
        issues.append(
            DataQualityIssue(
                code="NUTRITION_MISSING_DATES",
                domain="nutrition",
                severity="info",
                message="No nutrition entries were returned for these calendar dates.",
                affected_dates=missing_dates,
                details={"count": len(missing_dates)},
            )
        )
    if grouped.get(window.current_local_date):
        issues.append(
            DataQualityIssue(
                code="NUTRITION_CURRENT_DAY_PARTIAL",
                domain="nutrition",
                severity="info",
                message=(
                    "The current local day is excluded from historical statistics "
                    "and may be incomplete."
                ),
                affected_dates=[window.current_local_date],
            )
        )

    recorded_past_days = [
        day for day in window.calendar_days if day < window.current_local_date and grouped.get(day)
    ]
    excluded = [day for day in window.calendar_days if day not in recorded_past_days]
    values: dict[str, list[tuple[date, float]]] = {
        "calories_kcal": [
            (day, float(sum(e.calories for e in grouped[day]))) for day in recorded_past_days
        ],
        "protein_g": [(day, sum(e.protein_g for e in grouped[day])) for day in recorded_past_days],
        "carbs_g": [(day, sum(e.carbs_g for e in grouped[day])) for day in recorded_past_days],
        "fat_g": [(day, sum(e.fat_g for e in grouped[day])) for day in recorded_past_days],
    }
    coverage = NutritionCoverage(
        requested_days=window.requested_days,
        days_with_entries=sum(bool(grouped.get(day)) for day in window.calendar_days),
        days_without_entries=len(missing_dates),
        recorded_day_ratio=sum(bool(grouped.get(day)) for day in window.calendar_days)
        / window.requested_days,
        missing_dates=missing_dates,
        statistics_excluded_dates=excluded,
    )
    profile = profile or AdviceAthleteProfile()
    target_comparison = _target_comparison(values, profile)
    analysis = NutritionAnalysis(
        coverage=coverage,
        daily=daily,
        recorded_past_day_statistics={key: distribution(series) for key, series in values.items()},
        target_comparison=target_comparison,
    )
    return analysis, issues


def _target_comparison(
    values: dict[str, list[tuple[date, float]]], profile: AdviceAthleteProfile
) -> NutritionTargetComparison | None:
    specs = {
        "protein_min_g": ("protein_g", profile.protein_min_g, "min"),
        "protein_target_g": ("protein_g", profile.protein_target_g, "target"),
        "calorie_target_kcal": ("calories_kcal", profile.calorie_target_kcal, "target"),
        "fat_min_g": ("fat_g", profile.fat_min_g, "min"),
        "fat_max_g": ("fat_g", profile.fat_max_g, "max"),
    }
    comparisons: dict[str, NutritionTargetMetric | None] = {}
    for name, (field, target, kind) in specs.items():
        if target is None:
            comparisons[name] = None
            continue
        series = values[field]
        average = sum(value for _, value in series) / len(series) if series else None
        if kind == "min":
            meeting = sum(value >= target for _, value in series)
        elif kind == "max":
            meeting = sum(value <= target for _, value in series)
        else:
            meeting = sum(abs(value - target) <= max(1.0, target * 0.05) for _, value in series)
        comparisons[name] = NutritionTargetMetric(
            target=target,
            average_recorded_value=average,
            absolute_difference=average - target if average is not None else None,
            percentage_difference=percentage_difference(average, target),
            days_meeting_target=meeting,
            recorded_day_count=len(series),
            meeting_ratio=meeting / len(series) if series else None,
        )
    return (
        NutritionTargetComparison(**comparisons)
        if any(value is not None for value in comparisons.values())
        else None
    )


__all__ = ["MACRO_MISMATCH_MIN_KCAL", "MACRO_MISMATCH_RATIO", "analyze_nutrition"]
