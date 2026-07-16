from datetime import datetime, timezone

from src.domain.advice.cross_domain import analyze_cross_domain
from src.domain.advice.training import analyze_training
from src.domain.advice.window import build_analysis_window
from src.models.advice_context import AdviceAthleteProfile
from src.models.workout import WorkoutLog
from src.domain.advice.nutrition import analyze_nutrition
from src.models.body import BodyMeasurement
from src.domain.advice.body import analyze_body


def _workout(
    day: str, workout_type: str, family: str, tss: float, kcal: float | None
) -> WorkoutLog:
    return WorkoutLog(
        page_id=f"{day}-{workout_type}",
        name=workout_type,
        date=day,
        duration_s=3600,
        distance_m=1000,
        elevation_m=10,
        type=workout_type,
        tss=tss,
        tss_origin="hr_estimated" if family == "hr_estimated_load" else "provider",
        load_family=family,
        kcal=kcal,
    )


def test_training_keeps_hr_load_separate_from_provider_load() -> None:
    window = build_analysis_window(
        days=7,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    training, issues = analyze_training(
        [
            _workout("2026-07-15", "Ride", "provider_training_load", 100, 500),
            _workout("2026-07-16", "Strength", "hr_estimated_load", 50, None),
        ],
        window,
    )

    assert training.windows[-1].load_by_family == {
        "provider_training_load": 100,
        "hr_estimated_load": 50,
    }
    assert "TRAINING_MIXED_LOAD_FAMILIES" in {issue.code for issue in issues}


def test_cross_domain_does_not_screen_without_complete_exercise_calories() -> None:
    window = build_analysis_window(
        days=2,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    nutrition, _ = analyze_nutrition([], window, AdviceAthleteProfile())
    training, _ = analyze_training(
        [_workout("2026-07-15", "Ride", "provider_training_load", 100, None)], window
    )
    body, _ = analyze_body(
        [
            BodyMeasurement(
                measurement_time=datetime(2026, 7, 15, 7, tzinfo=timezone.utc),
                weight_kg=70,
                fat_free_mass_kg=55,
                device_name="Scale",
            )
        ],
        window,
    )

    joined = analyze_cross_domain(nutrition, body, training, window)

    assert joined.daily[0].screening_energy_availability_kcal_per_kg_ffm is None
