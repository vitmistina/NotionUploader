from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from src.application.advice_context import GetAdviceContextUseCase
from src.models.body import BodyMeasurement
from src.models.nutrition import NutritionEntry
from src.models.workout import WorkoutLog


class Nutrition:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises

    async def list_entries_in_range(self, start_date, end_date):
        if self.raises:
            raise self.raises
        return [
            NutritionEntry(
                food_item="Food",
                date=end_date - __import__("datetime").timedelta(days=1),
                calories=400,
                protein_g=30,
                carbs_g=40,
                fat_g=10,
                meal_type="Dinner",
                notes="note",
            )
        ]


class Body:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises

    async def fetch_measurements_in_range(self, start_at, end_at):
        if self.raises:
            raise self.raises
        return [
            BodyMeasurement(
                measurement_time=datetime(2026, 7, 15, 7, tzinfo=timezone.utc),
                weight_kg=70,
                fat_free_mass_kg=55,
                device_name="Scale",
            )
        ]


class Workouts:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises

    async def list_workouts_in_range(self, start_date, end_date, timezone_name):
        if self.raises:
            raise self.raises
        return [
            WorkoutLog(
                page_id="ride-1",
                name="Ride",
                date="2026-07-15",
                duration_s=3600,
                distance_m=1000,
                elevation_m=10,
                type="Ride",
                kcal=500,
                tss=100,
                tss_origin="provider",
                load_family="provider_training_load",
            )
        ]

    async def fetch_latest_athlete_profile(self):
        return {"protein_target_g": 130, "resting_hr": 60}


def clock() -> datetime:
    return datetime(2026, 7, 16, 12, tzinfo=timezone.utc)


def make_use_case(*, nutrition=None, body=None, workouts=None):
    return GetAdviceContextUseCase(
        nutrition_repository=nutrition or Nutrition(),
        withings_port=body or Body(),
        workout_repository=workouts or Workouts(),
        clock=clock,
    )


@pytest.mark.asyncio
async def test_context_uses_one_window_and_returns_typed_source_statuses() -> None:
    context = await make_use_case().__call__(
        days=3, timezone="Europe/Prague", include_entries=False
    )

    assert context.context_version == "2.0"
    assert context.window.calendar_days == [date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)]
    assert {item.status for item in context.source_status} == {"ok"}
    assert context.nutrition.daily[1].entries == []
    assert context.training.windows[-1].training_days == 1


@pytest.mark.asyncio
async def test_context_survives_one_source_failure() -> None:
    context = await make_use_case(body=Body(raises=RuntimeError("secret"))).__call__(
        days=2, timezone="UTC"
    )

    assert (
        next(item for item in context.source_status if item.source == "withings").status
        == "unavailable"
    )
    assert any(issue.code == "SOURCE_PARTIAL_FAILURE" for issue in context.quality_issues)


@pytest.mark.asyncio
async def test_context_returns_503_when_all_analytical_sources_fail() -> None:
    use_case = make_use_case(
        nutrition=Nutrition(raises=RuntimeError()),
        body=Body(raises=RuntimeError()),
        workouts=Workouts(raises=RuntimeError()),
    )

    with pytest.raises(HTTPException) as raised:
        await use_case(days=1, timezone="UTC")
    assert raised.value.status_code == 503

class PayloadStore:
    def __init__(self, values):
        self.values = values

    async def put(self, key: str, value: str) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        value = self.values[key]
        if isinstance(value, Exception):
            raise value
        return value


class DetailWorkouts(Workouts):
    def __init__(self, payload_keys: list[str | None]) -> None:
        self.payload_keys = payload_keys

    async def list_workouts_in_range(self, start_date, end_date, timezone_name):
        return [
            WorkoutLog(
                page_id=f"ride-{index}",
                name="Ride",
                date="2026-07-15",
                duration_s=3600,
                distance_m=1000,
                elevation_m=10,
                type="Ride",
                kcal=500,
                tss=100,
                tss_origin="provider",
                load_family="provider_training_load",
                payload_key=payload_key,
            )
            for index, payload_key in enumerate(self.payload_keys)
        ]


@pytest.mark.asyncio
async def test_context_enriches_workout_details_and_reports_partial_payload_failures() -> None:
    import base64
    import gzip
    import json

    valid = base64.b64encode(
        gzip.compress(json.dumps({"laps": [{"distance": 1}]}).encode())
    ).decode()
    use_case = GetAdviceContextUseCase(
        nutrition_repository=Nutrition(),
        withings_port=Body(),
        workout_repository=DetailWorkouts(["valid", None, "expired", "broken", "store"]),
        clock=clock,
        payload_store=PayloadStore(
            {
                "valid": valid,
                "expired": None,
                "broken": "not-gzip-json",
                "store": RuntimeError("redis://secret-token"),
            }
        ),
    )

    context = await use_case(days=2, timezone="UTC", include_workout_details=True)

    assert context.training.workouts[0].intervals == [{"distance": 1}]
    reasons = [
        issue.details["reason"]
        for issue in context.quality_issues
        if issue.code == "TRAINING_WORKOUT_DETAILS_UNAVAILABLE"
    ]
    assert reasons == ["not_retained", "expired", "decode_failed", "store_unavailable"]


@pytest.mark.asyncio
async def test_context_reports_configured_payload_key_when_store_is_unavailable() -> None:
    use_case = GetAdviceContextUseCase(
        nutrition_repository=Nutrition(),
        withings_port=Body(),
        workout_repository=DetailWorkouts(["retained-key"]),
        clock=clock,
        payload_store=None,
    )

    context = await use_case(days=2, timezone="UTC", include_workout_details=True)

    issue = next(
        item
        for item in context.quality_issues
        if item.code == "TRAINING_WORKOUT_DETAILS_UNAVAILABLE"
    )
    assert issue.details == {"reason": "store_unavailable"}


@pytest.mark.asyncio
async def test_context_rejects_non_list_primary_interval_collection() -> None:
    import base64
    import gzip
    import json

    payload = base64.b64encode(
        gzip.compress(json.dumps({"splits_metric": {}, "laps": []}).encode())
    ).decode()
    use_case = GetAdviceContextUseCase(
        nutrition_repository=Nutrition(),
        withings_port=Body(),
        workout_repository=DetailWorkouts(["malformed"]),
        clock=clock,
        payload_store=PayloadStore({"malformed": payload}),
    )

    context = await use_case(days=2, timezone="UTC", include_workout_details=True)

    assert context.training.workouts[0].intervals is None
    assert any(
        item.details == {"reason": "decode_failed"}
        for item in context.quality_issues
        if item.code == "TRAINING_WORKOUT_DETAILS_UNAVAILABLE"
    )
