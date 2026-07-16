"""Typed, deterministic evidence returned by the advice-context endpoint."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .body import BodyMeasurement, LinearRegressionResult
from .nutrition import NutritionEntry
from .workout import WorkoutLog

SourceName = Literal["nutrition", "withings", "workouts", "athlete_profile"]
SourceState = Literal["ok", "unavailable", "partial"]
QualityDomain = Literal["nutrition", "body", "training", "profile", "cross_domain"]
QualitySeverity = Literal["info", "warning", "critical"]
SportGroup = Literal["cycling", "strength", "walking", "running", "other"]
LoadFamily = Literal[
    "provider_training_load",
    "power_derived_tss",
    "hr_estimated_load",
    "manual_load",
    "unknown_load",
]


class AnalysisWindow(BaseModel):
    """The one inclusive local-calendar window used by every source."""

    timezone: str
    start_date: date
    end_date: date
    requested_days: int = Field(..., ge=1, le=90)
    calendar_days: list[date]
    current_local_date: date
    includes_current_day: bool


class SourceStatus(BaseModel):
    """Availability and safe diagnostics for one upstream source."""

    source: SourceName
    status: SourceState
    record_count: int = Field(ge=0)
    error_code: str | None = None


class DataQualityIssue(BaseModel):
    """A stable, actionable data-quality observation."""

    code: str
    domain: QualityDomain
    severity: QualitySeverity
    message: str
    affected_dates: list[date] = Field(default_factory=list)
    affected_record_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class AdviceAthleteProfile(BaseModel):
    """Profile values and optional configured targets used by analysis."""

    ftp: float | None = None
    weight: float | None = None
    max_hr: float | None = None
    protein_min_g: float | None = None
    protein_target_g: float | None = None
    calorie_target_kcal: float | None = None
    fat_min_g: float | None = None
    fat_max_g: float | None = None
    weekly_cycling_hours_target: float | None = None
    weekly_cycling_load_target: float | None = None
    weekly_strength_sessions_target: int | None = None
    resting_hr: float | None = None
    timezone: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Provide a small mapping-compatible shim for legacy metric code."""
        return getattr(self, key, default)


class NumericDistribution(BaseModel):
    """Descriptive statistics for one recorded-day nutrition series."""

    count: int = Field(ge=0)
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    minimum: float | None = None
    minimum_date: date | None = None
    maximum: float | None = None
    maximum_date: date | None = None


class NutritionDayAnalysis(BaseModel):
    """Nutrition evidence for exactly one calendar day."""

    date: date
    has_entries: bool
    is_current_day: bool
    entry_count: int = Field(ge=0)
    observed_meal_types: list[str] = Field(default_factory=list)
    calories_kcal: int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    macro_energy_kcal: float | None = None
    unattributed_energy_kcal: float | None = None
    unattributed_energy_ratio: float | None = None
    protein_by_meal_type_g: dict[str, float] = Field(default_factory=dict)
    carbs_by_meal_type_g: dict[str, float] = Field(default_factory=dict)
    entries: list[NutritionEntry] = Field(default_factory=list)


class NutritionCoverage(BaseModel):
    """Coverage facts for the requested nutrition window."""

    requested_days: int
    days_with_entries: int
    days_without_entries: int
    recorded_day_ratio: float
    missing_dates: list[date] = Field(default_factory=list)
    statistics_excluded_dates: list[date] = Field(default_factory=list)


class NutritionTargetMetric(BaseModel):
    """Comparison of a target against recorded past-day values."""

    target: float
    average_recorded_value: float | None = None
    absolute_difference: float | None = None
    percentage_difference: float | None = None
    days_meeting_target: int = 0
    recorded_day_count: int = 0
    meeting_ratio: float | None = None


class NutritionTargetComparison(BaseModel):
    """Available nutrition target comparisons, without qualitative labels."""

    protein_min_g: NutritionTargetMetric | None = None
    protein_target_g: NutritionTargetMetric | None = None
    calorie_target_kcal: NutritionTargetMetric | None = None
    fat_min_g: NutritionTargetMetric | None = None
    fat_max_g: NutritionTargetMetric | None = None


class NutritionAnalysis(BaseModel):
    coverage: NutritionCoverage
    daily: list[NutritionDayAnalysis]
    recorded_past_day_statistics: dict[str, NumericDistribution] = Field(default_factory=dict)
    target_comparison: NutritionTargetComparison | None = None


class BodyDailyAnalysis(BaseModel):
    date: date
    measurement_count: int
    representative: BodyMeasurement


class BodyAnalysis(BaseModel):
    daily: list[BodyDailyAnalysis] = Field(default_factory=list)
    measurements: list[BodyMeasurement] = Field(default_factory=list)
    trends: dict[str, LinearRegressionResult] = Field(default_factory=dict)
    moving_average_7d: dict[str, float | None] | None = None


class DailyTrainingSummary(BaseModel):
    date: date
    workout_count: int
    duration_s: float
    distance_m: float
    elevation_m: float
    kcal: float | None = None
    load_by_family: dict[LoadFamily, float] = Field(default_factory=dict)


class TrainingWindowSummary(BaseModel):
    start_date: date
    end_date: date
    calendar_days: int
    training_days: int
    duration_hours_by_sport: dict[SportGroup, float] = Field(default_factory=dict)
    workout_count_by_sport: dict[SportGroup, int] = Field(default_factory=dict)
    load_by_family: dict[LoadFamily, float] = Field(default_factory=dict)
    exercise_kcal_sum: float | None = None
    exercise_kcal_coverage_ratio: float
    longest_training_streak_days: int
    longest_rest_gap_days: int


class LoadConcentration(BaseModel):
    sport_group: SportGroup
    load_family: LoadFamily
    recent_window_days: int
    recent_load: float
    full_window_load: float
    recent_share_of_full_window: float | None = None


class TrainingAnalysis(BaseModel):
    daily: list[DailyTrainingSummary] = Field(default_factory=list)
    workouts: list[WorkoutLog] = Field(default_factory=list)
    windows: list[TrainingWindowSummary] = Field(default_factory=list)
    load_concentration: list[LoadConcentration] = Field(default_factory=list)


class DailyCrossDomainSummary(BaseModel):
    date: date
    nutrition_recorded: bool
    workout_count: int
    workout_duration_s: float
    exercise_kcal: float | None = None
    exercise_kcal_coverage_ratio: float
    intake_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    net_intake_after_recorded_exercise_kcal: float | None = None
    screening_energy_availability_kcal_per_kg_ffm: float | None = None
    energy_availability_inputs_complete: bool
    fat_free_mass_date: date | None = None
    fat_free_mass_kg: float | None = None


class CrossDomainAnalysis(BaseModel):
    daily: list[DailyCrossDomainSummary] = Field(default_factory=list)


class AdviceContext(BaseModel):
    """LLM-facing deterministic analytical context."""

    context_version: Literal["2.0"] = "2.0"
    generated_at: datetime
    window: AnalysisWindow
    source_status: list[SourceStatus]
    athlete_profile: AdviceAthleteProfile
    nutrition: NutritionAnalysis
    body: BodyAnalysis
    training: TrainingAnalysis
    cross_domain: CrossDomainAnalysis
    quality_issues: list[DataQualityIssue] = Field(default_factory=list)


__all__ = [
    "AdviceAthleteProfile",
    "AdviceContext",
    "AnalysisWindow",
    "BodyAnalysis",
    "BodyDailyAnalysis",
    "CrossDomainAnalysis",
    "DailyCrossDomainSummary",
    "DailyTrainingSummary",
    "DataQualityIssue",
    "LoadConcentration",
    "LoadFamily",
    "NumericDistribution",
    "NutritionAnalysis",
    "NutritionCoverage",
    "NutritionDayAnalysis",
    "NutritionTargetComparison",
    "NutritionTargetMetric",
    "SourceStatus",
    "TrainingAnalysis",
    "TrainingWindowSummary",
]
