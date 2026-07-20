"""Application orchestration for the deterministic advice context."""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException

from ..domain.advice.body import analyze_body
from ..domain.advice.cross_domain import analyze_cross_domain
from ..domain.advice.nutrition import analyze_nutrition
from ..domain.advice.quality import merge_quality_issues
from ..domain.advice.training import analyze_training
from ..domain.advice.window import (
    build_analysis_window,
    exclusive_end_utc,
    local_midnight_utc,
    utc_now,
)
from ..models.advice_context import (
    AdviceAthleteProfile,
    AdviceContext,
    DataQualityIssue,
    SourceStatus,
)
from ..models.body import BodyMeasurement
from ..models.nutrition import NutritionEntry
from ..models.workout import WorkoutLog
from ..notion.application.ports import NutritionRepository, WorkoutRepository
from ..withings.application import WithingsMeasurementsPort
from ..workout_payload.application.ports import WorkoutPayloadStore


@dataclass
class GetAdviceContextUseCase:
    """Fetch all evidence once and build a typed, partial-failure-safe context."""

    nutrition_repository: NutritionRepository
    workout_repository: WorkoutRepository
    withings_port: WithingsMeasurementsPort
    clock: Callable[[], datetime] = utc_now
    payload_store: WorkoutPayloadStore | None = None

    async def __call__(
        self,
        *,
        days: int,
        timezone: str,
        include_entries: bool = True,
        include_workout_details: bool = False,
    ) -> AdviceContext:
        """Return analytical facts for the requested local-calendar window."""
        _ = include_workout_details  # Reserved for the payload store phase.
        window = build_analysis_window(days=days, timezone_name=timezone, clock=self.clock)
        start_at = local_midnight_utc(window.start_date, timezone)
        end_at = exclusive_end_utc(window.end_date, timezone)
        results = await asyncio.gather(
            self._read_nutrition(window),
            self._read_body(start_at, end_at),
            self._read_workouts(window),
            self._read_profile(),
            return_exceptions=True,
        )
        nutrition_raw, body_raw, workouts_raw, profile_raw = results
        analytical_results = (nutrition_raw, body_raw, workouts_raw)
        if all(isinstance(item, Exception) for item in analytical_results):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ADVICE_CONTEXT_UNAVAILABLE",
                    "message": "All analytical data sources are unavailable.",
                },
            )

        entries = nutrition_raw if isinstance(nutrition_raw, list) else []
        measurements = body_raw if isinstance(body_raw, list) else []
        workouts = workouts_raw if isinstance(workouts_raw, list) else []
        detail_issues: list[DataQualityIssue] = []
        if include_workout_details:
            workouts, detail_issues = await self._add_workout_details(workouts)
        profile = _profile_model(profile_raw if not isinstance(profile_raw, Exception) else {})
        nutrition, nutrition_issues = analyze_nutrition(
            entries, window, profile, include_entries=include_entries
        )
        body, body_issues = analyze_body(measurements, window)
        training, training_issues = analyze_training(workouts, window)
        cross_domain = analyze_cross_domain(nutrition, body, training, window)
        source_status = [
            _source_status("nutrition", nutrition_raw, len(entries)),
            _source_status("withings", body_raw, len(measurements)),
            _source_status("workouts", workouts_raw, len(workouts)),
            _source_status(
                "athlete_profile",
                profile_raw,
                1 if _profile_has_values(profile_raw) else 0,
            ),
        ]
        quality = nutrition_issues + body_issues + training_issues + detail_issues
        quality.extend(_source_issues(source_status))
        if not any(
            getattr(profile, field) is not None
            for field in (
                "protein_min_g",
                "protein_target_g",
                "calorie_target_kcal",
                "fat_min_g",
                "fat_max_g",
            )
        ):
            quality.append(
                DataQualityIssue(
                    code="PROFILE_TARGET_MISSING",
                    domain="profile",
                    severity="info",
                    message="No nutrition targets were configured in the athlete profile.",
                )
            )
        return AdviceContext(
            generated_at=self._generated_at(),
            window=window,
            source_status=source_status,
            athlete_profile=profile,
            nutrition=nutrition,
            body=body,
            training=training,
            cross_domain=cross_domain,
            quality_issues=merge_quality_issues(quality),
        )

    async def _read_nutrition(self, window: Any) -> list[NutritionEntry]:
        return await self.nutrition_repository.list_entries_in_range(
            window.start_date, window.end_date
        )

    async def _read_body(self, start_at: datetime, end_at: datetime) -> list[BodyMeasurement]:
        return list(await self.withings_port.fetch_measurements_in_range(start_at, end_at))

    async def _read_workouts(self, window: Any) -> list[WorkoutLog]:
        return await self.workout_repository.list_workouts_in_range(
            window.start_date, window.end_date, window.timezone
        )

    async def _read_profile(self) -> Any:
        return await self.workout_repository.fetch_latest_athlete_profile()

    async def _add_workout_details(
        self, workouts: list[WorkoutLog]
    ) -> tuple[list[WorkoutLog], list[DataQualityIssue]]:
        enriched: list[WorkoutLog] = []
        issues: list[DataQualityIssue] = []
        for workout in workouts:
            if not workout.payload_key:
                enriched.append(workout)
                issues.append(_workout_detail_issue(workout, "info", "not_retained"))
                continue
            if self.payload_store is None:
                enriched.append(workout)
                issues.append(_workout_detail_issue(workout, "warning", "store_unavailable"))
                continue
            try:
                payload = await self.payload_store.get(workout.payload_key)
            except Exception:
                enriched.append(workout)
                issues.append(_workout_detail_issue(workout, "warning", "store_unavailable"))
                continue
            if payload is None:
                enriched.append(workout)
                issues.append(_workout_detail_issue(workout, "info", "expired"))
                continue
            try:
                intervals = _decode_workout_intervals(payload)
                enriched.append(workout.model_copy(update={"intervals": intervals}))
            except (ValueError, TypeError, OSError, UnicodeDecodeError, json.JSONDecodeError):
                enriched.append(workout)
                issues.append(_workout_detail_issue(workout, "warning", "decode_failed"))
        return enriched, issues

    def _generated_at(self) -> datetime:
        generated = self.clock()
        if generated.tzinfo is None or generated.utcoffset() is None:
            generated = generated.replace(tzinfo=timezone.utc)
        return generated.astimezone(timezone.utc)


def _profile_model(value: Any) -> AdviceAthleteProfile:
    if isinstance(value, AdviceAthleteProfile):
        return value
    if isinstance(value, dict):
        return AdviceAthleteProfile.model_validate(value)
    return AdviceAthleteProfile()


def _profile_has_values(value: Any) -> bool:
    if isinstance(value, AdviceAthleteProfile):
        return any(item is not None for item in value.model_dump().values())
    return bool(value) if not isinstance(value, Exception) else False


def _source_status(source: str, value: Any, count: int) -> SourceStatus:
    if isinstance(value, Exception):
        return SourceStatus(
            source=source, status="unavailable", record_count=0, error_code="UPSTREAM_UNAVAILABLE"
        )
    return SourceStatus(source=source, status="ok", record_count=count)


def _source_issues(statuses: list[SourceStatus]) -> list[DataQualityIssue]:
    unavailable = [status for status in statuses if status.status != "ok"]
    if not unavailable:
        return []
    return [
        DataQualityIssue(
            code="SOURCE_PARTIAL_FAILURE",
            domain="profile" if item.source == "athlete_profile" else "cross_domain",
            severity="warning",
            message="One upstream source was unavailable; affected analytical fields may be empty.",
            details={"source": item.source, "error_code": item.error_code},
        )
        for item in unavailable
    ]


__all__ = ["GetAdviceContextUseCase"]


def _workout_detail_issue(workout: WorkoutLog, severity: str, reason: str) -> DataQualityIssue:
    return DataQualityIssue(
        code="TRAINING_WORKOUT_DETAILS_UNAVAILABLE",
        domain="training",
        severity=severity,
        message="Structured interval details are unavailable for this workout.",
        affected_record_ids=[workout.page_id],
        details={"reason": reason},
    )


def _decode_workout_intervals(payload: str) -> list[Any]:
    decoded = gzip.decompress(base64.b64decode(payload)).decode()
    detail = json.loads(decoded)
    if not isinstance(detail, dict):
        raise ValueError("payload top-level value is not an object")
    if "splits_metric" in detail:
        intervals = detail["splits_metric"]
    elif "laps" in detail:
        intervals = detail["laps"]
    else:
        intervals = []
    if not isinstance(intervals, list):
        raise ValueError("payload intervals are not a list")
    return intervals
