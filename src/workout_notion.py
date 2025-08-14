from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models.workout import WorkoutLog
from .services.notion import NotionClient
from .settings import Settings


async def fetch_latest_athlete_profile(
    settings: Settings,
    *,
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Fetch the latest athlete profile entry from Notion."""
    payload = {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": 1,
    }
    if client is None:
        async with NotionClient(settings) as notion:
            resp = await notion.query_database(
                settings.notion_athlete_profile_database_id, payload
            )
    else:
        resp = await client.query_database(
            settings.notion_athlete_profile_database_id, payload
        )
    results = resp.json().get("results", [])
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
    client: Optional[NotionClient] = None,
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
        "Name": {"title": [{"text": {"content": detail.get("name", "")}}]},
        "Date": {"date": {"start": date_only}},
        "Duration [s]": {"number": detail.get("elapsed_time")},
        "Distance [m]": {"number": detail.get("distance")},
        "Elevation [m]": {"number": detail.get("total_elevation_gain")},
        "Type": {"rich_text": [{"text": {"content": str(detail.get("type", ""))}}]},
        "Id": {"number": detail.get("id")},
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
        "filter": {"property": "Id", "number": {"equals": detail.get("id")}},
        "page_size": 1,
    }
    if client is None:
        async with NotionClient(settings) as notion:
            query_resp = await notion.query_database(
                settings.notion_workout_database_id, query_payload
            )
            results = query_resp.json().get("results", [])
            if results:
                page_id = results[0]["id"]
                payload = {"properties": props}
                await notion.update_page(page_id, payload)
                return
            payload = {
                "parent": {"database_id": settings.notion_workout_database_id},
                "properties": props,
            }
            await notion.create_page(payload)
    else:
        query_resp = await client.query_database(
            settings.notion_workout_database_id, query_payload
        )
        results = query_resp.json().get("results", [])
        if results:
            page_id = results[0]["id"]
            payload = {"properties": props}
            await client.update_page(page_id, payload)
            return
        payload = {
            "parent": {"database_id": settings.notion_workout_database_id},
            "properties": props,
        }
        await client.create_page(payload)


def _parse_workout_page(page: Dict[str, Any]) -> Optional[WorkoutLog]:
    props = page["properties"]
    try:
        type_value = ""
        if props.get("Type", {}).get("rich_text"):
            type_value = props["Type"]["rich_text"][0]["text"]["content"]
        elif props.get("Type", {}).get("select"):
            type_value = props["Type"]["select"]["name"]

        return WorkoutLog(
            name=props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "",
            date=props["Date"]["date"]["start"] if props["Date"]["date"] else "",
            duration_s=props["Duration [s]"]["number"],
            distance_m=props["Distance [m]"]["number"],
            elevation_m=props["Elevation [m]"]["number"],
            type=type_value,
            average_cadence=props.get("Average Cadence", {}).get("number"),
            average_watts=props.get("Average Watts", {}).get("number"),
            weighted_average_watts=props.get("Weighted Average Watts", {}).get("number"),
            kilojoules=props.get("Kilojoules", {}).get("number"),
            kcal=props.get("Kcal", {}).get("number"),
            average_heartrate=props.get("Average Heartrate", {}).get("number"),
            max_heartrate=props.get("Max Heartrate", {}).get("number"),
            hr_drift_percent=props.get("HR drift [%]", {}).get("number"),
            vo2max_minutes=props.get("VO2 MAX [min]", {}).get("number"),
            tss=props.get("TSS", {}).get("number"),
            intensity_factor=props.get("IF", {}).get("number"),
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
    days: int,
    settings: Settings,
    *,
    client: Optional[NotionClient] = None,
) -> List[WorkoutLog]:
    """Return workouts from the workout database for the last ``days`` days."""
    start = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    payload = {"filter": {"property": "Date", "date": {"on_or_after": start}}}
    if client is None:
        async with NotionClient(settings) as notion:
            resp = await notion.query_database(
                settings.notion_workout_database_id, payload
            )
    else:
        resp = await client.query_database(
            settings.notion_workout_database_id, payload
        )
    results = resp.json().get("results", [])
    workouts: List[WorkoutLog] = []
    for page in results:
        w = _parse_workout_page(page)
        if w:
            workouts.append(w)
    return workouts
