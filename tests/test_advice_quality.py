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


def test_quality_issues_with_different_details_do_not_merge() -> None:
    issues = [
        DataQualityIssue(
            code="SOURCE_PARTIAL_FAILURE",
            domain="cross_domain",
            severity="warning",
            message="source unavailable",
            details={"source": "nutrition", "error_code": "UPSTREAM_UNAVAILABLE"},
        ),
        DataQualityIssue(
            code="SOURCE_PARTIAL_FAILURE",
            domain="cross_domain",
            severity="warning",
            message="source unavailable",
            details={"source": "withings", "error_code": "UPSTREAM_UNAVAILABLE"},
        ),
    ]

    merged = merge_quality_issues(issues)

    assert [item.details["source"] for item in merged] == ["nutrition", "withings"]
