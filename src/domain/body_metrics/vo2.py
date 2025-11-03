"""VO2 related calculations."""

from __future__ import annotations

from math import exp
from typing import Any, List, Optional


def vo2max_minutes(
    splits: List[dict[str, Any]],
    max_hr: Optional[float],
    vo2_threshold_fraction_of_hrmax: float = 0.88,
    kinetics_time_constant_seconds: float = 30.0,
    peak_influence_cap: float = 0.70,
) -> float:
    """Estimate total minutes spent at/above a VO2max heart-rate threshold."""

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

        avg_fraction_of_hrmax = avg_hr / max_hr
        peak_fraction_of_hrmax = peak_hr / max_hr

        avg_evidence = relative_excess_above_threshold(avg_fraction_of_hrmax)
        peak_evidence = relative_excess_above_threshold(peak_fraction_of_hrmax)

        settling_factor = 1.0 - exp(-lap_seconds / kinetics_time_constant_seconds)
        settling_factor = clamp(settling_factor)

        peak_add_back = peak_influence_cap * settling_factor * peak_evidence
        fraction_in_vo2_zone = avg_evidence + (1.0 - avg_evidence) * peak_add_back
        fraction_in_vo2_zone = clamp(fraction_in_vo2_zone)

        total_vo2_seconds += fraction_in_vo2_zone * lap_seconds

    return total_vo2_seconds / 60.0
