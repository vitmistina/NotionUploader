from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from ...models.activity import ActivityLap, ActivitySplit, WorkoutActivity
from .ports import IntervalsPayloadError

_ID_RE = re.compile(r"^i(\d+)$")


def _norm(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def intervals_id_to_negative_notion_id(external_id: str) -> int:
    match = _ID_RE.match(external_id or "")
    if not match:
        raise IntervalsPayloadError(f"Unsupported Intervals.icu activity id {external_id!r}")
    value = int(match.group(1))
    if value <= 0:
        raise IntervalsPayloadError(f"Unsupported Intervals.icu activity id {external_id!r}")
    return -value


def start_date_to_timestamp_notion_id(start_date: str) -> int:
    try:
        parsed = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise IntervalsPayloadError("Intervals Companion activity has invalid start_date") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IntervalsPayloadError(
            "Intervals Companion activity start_date must be timezone-aware"
        )
    return int(parsed.astimezone(timezone.utc).timestamp())


def activity_to_notion_id(activity: dict[str, Any]) -> int:
    if _norm(activity.get("oauth_client_name")) == "intervals companion":
        start_date = activity.get("start_date")
        if not isinstance(start_date, str) or not start_date:
            raise IntervalsPayloadError("Intervals Companion activity missing start_date")
        return start_date_to_timestamp_notion_id(start_date)
    external_id = activity.get("id")
    if not isinstance(external_id, str):
        raise IntervalsPayloadError("Intervals.icu activity missing string id")
    return intervals_id_to_negative_notion_id(external_id)


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _num(value: Any, *, field: str, non_negative: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise IntervalsPayloadError(f"{field} must be numeric")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value)
        except ValueError as exc:
            raise IntervalsPayloadError(f"{field} must be numeric") from exc
    else:
        raise IntervalsPayloadError(f"{field} must be numeric")
    if not math.isfinite(result):
        raise IntervalsPayloadError(f"{field} must be finite")
    if non_negative and result < 0:
        raise IntervalsPayloadError(f"{field} must be non-negative")
    return result


def _int_num(value: Any, *, field: str) -> int | None:
    numeric = _num(value, field=field)
    return int(numeric) if numeric is not None else None


def _interval_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "average_heartrate": _num(
            item.get("average_heartrate"), field="interval.average_heartrate"
        ),
        "max_heartrate": _num(item.get("max_heartrate"), field="interval.max_heartrate"),
        "moving_time": _int_num(item.get("moving_time"), field="interval.moving_time"),
        "elapsed_time": _int_num(item.get("elapsed_time"), field="interval.elapsed_time"),
        "average_speed": _num(item.get("average_speed"), field="interval.average_speed"),
        "distance": _num(item.get("distance"), field="interval.distance"),
        "average_watts": _num(item.get("average_watts"), field="interval.average_watts"),
        "weighted_average_watts": _num(
            item.get("weighted_average_watts"), field="interval.weighted_average_watts"
        ),
        "max_watts": _num(item.get("max_watts"), field="interval.max_watts"),
        "average_cadence": _num(item.get("average_cadence"), field="interval.average_cadence"),
    }


def map_intervals_activity(
    detail: dict[str, Any], intervals: list[dict[str, Any]]
) -> WorkoutActivity:
    external_id = detail.get("id")
    if not isinstance(external_id, str) or not external_id:
        raise IntervalsPayloadError("Intervals.icu activity missing id")
    mapped_intervals = [_interval_dict(item) for item in intervals]
    intensity = _num(detail.get("icu_intensity"), field="icu_intensity", non_negative=True)
    joules = _num(detail.get("icu_joules"), field="icu_joules", non_negative=True)
    return WorkoutActivity(
        id=activity_to_notion_id(detail),
        external_id=external_id,
        provider_source=detail.get("source"),
        provider_client_name=detail.get("oauth_client_name"),
        device_name=detail.get("device_name"),
        name=str(detail.get("name") or "Unnamed activity"),
        start_date=_first_not_none(detail.get("start_date"), detail.get("start_date_local")),
        start_date_local=detail.get("start_date_local"),
        type=_first_not_none(detail.get("type"), "Other"),
        elapsed_time=_int_num(
            _first_not_none(
                detail.get("elapsed_time"),
                detail.get("icu_recording_time"),
                detail.get("moving_time"),
            ),
            field="elapsed_time",
        ),
        moving_time=_int_num(
            _first_not_none(
                detail.get("moving_time"),
                detail.get("icu_recording_time"),
                detail.get("elapsed_time"),
            ),
            field="moving_time",
        ),
        distance=_num(
            _first_not_none(detail.get("icu_distance"), detail.get("distance")), field="distance"
        ),
        total_elevation_gain=_num(detail.get("total_elevation_gain"), field="total_elevation_gain"),
        splits_metric=[ActivitySplit(**item) for item in mapped_intervals],
        laps=[ActivityLap(**item) for item in mapped_intervals],
        average_cadence=_num(detail.get("average_cadence"), field="average_cadence"),
        average_watts=_num(
            _first_not_none(detail.get("icu_average_watts"), detail.get("average_watts")),
            field="average_watts",
        ),
        weighted_average_watts=_num(
            detail.get("icu_weighted_avg_watts"), field="icu_weighted_avg_watts"
        ),
        kilojoules=joules / 1000 if joules is not None else None,
        calories=_num(detail.get("calories"), field="calories"),
        average_heartrate=_num(detail.get("average_heartrate"), field="average_heartrate"),
        max_heartrate=_num(detail.get("max_heartrate"), field="max_heartrate"),
        description=detail.get("description"),
        provider_training_load=_num(
            detail.get("icu_training_load"), field="icu_training_load", non_negative=True
        ),
        provider_intensity_factor=intensity / 100 if intensity is not None else None,
        provider_hr_drift=_num(detail.get("decoupling"), field="decoupling"),
    )
