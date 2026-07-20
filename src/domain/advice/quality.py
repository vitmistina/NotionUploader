"""Helpers for stable data-quality issue construction and de-duplication."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from ...models.advice_context import DataQualityIssue


def merge_quality_issues(issues: list[DataQualityIssue]) -> list[DataQualityIssue]:
    """Merge only semantically identical issues while preserving first-seen order."""
    merged: dict[tuple[Any, ...], DataQualityIssue] = {}
    for issue in issues:
        key = (
            issue.code,
            issue.domain,
            issue.severity,
            issue.message,
            tuple(issue.affected_record_ids),
            _canonical(issue.details),
        )
        if key not in merged:
            merged[key] = issue.model_copy(deep=True)
            continue
        existing = merged[key]
        existing.affected_dates = sorted(set(existing.affected_dates + issue.affected_dates))
    return list(merged.values())


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple((key, _canonical(value[key])) for key in sorted(value))
    if isinstance(value, list):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


__all__ = ["merge_quality_issues"]
