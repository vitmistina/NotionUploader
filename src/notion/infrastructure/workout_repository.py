from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends

from ...models.workout import WorkoutLog
from ...services.interfaces import NotionAPI
from ...services.notion import get_notion_client
from ...settings import Settings, get_settings
from ..application.ports import WorkoutRepository


class NotionWorkoutRepository(WorkoutRepository):
    """Concrete Notion adapter for workout-related operations."""

    def __init__(self, *, settings: Settings, client: NotionAPI) -> None:
        self._settings = settings
        self._client = client

    async def list_recent_workouts(self, days: int) -> List[WorkoutLog]:
        start = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        payload = {"filter": {"property": "Date", "date": {"on_or_after": start}}}
        response = await self._client.query(self._settings.notion_workout_database_id, payload)
        workouts: List[WorkoutLog] = []
        for page in response.get("results", []):
            workout = self._parse_workout_page(page)
            if workout:
                workouts.append(workout)
        return workouts

    async def fetch_latest_athlete_profile(self) -> Dict[str, Any]:
        payload = {
            "sorts": [{"property": "Date", "direction": "descending"}],
            "page_size": 1,
        }
        response = await self._client.query(
            self._settings.notion_athlete_profile_database_id, payload
        )
        results = response.get("results", [])
        if not results:
            return {}
        props = results[0].get("properties", {})
        return {
            "ftp": props.get("FTP Watts", {}).get("number"),
            "weight": props.get("Weight Kg", {}).get("number"),
            "max_hr": props.get("Max HR", {}).get("number"),
        }

    async def save_workout(
        self,
        detail: Dict[str, Any],
        attachment: str,
        hr_drift: float,
        vo2max: float,
        *,
        tss: Optional[float] = None,
        intensity_factor: Optional[float] = None,
    ) -> None:
        start_date = detail.get("start_date")
        date_only = (
            start_date.split("T")[0]
            if isinstance(start_date, str) and start_date
            else datetime.utcnow().date().isoformat()
        )
        day_of_week = datetime.fromisoformat(date_only).strftime("%A")
        _ = attachment  # noqa: F841 - Preserve signature compatibility; currently unused.

        props: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": detail["name"]}}]},
            "Date": {"date": {"start": date_only}},
            "Duration [s]": {"number": detail.get("elapsed_time")},
            "Distance [m]": {"number": detail.get("distance")},
            "Elevation [m]": {"number": detail.get("total_elevation_gain")},
            "Type": {
                "rich_text": [
                    {"text": {"content": str(detail.get("type", ""))}}
                ]
            },
            "Id": {"number": detail["id"]},
            "Day of week": {"select": {"name": day_of_week}},
        }

        self._add_number_prop(props, "Average Cadence", detail.get("average_cadence"))
        self._add_number_prop(props, "Average Watts", detail.get("average_watts"))
        self._add_number_prop(
            props, "Weighted Average Watts", detail.get("weighted_average_watts")
        )
        self._add_number_prop(props, "Kilojoules", detail.get("kilojoules"))
        self._add_number_prop(props, "Kcal", detail.get("calories"))
        self._add_number_prop(props, "Average Heartrate", detail.get("average_heartrate"))
        self._add_number_prop(props, "Max Heartrate", detail.get("max_heartrate"))
        self._add_number_prop(props, "HR drift [%]", hr_drift)
        self._add_number_prop(props, "VO2 MAX [min]", vo2max)
        self._add_number_prop(props, "TSS", tss)
        self._add_number_prop(props, "IF", intensity_factor)

        description = detail.get("description")
        if description:
            props["Notes"] = {"rich_text": [{"text": {"content": description}}]}

        query_payload = {
            "filter": {"property": "Id", "number": {"equals": detail["id"]}},
            "page_size": 1,
        }
        response = await self._client.query(
            self._settings.notion_workout_database_id, query_payload
        )
        results = response.get("results", [])
        if results:
            page_id = results[0]["id"]
            await self._client.update(page_id, {"properties": props})
            return

        payload = {
            "parent": {"database_id": self._settings.notion_workout_database_id},
            "properties": props,
        }
        await self._client.create(payload)

    @staticmethod
    def _add_number_prop(
        props: Dict[str, Any], name: str, value: Optional[float]
    ) -> None:
        if value is not None:
            props[name] = {"number": value}

    @staticmethod
    def _parse_workout_page(page: Dict[str, Any]) -> Optional[WorkoutLog]:
        props = page.get("properties", {})

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

            notes_value: Optional[str] = None
            notes_payload = props.get("Notes", {}).get("rich_text")
            if notes_payload:
                notes_value = (
                    notes_payload[0]
                    .get("text", {})
                    .get("content")
                )

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
                notes=notes_value,
            )
        except Exception:
            return None


def get_workout_repository(
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> WorkoutRepository:
    """FastAPI dependency providing the concrete workout repository."""

    return NotionWorkoutRepository(settings=settings, client=client)
