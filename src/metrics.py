from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from .models.body import BodyMeasurement, BodyMeasurementAverages


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


def hr_drift_from_splits(splits: List[dict[str, Any]]) -> float:
    """Calculate heart rate drift percentage from distance splits."""
    if not splits:
        return 0.0
    half = len(splits) // 2
    if half == 0:
        return 0.0
    first_avg = sum(s.get("average_heartrate", 0) for s in splits[:half]) / half
    second_avg = sum(s.get("average_heartrate", 0) for s in splits[half:]) / (len(splits) - half)
    if first_avg == 0:
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
        lap_seconds = split.get("moving_time", 0)
        avg_hr = split.get("average_heartrate", 0)
        peak_hr = split.get("max_heartrate", 0)

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
