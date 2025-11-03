"""Deprecated metrics module preserved for backwards compatibility."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from warnings import warn

from .domain.body_metrics.hr import (
    estimate_if_tss_from_hr as _estimate_if_tss_from_hr,
)
from .domain.body_metrics.hr import (
    hr_drift_from_splits as _hr_drift_from_splits,
)
from .domain.body_metrics.moving_average import (
    add_moving_average as _add_moving_average,
)
from .domain.body_metrics.regression import (
    linear_regression as _linear_regression,
)
from .domain.body_metrics.vo2 import vo2max_minutes as _vo2max_minutes
from .models.body import BodyMeasurement, LinearRegressionResult

__all__ = [
    "add_moving_average",
    "linear_regression",
    "hr_drift_from_splits",
    "vo2max_minutes",
    "estimate_if_tss_from_hr",
]


def _warn() -> None:
    warn(
        "'src.metrics' is deprecated; import from 'src.domain.body_metrics' instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def add_moving_average(
    measurements: List[BodyMeasurement], window: int = 7
) -> List[BodyMeasurement]:
    _warn()
    return _add_moving_average(measurements, window)


def linear_regression(
    measurements: List[BodyMeasurement],
    metrics: Optional[List[str]] = None,
) -> Dict[str, LinearRegressionResult]:
    _warn()
    return _linear_regression(measurements, metrics)


def hr_drift_from_splits(splits: List[dict[str, Any]]) -> float:
    _warn()
    return _hr_drift_from_splits(splits)


def vo2max_minutes(
    splits: List[dict[str, Any]],
    max_hr: Optional[float],
    vo2_threshold_fraction_of_hrmax: float = 0.88,
    kinetics_time_constant_seconds: float = 30.0,
    peak_influence_cap: float = 0.70,
) -> float:
    _warn()
    return _vo2max_minutes(
        splits,
        max_hr,
        vo2_threshold_fraction_of_hrmax=vo2_threshold_fraction_of_hrmax,
        kinetics_time_constant_seconds=kinetics_time_constant_seconds,
        peak_influence_cap=peak_influence_cap,
    )


def estimate_if_tss_from_hr(
    *,
    hr_avg_session: Optional[float],
    hr_max_session: Optional[float],
    dur_s: Optional[float],
    hr_max_athlete: Optional[float],
    hr_rest_athlete: Optional[float] = None,
    kcal: Optional[float] = None,
) -> Optional[Tuple[float, float]]:
    _warn()
    return _estimate_if_tss_from_hr(
        hr_avg_session=hr_avg_session,
        hr_max_session=hr_max_session,
        dur_s=dur_s,
        hr_max_athlete=hr_max_athlete,
        hr_rest_athlete=hr_rest_athlete,
        kcal=kcal,
    )
