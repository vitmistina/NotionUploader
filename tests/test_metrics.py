from datetime import datetime, timedelta

import pytest

from src.metrics import add_moving_average
from src.models import BodyMeasurement


def make_measurement(day: int) -> BodyMeasurement:
    base = datetime(2023, 1, 1)
    value = float(day)
    return BodyMeasurement(
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


def test_add_moving_average() -> None:
    measurements = [make_measurement(i) for i in range(1, 8)]
    result = add_moving_average(measurements)

    for i in range(6):
        assert result[i].moving_average_7d is None

    avg = result[6].moving_average_7d
    assert avg is not None
    assert avg.weight_kg == pytest.approx(4.0)
    assert avg.body_fat_percent == pytest.approx(4.0)
