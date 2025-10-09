from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models.workout import WorkoutLog
from .services.interfaces import NotionAPI
from .settings import Settings


async def fetch_latest_athlete_profile(
    settings: Settings, client: NotionAPI
) -> Dict[str, Any]:
    """Fetch the latest athlete profile entry from Notion."""
    payload = {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": 1,
    }
    resp = await client.query(
        settings.notion_athlete_profile_database_id, payload
    )
    results = resp.get("results", [])
    if not results:
        return {}
    props = results[0]["properties"]
    return {
        "ftp": props.get("FTP Watts", {}).get("number"),
        "weight": props.get("Weight Kg", {}).get("number"),
        "max_hr": props.get("Max HR", {}).get("number"),
    }


def _add_number_prop(props: Dict[str, Any], name: str, value: Optional[float]) -> None:
    if value is not None:
        props[name] = {"number": value}


async def save_workout_to_notion(
    detail: Dict[str, Any],
    attachment: str,
    hr_drift: float,
    vo2max: float,
    *,
    tss: Optional[float] = None,
    intensity_factor: Optional[float] = None,
    settings: Settings,
    client: NotionAPI,
) -> None:
    """Store a Strava activity detail in the workout database.

    The function checks for an existing page with the same activity id and
    updates it if found; otherwise a new page is created. This upsert semantics
    avoids duplicate entries.
    """
    start_date = detail.get("start_date")
    date_only = start_date.split("T")[0] if start_date else datetime.utcnow().date().isoformat()
    day_of_week = datetime.fromisoformat(date_only).strftime("%A")

    props: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": detail["name"]}}]},
        "Date": {"date": {"start": date_only}},
        "Duration [s]": {"number": detail.get("elapsed_time")},
        "Distance [m]": {"number": detail.get("distance")},
        "Elevation [m]": {"number": detail.get("total_elevation_gain")},
        "Type": {"rich_text": [{"text": {"content": str(detail.get("type", ""))}}]},
        "Id": {"number": detail["id"]},
        "Day of week": {"select": {"name": day_of_week}},
    }

    _add_number_prop(props, "Average Cadence", detail.get("average_cadence"))
    _add_number_prop(props, "Average Watts", detail.get("average_watts"))
    _add_number_prop(props, "Weighted Average Watts", detail.get("weighted_average_watts"))
    _add_number_prop(props, "Kilojoules", detail.get("kilojoules"))
    _add_number_prop(props, "Kcal", detail.get("calories"))
    _add_number_prop(props, "Average Heartrate", detail.get("average_heartrate"))
    _add_number_prop(props, "Max Heartrate", detail.get("max_heartrate"))
    _add_number_prop(props, "HR drift [%]", hr_drift)
    _add_number_prop(props, "VO2 MAX [min]", vo2max)
    _add_number_prop(props, "TSS", tss)
    _add_number_prop(props, "IF", intensity_factor)

    description = detail.get("description")
    if description:
        props["Notes"] = {"rich_text": [{"text": {"content": description}}]}

    # Attempt to find an existing page with the same activity id and update it
    query_payload = {
        "filter": {"property": "Id", "number": {"equals": detail["id"]}},
        "page_size": 1,
    }
    resp = await client.query(settings.notion_workout_database_id, query_payload)
    results = resp.get("results", [])
    if results:
        page_id = results[0]["id"]
        payload = {"properties": props}
        await client.update(page_id, payload)
        return
    payload = {
        "parent": {"database_id": settings.notion_workout_database_id},
        "properties": props,
    }
    await client.create(payload)


def _parse_workout_page(page: Dict[str, Any]) -> Optional[WorkoutLog]:
    props = page["properties"]

    def _get_number(name: str, default: float = 0.0) -> float:
        value = props.get(name, {}).get("number")
        return value if value is not None else default

    def _get_optional_number(name: str) -> Optional[float]:
        return props.get(name, {}).get("number")

    def _get_title(name: str) -> str:
        title_data = props.get(name, {}).get("title", [])
        if title_data:
            return title_data[0].get("text", {}).get("content", "")
        return ""

    def _get_date(name: str) -> str:
        date_data = props.get(name, {}).get("date")
        if date_data:
            return date_data.get("start") or ""
        return ""

    try:
        type_value = ""
        if props.get("Type", {}).get("rich_text"):
            type_value = props["Type"]["rich_text"][0]["text"]["content"]
        elif props.get("Type", {}).get("select"):
            type_value = props["Type"]["select"]["name"]

        return WorkoutLog(
            name=_get_title("Name"),
            date=_get_date("Date"),
            duration_s=_get_number("Duration [s]"),
            distance_m=_get_number("Distance [m]"),
            elevation_m=_get_number("Elevation [m]"),
            type=type_value,
            average_cadence=_get_optional_number("Average Cadence"),
            average_watts=_get_optional_number("Average Watts"),
            weighted_average_watts=_get_optional_number("Weighted Average Watts"),
            kilojoules=_get_optional_number("Kilojoules"),
            kcal=_get_optional_number("Kcal"),
            average_heartrate=_get_optional_number("Average Heartrate"),
            max_heartrate=_get_optional_number("Max Heartrate"),
            hr_drift_percent=_get_optional_number("HR drift [%]"),
            vo2max_minutes=_get_optional_number("VO2 MAX [min]"),
            tss=_get_optional_number("TSS"),
            intensity_factor=_get_optional_number("IF"),
            notes=(
                props.get("Notes", {})
                .get("rich_text", [{}])[0]
                .get("text", {})
                .get("content")
                if props.get("Notes", {}).get("rich_text")
                else None
            ),
        )
    except Exception:
        return None


async def fetch_workouts_from_notion(
    days: int, settings: Settings, client: NotionAPI
) -> List[WorkoutLog]:
    """Return workouts from the workout database for the last ``days`` days."""
    start = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    payload = {"filter": {"property": "Date", "date": {"on_or_after": start}}}
    resp = await client.query(settings.notion_workout_database_id, payload)
    results = resp.get("results", [])
    workouts: List[WorkoutLog] = []
    for page in results:
        w = _parse_workout_page(page)
        if w:
            workouts.append(w)
    return workouts
