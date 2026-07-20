from datetime import datetime, timezone

from src.domain.advice.body import analyze_body
from src.domain.advice.window import build_analysis_window
from src.models.body import BodyMeasurement


def _measurement(day: int, weight: float, fat_mass: float | None = 10.0) -> BodyMeasurement:
    return BodyMeasurement(
        measurement_time=datetime(2026, 7, day, 7, tzinfo=timezone.utc),
        weight_kg=weight,
        fat_mass_kg=fat_mass,
        muscle_mass_kg=50,
        bone_mass_kg=3,
        hydration_kg=40,
        fat_free_mass_kg=55,
        body_fat_percent=15,
        device_name="Scale",
    )


def test_body_duplicate_days_use_median_without_zero_filling() -> None:
    window = build_analysis_window(
        days=4,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    analysis, issues = analyze_body(
        [_measurement(14, 70), _measurement(14, 72), _measurement(15, 71, None)], window
    )

    assert analysis.daily[0].measurement_count == 2
    assert analysis.daily[0].representative.weight_kg == 71
    assert analysis.daily[1].representative.fat_mass_kg is None
    assert "BODY_DUPLICATE_DAILY_MEASUREMENTS" in {issue.code for issue in issues}
