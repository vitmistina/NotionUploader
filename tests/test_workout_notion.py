"""Exercises for the Notion workout repository."""

from __future__ import annotations

from datetime import date

import pytest

from src.notion.infrastructure.workout_repository import NotionWorkoutAdapter
from platform.config import Settings

from tests.builders import (
    make_notion_profile,
    make_notion_workout,
    notion_number,
    notion_rich_text,
    notion_title,
)
from tests.conftest import NotionAPIStub
from tests.fakes import NotionWorkoutFake

EXPECTED_BACKFILL_INTENSITY_FACTOR = 0.78
EXPECTED_BACKFILL_TSS = 78.3
EXPECTED_FILL_INTENSITY_FACTOR = 0.87
EXPECTED_FILL_TSS = 87.3
USER_SUPPLIED_INTENSITY_FACTOR = 0.62
USER_SUPPLIED_TSS = 33.0


def assert_metric_update_payload(
    payload: dict, *, expected_tss: float, expected_intensity_factor: float
) -> None:
    properties = payload["properties"]
    assert properties["TSS"]["number"] == pytest.approx(expected_tss)
    assert properties["IF"]["number"] == pytest.approx(expected_intensity_factor)


@pytest.mark.asyncio
async def test_fetch_workouts_includes_minimal_entries(
    settings: Settings,
    freeze_time,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    """Listing workouts returns minimal entries alongside fully populated ones."""

    _ = freeze_time

    notion_workout_fake.with_profile(make_notion_profile()).with_workouts(
        [
            make_notion_workout(
                id="page-1",
                properties={
                    "Name": notion_title("Outdoor Run"),
                    "Date": {"date": {"start": "2025-10-08"}},
                },
            ),
            make_notion_workout(
                id="page-2",
                properties={
                    "Name": notion_title("PT in gym"),
                    "Date": {"date": {"start": "2025-10-09"}},
                    "Duration [s]": notion_number(None),
                    "Distance [m]": notion_number(None),
                    "Elevation [m]": notion_number(None),
                    "Type": notion_rich_text(None),
                    "Notes": notion_rich_text("Inclined walk warmup."),
                },
            ),
        ]
    )

    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_recent_workouts(7)

    names = [w.name for w in workouts]
    assert "Outdoor Run" in names
    assert "PT in gym" in names
    assert {w.page_id for w in workouts} == {"page-1", "page-2"}


@pytest.mark.asyncio
async def test_list_recent_workouts_backfills_metrics(
    settings: Settings,
    freeze_time,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    """Missing training metrics are backfilled when enough heart-rate data exists."""

    _ = freeze_time

    notion_workout_fake.with_profile(
        make_notion_profile({"Max HR": notion_number(188)})
    ).with_workouts(
        [
            make_notion_workout(
                id="page-backfill",
                properties={
                    "Name": notion_title("Gym Session"),
                    "Date": {"date": {"start": "2025-10-10"}},
                    "Distance [m]": notion_number(0),
                    "Elevation [m]": notion_number(0),
                    "Type": notion_rich_text(None),
                    "Average Heartrate": notion_number(140),
                    "Max Heartrate": notion_number(165),
                    "TSS": notion_number(None),
                    "IF": notion_number(None),
                },
            )
        ]
    )

    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_recent_workouts(7)

    assert workouts[0].type == "Gym"
    assert workouts[0].tss == pytest.approx(EXPECTED_BACKFILL_TSS)
    assert workouts[0].intensity_factor == pytest.approx(EXPECTED_BACKFILL_INTENSITY_FACTOR)
    assert workouts[0].page_id == "page-backfill"

    page_id, payload = notion_workout_fake.updates()[-1]
    assert page_id == "page-backfill"
    assert payload["properties"]["Type"] == {"rich_text": [{"text": {"content": "Gym"}}]}
    assert_metric_update_payload(
        payload,
        expected_tss=EXPECTED_BACKFILL_TSS,
        expected_intensity_factor=EXPECTED_BACKFILL_INTENSITY_FACTOR,
    )


@pytest.mark.asyncio
async def test_fill_missing_metrics_updates_notion(
    settings: Settings,
    freeze_time,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    """Filling metrics writes back the calculated values to Notion."""

    _ = freeze_time

    notion_workout_fake.with_profile(
        make_notion_profile({"Max HR": notion_number(185)})
    ).with_workouts(
        [
            make_notion_workout(
                id="page-fill",
                properties={
                    "Name": notion_title("Gym Session"),
                    "Date": {"date": {"start": "2025-10-10"}},
                    "Distance [m]": notion_number(0),
                    "Elevation [m]": notion_number(0),
                    "Type": notion_rich_text(None),
                    "Average Heartrate": notion_number(150),
                    "Max Heartrate": notion_number(175),
                },
            )
        ]
    )

    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    updated = await repository.fill_missing_metrics("page-fill")

    assert updated is not None
    assert updated.page_id == "page-fill"
    assert updated.tss == pytest.approx(EXPECTED_FILL_TSS)
    assert updated.intensity_factor == pytest.approx(EXPECTED_FILL_INTENSITY_FACTOR)

    page_id, payload = notion_workout_fake.updates()[-1]
    assert page_id == "page-fill"
    properties = payload["properties"]
    assert {"TSS", "IF", "Type"}.issubset(properties.keys())
    assert properties["Type"] == {"rich_text": [{"text": {"content": "Gym"}}]}
    assert_metric_update_payload(
        payload,
        expected_tss=EXPECTED_FILL_TSS,
        expected_intensity_factor=EXPECTED_FILL_INTENSITY_FACTOR,
    )


@pytest.mark.asyncio
async def test_save_workout_creates_new_notion_page(
    settings: Settings, notion_api_stub: NotionAPIStub
) -> None:
    detail = {
        "id": 123,
        "name": "Morning Ride",
        "start_date": "2026-05-10T12:00:00Z",
        "elapsed_time": 3600,
        "distance": 25_000,
        "total_elevation_gain": 250,
        "type": "Ride",
        "average_cadence": 82,
        "average_watts": 180,
        "weighted_average_watts": 200,
        "kilojoules": 650,
        "calories": 700,
        "average_heartrate": 145,
        "max_heartrate": 172,
        "description": "Sunny endurance ride",
    }
    notion_api_stub.expect_query(
        settings.notion_workout_database_id,
        {
            "filter": {"property": "Id", "number": {"equals": 123}},
            "page_size": 1,
        },
        returns={"results": []},
    ).expect_create(returns={"id": "created-page"})
    repository = NotionWorkoutAdapter(settings=settings, client=notion_api_stub)

    await repository.save_workout(
        detail,
        "attachment",
        hr_drift=1.5,
        vo2max=42.0,
        tss=55.0,
        intensity_factor=0.75,
    )

    payload = notion_api_stub.last_create_payload()
    assert payload is not None
    assert payload["parent"] == {"database_id": settings.notion_workout_database_id}
    properties = payload["properties"]
    assert properties["Name"] == {"title": [{"text": {"content": "Morning Ride"}}]}
    assert properties["Date"] == {"date": {"start": "2026-05-10"}}
    assert properties["Day of week"] == {"select": {"name": "Sunday"}}
    assert properties["Type"] == {"rich_text": [{"text": {"content": "Ride"}}]}
    assert properties["Notes"] == {"rich_text": [{"text": {"content": "Sunny endurance ride"}}]}
    assert properties["TSS"] == {"number": 55.0}
    assert properties["IF"] == {"number": 0.75}


@pytest.mark.asyncio
async def test_save_workout_updates_existing_notion_page(
    settings: Settings, notion_api_stub: NotionAPIStub
) -> None:
    detail = {
        "id": 456,
        "name": "Strength",
        "elapsed_time": 1800,
        "distance": 0,
        "total_elevation_gain": 0,
        "type": None,
    }
    notion_api_stub.expect_query(
        settings.notion_workout_database_id,
        {
            "filter": {"property": "Id", "number": {"equals": 456}},
            "page_size": 1,
        },
        returns={"results": [{"id": "existing-page"}]},
    ).expect_update(page_id="existing-page", returns={"id": "existing-page"})
    repository = NotionWorkoutAdapter(settings=settings, client=notion_api_stub)

    await repository.save_workout(
        detail,
        "attachment",
        hr_drift=0.0,
        vo2max=0.0,
        tss=20.0,
        intensity_factor=0.5,
    )

    payload = notion_api_stub.last_update_payload()
    assert payload is not None
    properties = payload["properties"]
    assert properties["Name"] == {"title": [{"text": {"content": "Strength"}}]}
    assert properties["Type"] == {"rich_text": [{"text": {"content": "Gym"}}]}
    assert properties["Id"] == {"number": 456}


@pytest.mark.asyncio
async def test_range_read_preserves_legacy_calendar_date_in_negative_timezone(
    settings: Settings, notion_workout_fake: NotionWorkoutFake
) -> None:
    notion_workout_fake.with_workouts(
        [
            make_notion_workout(
                id="legacy-page",
                properties={
                    "Name": notion_title("Legacy ride"),
                    "Date": {"date": {"start": "2026-07-15"}},
                },
            )
        ]
    )
    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_workouts_in_range(
        date(2026, 7, 15), date(2026, 7, 15), "America/New_York"
    )

    assert [workout.page_id for workout in workouts] == ["legacy-page"]
    assert workouts[0].start_time is None


@pytest.mark.asyncio
async def test_range_read_keeps_invalid_date_for_domain_diagnostics(
    settings: Settings, notion_workout_fake: NotionWorkoutFake
) -> None:
    notion_workout_fake.with_workouts(
        [
            make_notion_workout(
                id="invalid-page",
                properties={
                    "Name": notion_title("Malformed legacy ride"),
                    "Date": {"date": {"start": "not-a-date"}},
                },
            )
        ]
    )
    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_workouts_in_range(
        date(2026, 7, 15), date(2026, 7, 15), "UTC"
    )

    assert [workout.page_id for workout in workouts] == ["invalid-page"]


@pytest.mark.asyncio
async def test_fill_missing_metrics_preserves_user_supplied_metrics(
    settings: Settings,
    freeze_time,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    """Existing user-supplied TSS and IF values are not overwritten by estimates."""

    _ = freeze_time

    notion_workout_fake.with_profile(
        make_notion_profile({"Max HR": notion_number(185)})
    ).with_workouts(
        [
            make_notion_workout(
                id="page-preserve",
                properties={
                    "Name": notion_title("Gym Session"),
                    "Date": {"date": {"start": "2025-10-10"}},
                    "Distance [m]": notion_number(0),
                    "Elevation [m]": notion_number(0),
                    "Type": notion_rich_text("Gym"),
                    "Average Heartrate": notion_number(150),
                    "Max Heartrate": notion_number(175),
                    "TSS": notion_number(USER_SUPPLIED_TSS),
                    "IF": notion_number(USER_SUPPLIED_INTENSITY_FACTOR),
                },
            )
        ]
    )

    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    updated = await repository.fill_missing_metrics("page-preserve")

    assert updated is not None
    assert updated.tss == pytest.approx(USER_SUPPLIED_TSS)
    assert updated.intensity_factor == pytest.approx(USER_SUPPLIED_INTENSITY_FACTOR)
    assert notion_workout_fake.updates() == []


@pytest.mark.asyncio
async def test_save_workout_filters_missing_extension_schema(
    settings: Settings,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    notion_workout_fake.database_schema = {"properties": {}}
    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    await repository.save_workout(
        {
            "id": 123,
            "name": "Ride",
            "start_date": "2026-07-15T12:00:00+00:00",
            "elapsed_time": 60,
            "moving_time": 60,
            "distance": 1,
            "total_elevation_gain": 0,
            "type": "Ride",
            "payload_key": "secret-free-key",
        },
        "attachment",
        0,
        0,
    )

    props = notion_workout_fake._pages["created-page"]["properties"]
    assert "Date" in props
    assert "Payload Key" not in props


@pytest.mark.asyncio
async def test_save_workout_writes_complete_extension_schema(
    settings: Settings,
    notion_workout_fake: NotionWorkoutFake,
) -> None:
    notion_workout_fake.database_schema = {
        "properties": {
            "Start Time": {"type": "date"},
            "Payload Key": {"type": "rich_text"},
            "TSS Origin": {"type": "rich_text"},
            "Load Family": {"type": "rich_text"},
            "External ID": {"type": "rich_text"},
            "Provider Source": {"type": "rich_text"},
            "Provider Client": {"type": "rich_text"},
            "Device": {"type": "rich_text"},
        }
    }
    repository = NotionWorkoutAdapter(settings=settings, client=notion_workout_fake)

    await repository.save_workout(
        {
            "id": 456,
            "name": "Ride",
            "start_date": "2026-07-15T12:00:00+00:00",
            "elapsed_time": 60,
            "moving_time": 60,
            "distance": 1,
            "total_elevation_gain": 0,
            "type": "Ride",
            "payload_key": "payload-key",
        },
        "attachment",
        0,
        0,
    )

    props = notion_workout_fake._pages["created-page"]["properties"]
    assert props["Start Time"] == {"date": {"start": "2026-07-15T12:00:00+00:00"}}
    assert props["Payload Key"] == {"rich_text": [{"text": {"content": "payload-key"}}]}
