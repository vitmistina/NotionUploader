from datetime import datetime, timedelta

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import add_moving_average
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
