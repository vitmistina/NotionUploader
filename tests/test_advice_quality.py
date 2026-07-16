from datetime import date

from src.domain.advice.quality import merge_quality_issues
from src.models.advice_context import DataQualityIssue


def test_quality_issues_merge_dates_for_same_identity() -> None:
    issues = [
        DataQualityIssue(
            code="NUTRITION_MISSING_DATES",
            domain="nutrition",
            severity="info",
            message="missing",
            affected_dates=[date(2026, 7, 14)],
        ),
        DataQualityIssue(
            code="NUTRITION_MISSING_DATES",
            domain="nutrition",
            severity="info",
            message="missing",
            affected_dates=[date(2026, 7, 15)],
        ),
    ]

    merged = merge_quality_issues(issues)

    assert len(merged) == 1
    assert merged[0].affected_dates == [date(2026, 7, 14), date(2026, 7, 15)]
