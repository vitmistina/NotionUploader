"""Small dependency-free statistical primitives."""

from __future__ import annotations

from datetime import date
from statistics import mean, median, pstdev
from typing import Iterable

from ...models.advice_context import NumericDistribution


def distribution(values: Iterable[tuple[date, float]]) -> NumericDistribution:
    """Calculate population descriptive statistics and date-indexed extrema."""
    pairs = list(values)
    if not pairs:
        return NumericDistribution(count=0)
    numbers = [value for _, value in pairs]
    minimum = min(numbers)
    maximum = max(numbers)
    return NumericDistribution(
        count=len(numbers),
        mean=mean(numbers),
        median=median(numbers),
        standard_deviation=pstdev(numbers),
        minimum=minimum,
        minimum_date=next(day for day, value in pairs if value == minimum),
        maximum=maximum,
        maximum_date=next(day for day, value in pairs if value == maximum),
    )


def percentage_difference(value: float | None, target: float) -> float | None:
    """Return percentage difference from target, or null for a zero target."""
    if value is None or target == 0:
        return None
    return (value - target) / target * 100


def safe_population_standard_deviation(values: Iterable[float]) -> float | None:
    """Return population standard deviation for a non-empty sequence."""
    numbers = list(values)
    return pstdev(numbers) if numbers else None


__all__ = ["distribution", "percentage_difference", "safe_population_standard_deviation"]
