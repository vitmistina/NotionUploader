from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from .models.body import (
    BodyMeasurement,
    BodyMeasurementAverages,
    LinearRegressionResult,
)


def add_moving_average(
    measurements: List[BodyMeasurement], window: int = 7
) -> List[BodyMeasurement]:
    """Attach 7-day moving averages to a list of body measurements.

    Measurements are first sorted by ``measurement_time`` and a simple moving
    average is computed for each metric. ``None`` values are ignored so missing
    data does not dilute the average. A moving average is only calculated when
    at least three non-missing values are present in the current window for
    every metric.

    Args:
        measurements: Raw body measurements.
        window: Number of measurements to consider for the moving window.
            Defaults to 7.

    Returns:
        The list of measurements with ``moving_average_7d`` populated when all
        metrics have at least three non-missing values in the current window.
    """

    metrics = [
        "weight_kg",
        "fat_mass_kg",
        "muscle_mass_kg",
        "bone_mass_kg",
        "hydration_kg",
        "fat_free_mass_kg",
        "body_fat_percent",
    ]

    sorted_measurements = sorted(
        measurements, key=lambda m: m.measurement_time
    )
    queues = {metric: deque(maxlen=window) for metric in metrics}

    min_values = 3
    for m in sorted_measurements:
        for metric in metrics:
            queues[metric].append(getattr(m, metric))

        averages: dict[str, float] = {}
        for metric in metrics:
            values = [v for v in queues[metric] if v is not None]
            if len(values) >= min_values:
                averages[metric] = sum(values) / len(values)
            else:
                break

        if len(averages) == len(metrics):
            m.moving_average_7d = BodyMeasurementAverages(**averages)
        else:
            m.moving_average_7d = None

    return sorted_measurements


def linear_regression(
    measurements: List[BodyMeasurement],
    metrics: Optional[List[str]] = None,
) -> Dict[str, LinearRegressionResult]:
    """Compute linear regression for core body measurement metrics.

    A basic least-squares regression is fit for each metric using the
    measurement time, expressed as days since the earliest measurement, as the
    independent variable. ``None`` values are ignored and a result is only
    produced when at least two valid measurements are present. The resulting
    slope therefore represents change per day.

    Args:
        measurements: Ordered body measurements.
        metrics: Optional list of metric names to evaluate. Defaults to core
            metrics: weight, body fat percent, muscle mass, and fat mass.

    Returns:
        Mapping of metric name to ``LinearRegressionResult``.
    """

    if metrics is None:
        metrics = [
            "weight_kg",
            "body_fat_percent",
            "muscle_mass_kg",
            "fat_mass_kg",
        ]

    sorted_measurements = sorted(
        measurements, key=lambda m: m.measurement_time
    )
    if not sorted_measurements:
        return {}
    start = sorted_measurements[0].measurement_time
    x_values = [
        (m.measurement_time - start).total_seconds() / 86400
        for m in sorted_measurements
    ]

    results: Dict[str, LinearRegressionResult] = {}
    for metric in metrics:
        y_values = [getattr(m, metric) for m in sorted_measurements]
        valid = [(x, y) for x, y in zip(x_values, y_values) if y is not None]
        if len(valid) < 2:
            continue
        xs, ys = zip(*valid)
        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = numerator / denominator if denominator else 0.0
        intercept = y_mean - slope * x_mean
        ss_tot = sum((y - y_mean) ** 2 for y in ys)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
        results[metric] = LinearRegressionResult(
            slope=slope, intercept=intercept, r2=r2
        )

    return results


def hr_drift_from_splits(splits: List[dict[str, Any]]) -> float:
    """Calculate heart rate drift percentage from distance splits."""

    if not splits:
        return 0.0

    half = len(splits) // 2
    if half == 0:
        return 0.0

    def average_hr(values: List[dict[str, Any]]) -> Optional[float]:
        hrs: List[float] = []
        for split in values:
            hr = split.get("average_heartrate")
            if hr is None:
                continue
            try:
                hr_value = float(hr)
            except (TypeError, ValueError):
                continue
            if hr_value <= 0:
                continue
            hrs.append(hr_value)
        if not hrs:
            return None
        return sum(hrs) / len(hrs)

    first_avg = average_hr(splits[:half])
    second_avg = average_hr(splits[half:])

    if first_avg is None or second_avg is None or first_avg == 0:
        return 0.0

    return (second_avg - first_avg) / first_avg * 100


def vo2max_minutes(
    splits: List[dict[str, Any]],
    max_hr: Optional[float],
    vo2_threshold_fraction_of_hrmax: float = 0.88,  # Lowered from 0.90 for better sensitivity
    kinetics_time_constant_seconds: float = 30.0,  # Lowered from 45.0 for faster HR response
    peak_influence_cap: float = 0.70  # Increased from 0.60 for more peak influence
) -> float:
    """
    Estimate total minutes spent at/above a VO2max heart-rate threshold from split-level data.
    
    Uses a sophisticated blended evidence approach that considers:
    1. Average heart rate as evidence of sustained time >= threshold
    2. Peak heart rate as evidence that some portion touched >= threshold
    3. Heart rate kinetics modeling to account for HR lag on short efforts
    
    Args:
        splits: List of dicts containing at least:
            - "moving_time" (seconds)
            - "average_heartrate" (bpm)
            - "max_heartrate" (bpm)
        max_hr: Athlete's maximum heart rate in bpm
        vo2_threshold_fraction_of_hrmax: VO2 threshold as fraction of HRmax (0.88-0.90)
        kinetics_time_constant_seconds: Time constant for HR lag model (30-60s typical)
        peak_influence_cap: Max contribution of peak HR evidence (0.4-0.7 typical)
    
    Returns:
        Estimated total minutes spent at/above VO2max intensity
    """
    from math import exp

    def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def relative_excess_above_threshold(x_fraction_of_hrmax: float) -> float:
        """Map HR (as fraction of HRmax) to 'excess over threshold' in [0,1]."""
        numerator = x_fraction_of_hrmax - vo2_threshold_fraction_of_hrmax
        denominator = 1.0 - vo2_threshold_fraction_of_hrmax
        if denominator <= 0:
            return 0.0
        return clamp(numerator / denominator)

    if not splits or not max_hr or max_hr <= 0:
        return 0.0

    total_vo2_seconds: float = 0.0

    for split in splits:
        lap_seconds = split.get("moving_time") or 0
        avg_hr = split.get("average_heartrate") or 0
        peak_hr = split.get("max_heartrate") or 0

        if lap_seconds <= 0 or avg_hr <= 0 or peak_hr <= 0:
            continue

        # Convert HRs to fractions of max
        avg_fraction_of_hrmax = avg_hr / max_hr
        peak_fraction_of_hrmax = peak_hr / max_hr

        # Calculate evidence from average and peak HR
        avg_evidence = relative_excess_above_threshold(avg_fraction_of_hrmax)
        peak_evidence = relative_excess_above_threshold(peak_fraction_of_hrmax)

        # Calculate HR settling factor to account for lag
        settling_factor = 1.0 - exp(-lap_seconds / kinetics_time_constant_seconds)
        settling_factor = clamp(settling_factor)

        # Blend average and peak evidence
        peak_add_back = peak_influence_cap * settling_factor * peak_evidence
        fraction_in_vo2_zone = avg_evidence + (1.0 - avg_evidence) * peak_add_back
        fraction_in_vo2_zone = clamp(fraction_in_vo2_zone)

        # Accumulate time
        total_vo2_seconds += fraction_in_vo2_zone * lap_seconds

    return total_vo2_seconds / 60.0
def estimate_if_tss_from_hr(
    *,
    hr_avg_session: Optional[float],
    hr_max_session: Optional[float],
    dur_s: Optional[float],
    hr_max_athlete: Optional[float],
    hr_rest_athlete: Optional[float] = None,
    kcal: Optional[float] = None,  # Included for signature parity / future use
) -> Optional[Tuple[float, float]]:
    """Estimate IF and TSS from heart-rate data when power metrics are absent.

    Args:
        hr_avg_session: Average heart rate during the session (bpm).
        hr_max_session: Maximum heart rate recorded for the session (bpm).
        dur_s: Activity duration in seconds.
        hr_max_athlete: Athlete's maximum heart rate (bpm).
        hr_rest_athlete: Athlete's resting heart rate (bpm). Defaults to 66 when ``None``.
        kcal: Optional calories expended (unused presently).

    Returns:
        Tuple of (intensity factor, TSS) rounded to (2, 1) decimals respectively
        when estimation is possible. Returns ``None`` if inputs are insufficient.
    """

    del kcal  # appease linters while keeping signature parity for future use

    if (
        hr_avg_session is None
        or hr_max_session is None
        or dur_s is None
        or dur_s <= 0
        or hr_max_athlete is None
    ):
        return None

    if hr_avg_session <= 0 or hr_max_session <= 0 or hr_max_athlete <= 0:
        return None

    rest_hr = (
        hr_rest_athlete if hr_rest_athlete is not None and hr_rest_athlete > 0 else 66.0
    )

    lthr_guess = 0.90 * hr_max_athlete
    lthr_candidate = min(
        lthr_guess, max(0.85 * hr_max_athlete, 0.98 * hr_max_session)
    )
    if lthr_candidate <= rest_hr + 10:
        lthr = lthr_guess
    else:
        lthr = lthr_candidate

    hr_range = max(1.0, hr_max_athlete - rest_hr)
    thr_range = max(1.0, lthr - rest_hr)

    if hr_avg_session <= rest_hr + 5:
        if_est = 0.30
    else:
        if_base = (hr_avg_session - rest_hr) / thr_range
        supra = max(0.0, hr_max_session - lthr)
        supra_cap = max(1.0, hr_max_athlete - lthr)
        bump = 0.08 * (supra / supra_cap) if supra_cap else 0.0
        if_est = max(0.30, min(1.35, if_base + bump))

    # Guard extremely low threshold spread once more after IF determination.
    if thr_range <= 1.0 and hr_range <= 1.0:
        if_est = 0.30

    tss = (dur_s / 3600.0) * if_est * 100.0
    return round(if_est, 2), round(tss, 1)

