"""Daily normalization and trend calculations for body measurements."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Iterable
from zoneinfo import ZoneInfo

from ...domain.body_metrics.regression import linear_regression
from ...models.advice_context import (
    AnalysisWindow,
    BodyAnalysis,
    BodyDailyAnalysis,
    DataQualityIssue,
)
from ...models.body import BodyMeasurement

BODY_METRICS = (
    "weight_kg",
    "fat_mass_kg",
    "muscle_mass_kg",
    "bone_mass_kg",
    "hydration_kg",
    "fat_free_mass_kg",
    "body_fat_percent",
)


def analyze_body(
    measurements: Iterable[BodyMeasurement], window: AnalysisWindow
) -> tuple[BodyAnalysis, list[DataQualityIssue]]:
    """Collapse same-day readings to median representatives and trend those days equally."""
    raw = sorted(
        [
            measurement
            for measurement in measurements
            if (window.start_date <= _local_date(measurement, window.timezone) <= window.end_date)
        ],
        key=lambda item: item.measurement_time,
    )
    by_day: dict[date, list[BodyMeasurement]] = defaultdict(list)
    for measurement in raw:
        by_day[_local_date(measurement, window.timezone)].append(measurement)
    daily: list[BodyDailyAnalysis] = []
    issues: list[DataQualityIssue] = []
    for day in sorted(by_day):
        records = by_day[day]
        representative = _median_representative(records)
        daily.append(
            BodyDailyAnalysis(
                date=day, measurement_count=len(records), representative=representative
            )
        )
        if len(records) > 1:
            issues.append(
                DataQualityIssue(
                    code="BODY_DUPLICATE_DAILY_MEASUREMENTS",
                    domain="body",
                    severity="warning",
                    message=(
                        "Multiple body measurements were collapsed to one median "
                        "daily representative."
                    ),
                    affected_dates=[day],
                    affected_record_ids=[str(index) for index, _ in enumerate(records, start=1)],
                    details={"measurement_count": len(records)},
                )
            )
        missing = [metric for metric in BODY_METRICS if getattr(representative, metric) is None]
        if missing:
            issues.append(
                DataQualityIssue(
                    code="BODY_METRIC_MISSING",
                    domain="body",
                    severity="info",
                    message="One or more body metrics were unavailable for a daily representative.",
                    affected_dates=[day],
                    details={"metrics": missing},
                )
            )
    for previous, current in zip(daily, daily[1:]):
        previous_weight = previous.representative.weight_kg
        current_weight = current.representative.weight_kg
        if (
            previous_weight
            and current_weight
            and abs(current_weight - previous_weight) / previous_weight >= 0.05
        ):
            issues.append(
                DataQualityIssue(
                    code="BODY_SHORT_TERM_OUTLIER",
                    domain="body",
                    severity="info",
                    message="A daily body-weight change is unusually large and was retained.",
                    affected_dates=[current.date],
                    details={
                        "previous_date": previous.date,
                        "previous_weight_kg": previous_weight,
                        "current_weight_kg": current_weight,
                    },
                )
            )
    daily_representatives = [item.representative for item in daily]
    trends = linear_regression(daily_representatives)
    latest = daily[-1].date if daily else None
    averages = _calendar_average(daily, latest) if latest is not None else None
    return BodyAnalysis(
        daily=daily, measurements=raw, trends=trends, moving_average_7d=averages
    ), issues


def _local_date(measurement: BodyMeasurement, timezone_name: str) -> date:
    timestamp = measurement.measurement_time
    if timestamp.tzinfo is None:
        return timestamp.date()
    return timestamp.astimezone(ZoneInfo(timezone_name)).date()


def _median_representative(records: list[BodyMeasurement]) -> BodyMeasurement:
    representative = min(records, key=lambda item: item.measurement_time).model_copy(deep=True)
    for metric in BODY_METRICS:
        values = [
            getattr(record, metric) for record in records if getattr(record, metric) is not None
        ]
        setattr(representative, metric, median(values) if values else None)
    return representative


def _calendar_average(daily: list[BodyDailyAnalysis], latest: date) -> dict[str, float | None]:
    start = latest - timedelta(days=6)
    recent = [item.representative for item in daily if start <= item.date <= latest]
    return {
        metric: (
            sum(values) / len(values)
            if (
                values := [
                    getattr(item, metric) for item in recent if getattr(item, metric) is not None
                ]
            )
            else None
        )
        for metric in BODY_METRICS
    }


__all__ = ["analyze_body"]
