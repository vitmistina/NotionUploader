"""Compatibility wrappers for nutrition utilities."""

from __future__ import annotations

from .domain.nutrition.summaries import get_daily_nutrition_summaries
from .domain.nutrition.summary import build_daily_summary

__all__ = ["build_daily_summary", "get_daily_nutrition_summaries"]
