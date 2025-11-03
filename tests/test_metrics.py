from datetime import datetime, timedelta

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.body_metrics.hr import estimate_if_tss_from_hr, hr_drift_from_splits
from src.domain.body_metrics.moving_average import add_moving_average
from src.domain.body_metrics.regression import linear_regression
from src.models.body import BodyMeasurement


def make_measurement(day: int, value: float | None) -> BodyMeasurement:
    """Create a BodyMeasurement for a given day with optional value."""
    base = datetime(2025, 8, 1)
    return BodyMeasurement.model_construct(
        measurement_time=base + timedelta(days=day - 1),
        weight_kg=value,
        fat_mass_kg=value,
        muscle_mass_kg=value,
        bone_mass_kg=value,
        hydration_kg=value,
        fat_free_mass_kg=value,
        body_fat_percent=value,
        device_name="Device",
    )


def test_add_moving_average_requires_three_values() -> None:
    measurements = [make_measurement(1, 10), make_measurement(2, 20)]
    result = add_moving_average(measurements)
    assert result[-1].moving_average_7d is None


def test_add_moving_average_after_three_values() -> None:
    measurements = [
        make_measurement(1, 10),
        make_measurement(2, 20),
        make_measurement(3, 30),
    ]
    result = add_moving_average(measurements)
    avg = result[-1].moving_average_7d
    assert avg is not None
    assert avg.weight_kg == pytest.approx(20.0)


def test_add_moving_average_excludes_missing_values() -> None:
    measurements = [
        make_measurement(1, 10),
        make_measurement(2, None),
        make_measurement(3, 30),
        make_measurement(4, None),
        make_measurement(5, 50),
        make_measurement(6, None),
        make_measurement(7, 70),
    ]
    result = add_moving_average(measurements)

    avg = result[-1].moving_average_7d
    assert avg is not None
    assert avg.weight_kg == pytest.approx(40.0)
    # Only four non-missing values contribute to the average
    values = [m.weight_kg for m in measurements if m.weight_kg is not None]
    assert len(values) == 4


def test_linear_regression_perfect_trend() -> None:
    measurements = [
        make_measurement(1, 70),
        make_measurement(2, 71),
        make_measurement(3, 72),
    ]
    results = linear_regression(measurements)
    weight = results["weight_kg"]
    assert weight.slope == pytest.approx(1.0)
    assert weight.intercept == pytest.approx(70.0)
    assert weight.r2 == pytest.approx(1.0)


def test_linear_regression_ignores_missing_values() -> None:
    measurements = [
        make_measurement(1, 70),
        make_measurement(2, None),
        make_measurement(3, 72),
    ]
    results = linear_regression(measurements)
    weight = results["weight_kg"]
    assert weight.slope == pytest.approx(1.0)
    assert weight.intercept == pytest.approx(70.0)


def test_linear_regression_respects_measurement_time() -> None:
    measurements = [
        make_measurement(1, 70),
        make_measurement(3, 71),
        make_measurement(5, 72),
    ]
    results = linear_regression(measurements)
    weight = results["weight_kg"]
    # Measurements span four days with a total increase of 2 kg
    assert weight.slope == pytest.approx(0.5)
    assert weight.intercept == pytest.approx(70.0)
    assert weight.r2 == pytest.approx(1.0)


def test_hr_drift_handles_missing_values() -> None:
    splits = [
        {"average_heartrate": None},
        {"average_heartrate": 150},
        {"average_heartrate": None},
        {"average_heartrate": 155},
    ]

    drift = hr_drift_from_splits(splits)

    assert drift == pytest.approx((155 - 150) / 150 * 100)


def test_hr_drift_without_heart_rate_data_returns_zero() -> None:
    splits = [
        {"average_heartrate": None},
        {"average_heartrate": None},
    ]

    assert hr_drift_from_splits(splits) == 0.0


def test_estimate_if_tss_from_hr_returns_values() -> None:
    estimate = estimate_if_tss_from_hr(
        hr_avg_session=145,
        hr_max_session=165,
        dur_s=3600,
        hr_max_athlete=190,
        hr_rest_athlete=60,
    )

    assert estimate is not None
    if_est, tss = estimate
    assert if_est == pytest.approx(0.85, abs=0.01)
    assert tss == pytest.approx(84.5, abs=0.5)


def test_estimate_if_tss_from_hr_handles_low_effort() -> None:
    estimate = estimate_if_tss_from_hr(
        hr_avg_session=65,
        hr_max_session=90,
        dur_s=1800,
        hr_max_athlete=190,
        hr_rest_athlete=60,
    )

    assert estimate == (0.3, 15.0)


def test_estimate_if_tss_from_hr_requires_minimum_inputs() -> None:
    assert (
        estimate_if_tss_from_hr(
            hr_avg_session=None,
            hr_max_session=150,
            dur_s=1800,
            hr_max_athlete=190,
        )
        is None
    )
