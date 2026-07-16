from __future__ import annotations

import base64
import gzip
import json
import logging
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ...domain.workout_metrics import compute_activity_metrics
from ...notion.application.ports import WorkoutRepository
from ...workout_payload.application.ports import WorkoutPayloadStore
from ...workout_payload.infrastructure.redis_store import workout_payload_key
from .mapper import map_intervals_activity
from .ports import IntervalsApiError, IntervalsClientPort, IntervalsPayloadError

logger = logging.getLogger(__name__)


class IntervalsSyncFailure(BaseModel):
    activity_id: str | None
    error: str


class IntervalsSyncResult(BaseModel):
    status: Literal["ok", "partial_failure"]
    oldest: date
    newest: date
    lookback_days: int
    discovered: int
    eligible: int
    processed: int
    skipped: int
    failed: int
    skipped_by_reason: dict[str, int] = Field(default_factory=dict)
    failures: list[IntervalsSyncFailure] = Field(default_factory=list)


class IntervalsSyncCoordinator:
    def __init__(
        self,
        client: IntervalsClientPort,
        workout_repository: WorkoutRepository,
        *,
        default_lookback_days: int,
        rouvy_start_date: date | None,
        clock: Callable[[], datetime] | None = None,
        payload_store: WorkoutPayloadStore | None = None,
    ) -> None:
        self._client = client
        self._workouts = workout_repository
        self._default_lookback_days = default_lookback_days
        self._rouvy_start_date = rouvy_start_date
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._payload_store = payload_store

    async def sync_recent(self, lookback_days: int | None = None) -> IntervalsSyncResult:
        days = self._validate_lookback(
            self._default_lookback_days if lookback_days is None else lookback_days
        )
        newest = self._clock().date()
        oldest = newest - timedelta(days=days)
        logger.info("Starting Intervals.icu sync oldest=%s newest=%s", oldest, newest)
        activities = await self._client.list_activities(oldest=oldest, newest=newest)
        skipped: Counter[str] = Counter()
        eligible = self._eligible_activities(activities, skipped)
        logger.info("Intervals.icu discovered=%s eligible=%s", len(activities), len(eligible))
        athlete = await self._workouts.fetch_latest_athlete_profile()
        processed = 0
        failures: list[IntervalsSyncFailure] = []
        for activity in eligible:
            activity_id = activity.get("id") if isinstance(activity.get("id"), str) else None
            try:
                logger.info("Processing Intervals.icu activity id=%s", activity_id)
                _ = self._is_pre_cutover_rouvy(activity)
                intervals = await self._client.get_activity_intervals(activity_id or "")
                mapped = map_intervals_activity(activity, intervals)
                metrics = compute_activity_metrics(mapped, athlete)
                detail = mapped.model_dump()
                minified = json.dumps(detail, separators=(",", ":"), default=str)
                attachment = base64.b64encode(gzip.compress(minified.encode())).decode()
                payload_key = workout_payload_key("intervals_icu", mapped.external_id)
                detail["payload_key"] = payload_key
                if self._payload_store is not None:
                    await self._payload_store.put(payload_key, attachment)
                await self._workouts.save_workout(
                    detail,
                    attachment,
                    metrics.hr_drift,
                    metrics.vo2,
                    tss=metrics.tss,
                    intensity_factor=metrics.intensity_factor,
                )
                processed += 1
            except (
                IntervalsApiError,
                IntervalsPayloadError,
                ValidationError,
                ValueError,
                RuntimeError,
            ) as exc:
                logger.exception("Failed to process Intervals.icu activity id=%s", activity_id)
                failures.append(
                    IntervalsSyncFailure(activity_id=activity_id, error=self._safe_error(exc))
                )
        failed = len(failures)
        result = IntervalsSyncResult(
            status="partial_failure" if failed else "ok",
            oldest=oldest,
            newest=newest,
            lookback_days=days,
            discovered=len(activities),
            eligible=len(eligible),
            processed=processed,
            skipped=len(activities) - len(eligible),
            failed=failed,
            skipped_by_reason=dict(skipped),
            failures=failures,
        )
        logger.info(
            "Intervals.icu sync completed processed=%s skipped=%s failed=%s",
            processed,
            result.skipped,
            failed,
        )
        return result

    @staticmethod
    def _validate_lookback(value: int) -> int:
        if not 1 <= value <= 365:
            raise ValueError("lookback_days must be between 1 and 365")
        return value

    def _eligible_activities(
        self, activities: list[dict[str, Any]], skipped: Counter[str]
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        eligible: list[dict[str, Any]] = []
        for activity in activities:
            activity_id = activity.get("id")
            if activity.get("source") == "STRAVA":
                skipped["source_strava"] += 1
                continue
            if not isinstance(activity_id, str) or not activity_id:
                skipped["missing_activity_id"] += 1
                continue
            if activity_id in seen:
                skipped["duplicate_activity_id"] += 1
                continue
            seen.add(activity_id)
            try:
                before_cutover = self._is_pre_cutover_rouvy(activity)
            except IntervalsPayloadError:
                eligible.append(activity)
                continue
            if before_cutover:
                skipped["before_rouvy_start_date"] += 1
                continue
            eligible.append(activity)
        return eligible

    def _is_pre_cutover_rouvy(self, activity: dict[str, Any]) -> bool:
        if self._rouvy_start_date is None:
            return False
        client_name = activity.get("oauth_client_name")
        is_rouvy = (
            activity.get("source") == "OAUTH_CLIENT"
            and isinstance(client_name, str)
            and client_name.strip().casefold() == "rouvy"
        )
        if not is_rouvy:
            return False
        raw = activity.get("start_date_local")
        if not isinstance(raw, str) or not raw:
            raise IntervalsPayloadError("Direct Rouvy activity missing start_date_local")
        try:
            local_date = datetime.fromisoformat(raw).date()
        except ValueError as exc:
            raise IntervalsPayloadError(
                "Direct Rouvy activity has invalid start_date_local"
            ) from exc
        return local_date < self._rouvy_start_date

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc).splitlines()[0]
        return message[:300]
