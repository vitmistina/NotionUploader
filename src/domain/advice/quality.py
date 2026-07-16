"""Helpers for stable data-quality issue construction and de-duplication."""

from __future__ import annotations

from ...models.advice_context import DataQualityIssue


def merge_quality_issues(issues: list[DataQualityIssue]) -> list[DataQualityIssue]:
    """Merge duplicate issue identities while preserving deterministic order."""
    merged: dict[tuple[str, str, str, tuple[str, ...]], DataQualityIssue] = {}
    for issue in issues:
        key = (issue.code, issue.domain, issue.severity, tuple(issue.affected_record_ids))
        if key not in merged:
            merged[key] = issue
            continue
        existing = merged[key]
        existing.affected_dates = sorted(set(existing.affected_dates + issue.affected_dates))
        existing.details = {**existing.details, **issue.details}
    return list(merged.values())


__all__ = ["merge_quality_issues"]
