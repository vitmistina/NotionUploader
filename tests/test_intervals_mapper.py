from datetime import datetime, timezone

import pytest

from src.intervals_icu.application.mapper import (
    intervals_id_to_negative_notion_id,
    map_intervals_activity,
    start_date_to_timestamp_notion_id,
)
from src.intervals_icu.application.ports import IntervalsPayloadError
from src.models.workout import ManualWorkoutSubmission


def rouvy():
    return {
        "id": "i165581497",
        "start_date_local": "2026-07-12T18:31:22",
        "start_date": "2026-07-12T16:31:22Z",
        "type": "VirtualRide",
        "source": "OAUTH_CLIENT",
        "oauth_client_name": "ROUVY",
        "device_name": "VIRTUALTRAINING Rouvy",
        "name": "ROUVY - Synthetic Test Ride",
        "elapsed_time": 2504,
        "moving_time": 2504,
        "distance": 1,
        "icu_distance": 12950.34,
        "total_elevation_gain": 314.00003,
        "icu_average_watts": 115,
        "icu_weighted_avg_watts": 117,
        "icu_joules": 288520,
        "icu_training_load": 31,
        "icu_intensity": 66.47727,
        "average_heartrate": 128,
        "max_heartrate": 136,
        "average_cadence": 78.07146,
        "calories": 276,
        "decoupling": 6.106287,
    }


def test_intervals_id_to_negative_notion_id():
    assert intervals_id_to_negative_notion_id("i165581497") == -165581497
    for bad in ["165581497", "abc", "i", "i-1", "i0", ""]:
        with pytest.raises(IntervalsPayloadError):
            intervals_id_to_negative_notion_id(bad)


def test_map_rouvy_provider_metrics_and_intervals():
    activity = map_intervals_activity(rouvy(), [{"moving_time": 600, "average_heartrate": 125}])
    assert activity.id == -165581497
    assert activity.external_id == "i165581497"
    assert activity.provider_client_name == "ROUVY"
    assert activity.distance == 12950.34
    assert activity.kilojoules == 288.52
    assert activity.provider_intensity_factor == pytest.approx(0.6647727)
    assert activity.provider_training_load == 31
    assert activity.provider_hr_drift == 6.106287
    assert len(activity.splits_metric) == len(activity.laps) == 1


def test_companion_timestamp_matches_manual_identifier():
    detail = rouvy() | {
        "oauth_client_name": "Intervals Companion",
        "start_date": "2026-07-08T10:49:58Z",
        "type": "WeightTraining",
        "distance": None,
        "icu_distance": None,
        "icu_joules": None,
    }
    activity = map_intervals_activity(detail, [])
    manual = ManualWorkoutSubmission(
        name="x",
        start_time=datetime(2026, 7, 8, 10, 49, 58, tzinfo=timezone.utc),
        duration_minutes=1,
        average_heartrate=100,
        max_heartrate=120,
    )
    assert activity.id == manual._generate_identifier()
    assert start_date_to_timestamp_notion_id("2026-07-08T12:49:58+02:00") == activity.id


def test_companion_requires_timezone_aware_start_date():
    for value in [None, "bad", "2026-07-08T10:49:58"]:
        detail = rouvy() | {"oauth_client_name": "Intervals Companion", "start_date": value}
        with pytest.raises(IntervalsPayloadError):
            map_intervals_activity(detail, [])


def test_sparse_strength_maps_without_fabricated_distance():
    detail = rouvy() | {
        "oauth_client_name": "Intervals Companion",
        "type": "WeightTraining",
        "distance": None,
        "icu_distance": None,
        "icu_average_watts": None,
        "icu_weighted_avg_watts": None,
        "icu_joules": None,
    }
    activity = map_intervals_activity(detail, [])
    assert activity.type == "WeightTraining"
    assert activity.distance is None
    assert activity.average_watts is None
