"""Linear regression helpers for body measurements."""

from __future__ import annotations

from typing import Dict, List, Optional

from ...models.body import BodyMeasurement, LinearRegressionResult


def linear_regression(
    measurements: List[BodyMeasurement],
    metrics: Optional[List[str]] = None,
) -> Dict[str, LinearRegressionResult]:
    """Compute linear regression for core body measurement metrics."""

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
