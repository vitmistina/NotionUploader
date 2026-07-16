"""Coverage-aware direct joins between nutrition, body, and training facts."""

from __future__ import annotations

from datetime import date

from ...models.advice_context import (
    AnalysisWindow,
    BodyAnalysis,
    CrossDomainAnalysis,
    DailyCrossDomainSummary,
    NutritionAnalysis,
    TrainingAnalysis,
)


def analyze_cross_domain(
    nutrition: NutritionAnalysis,
    body: BodyAnalysis,
    training: TrainingAnalysis,
    window: AnalysisWindow,
) -> CrossDomainAnalysis:
    """Join same-day values and calculate energy availability only with complete inputs."""
    nutrition_by_date = {day.date: day for day in nutrition.daily}
    training_by_date = {day.date: day for day in training.daily}
    body_by_date = {day.date: day for day in body.daily}
    daily: list[DailyCrossDomainSummary] = []
    for day in window.calendar_days:
        nutrition_day = nutrition_by_date[day]
        training_day = training_by_date.get(day)
        workout_count = training_day.workout_count if training_day else 0
        duration = training_day.duration_s if training_day else 0.0
        exercise_kcal = training_day.kcal if training_day else (0.0 if workout_count == 0 else None)
        coverage = training_day_kcal_coverage(training_day, training)
        ffm_date, ffm = _latest_ffm(day, body_by_date)
        complete = (
            nutrition_day.calories_kcal is not None
            and exercise_kcal is not None
            and coverage == 1.0
            and ffm is not None
        )
        net = (
            nutrition_day.calories_kcal - exercise_kcal
            if nutrition_day.calories_kcal is not None and exercise_kcal is not None
            else None
        )
        screening = net / ffm if complete and net is not None and ffm else None
        daily.append(
            DailyCrossDomainSummary(
                date=day,
                nutrition_recorded=nutrition_day.has_entries,
                workout_count=workout_count,
                workout_duration_s=duration,
                exercise_kcal=exercise_kcal,
                exercise_kcal_coverage_ratio=coverage,
                intake_kcal=nutrition_day.calories_kcal,
                protein_g=nutrition_day.protein_g,
                carbs_g=nutrition_day.carbs_g,
                net_intake_after_recorded_exercise_kcal=net,
                screening_energy_availability_kcal_per_kg_ffm=screening,
                energy_availability_inputs_complete=complete,
                fat_free_mass_date=ffm_date,
                fat_free_mass_kg=ffm,
            )
        )
    return CrossDomainAnalysis(daily=daily)


def training_day_kcal_coverage(day: object | None, training: TrainingAnalysis) -> float:
    """Return the fraction of workouts with an exercise-calorie value."""
    if day is None:
        return 1.0
    workout_count = getattr(day, "workout_count", 0)
    if workout_count == 0:
        return 1.0
    training_day = next(
        (item for item in training.daily if item.date == getattr(day, "date")), None
    )
    if training_day is None:
        return 0.0
    workouts = [
        workout for workout in training.workouts if workout.date[:10] == str(training_day.date)
    ]
    if not workouts:
        return 0.0
    return sum(workout.kcal is not None for workout in workouts) / len(workouts)


def _latest_ffm(day: date, body_by_date: dict[date, object]) -> tuple[date | None, float | None]:
    candidates = [
        (measurement_date, getattr(item.representative, "fat_free_mass_kg", None))
        for measurement_date, item in body_by_date.items()
        if measurement_date <= day
        and getattr(item.representative, "fat_free_mass_kg", None) is not None
    ]
    return max(candidates, key=lambda item: item[0]) if candidates else (None, None)


__all__ = ["analyze_cross_domain", "training_day_kcal_coverage"]
