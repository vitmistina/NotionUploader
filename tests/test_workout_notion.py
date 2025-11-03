"""Exercises for the Notion workout repository."""

from __future__ import annotations

import pytest

from src.notion.infrastructure.workout_repository import NotionWorkoutRepository
from src.settings import Settings

from tests.builders import (
    make_notion_profile,
    make_notion_workout,
    notion_number,
    notion_rich_text,
    notion_title,
)
from tests.fakes import NotionWorkoutFake


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

    repository = NotionWorkoutRepository(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_recent_workouts(7)

    assert sorted(workout.name for workout in workouts) == ["Outdoor Run", "PT in gym"]


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

    repository = NotionWorkoutRepository(settings=settings, client=notion_workout_fake)

    workouts = await repository.list_recent_workouts(7)

    workout = workouts[0]
    assert workout.type == "Gym"
    assert workout.tss is not None
    assert workout.intensity_factor is not None


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

    repository = NotionWorkoutRepository(settings=settings, client=notion_workout_fake)

    updated = await repository.fill_missing_metrics("page-fill")

    assert updated is not None
    assert updated.tss is not None
    assert updated.intensity_factor is not None

    page_id, payload = notion_workout_fake.updates()[-1]
    assert page_id == "page-fill"
    properties = payload["properties"]
    assert {"TSS", "IF", "Type"}.issubset(properties.keys())
