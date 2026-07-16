from datetime import date, datetime, timezone

from src.domain.advice.nutrition import analyze_nutrition
from src.domain.advice.window import build_analysis_window
from src.models.nutrition import NutritionEntry


def test_nutrition_is_calendar_complete_and_excludes_current_day() -> None:
    window = build_analysis_window(
        days=3,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    entries = [
        NutritionEntry(
            food_item="Dinner",
            date=date(2026, 7, 15),
            calories=600,
            protein_g=40,
            carbs_g=50,
            fat_g=10,
            meal_type="Dinner",
            notes="logged",
        ),
        NutritionEntry(
            food_item="Breakfast",
            date=date(2026, 7, 16),
            calories=100,
            protein_g=10,
            carbs_g=10,
            fat_g=1,
            meal_type="Breakfast",
            notes="partial",
        ),
    ]

    analysis, issues = analyze_nutrition(entries, window)

    assert len(analysis.daily) == 3
    assert analysis.daily[0].calories_kcal is None
    assert analysis.coverage.days_without_entries == 1
    assert analysis.recorded_past_day_statistics["protein_g"].count == 1
    assert analysis.daily[-1].is_current_day is True
    assert {issue.code for issue in issues} >= {
        "NUTRITION_MISSING_DATES",
        "NUTRITION_CURRENT_DAY_PARTIAL",
        "NUTRITION_MACRO_ENERGY_MISMATCH",
    }
