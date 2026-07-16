from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from platform.config import Settings
from typing import Any, Dict, List, Optional

from ...domain.body_metrics.hr import estimate_if_tss_from_hr
from ...models.advice_context import AdviceAthleteProfile
from ...models.workout import WorkoutLog
from ...services.interfaces import NotionAPI
from ..application.ports import WorkoutRepository


class NotionWorkoutAdapter(WorkoutRepository):
    """Concrete Notion adapter for workout-related operations."""

    def __init__(self, *, settings: Settings, client: NotionAPI) -> None:
        self._settings = settings
        self._client = client

    async def list_recent_workouts(self, days: int) -> List[WorkoutLog]:
        start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        payload = {"filter": {"property": "Date", "date": {"on_or_after": start}}}
        response = await self._client.query(self._settings.notion_workout_database_id, payload)
        athlete = await self.fetch_latest_athlete_profile()
        hr_max_athlete = athlete.get("max_hr")
        hr_rest_athlete = athlete.get("resting_hr")
        workouts: List[WorkoutLog] = []
        for page in response.get("results", []):
            workout = self._parse_workout_page(page)
            if workout:
                updated = self._augment_with_estimates(
                    workout,
                    hr_max_athlete=hr_max_athlete,
                    hr_rest_athlete=hr_rest_athlete,
                )
                props = self._metric_update_props(workout, updated)
                if props:
                    await self._client.update(workout.page_id, {"properties": props})
                workouts.append(updated)
        return workouts

    async def list_workouts_in_range(
        self, start_date: date, end_date: date, timezone_name: str
    ) -> List[WorkoutLog]:
        """Read every workout page in an explicit range without mutating Notion."""
        _ = timezone_name
        payload: Dict[str, Any] = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": start_date.isoformat()}},
                    {"property": "Date", "date": {"on_or_before": end_date.isoformat()}},
                ]
            }
        }
        workouts: List[WorkoutLog] = []
        while True:
            response = await self._client.query(self._settings.notion_workout_database_id, payload)
            for page in response.get("results", []):
                workout = self._parse_workout_page(page)
                if workout is not None:
                    workouts.append(workout)
            if not response.get("has_more"):
                break
            payload["start_cursor"] = response.get("next_cursor")
        return workouts

    async def fetch_latest_athlete_profile(self) -> AdviceAthleteProfile:
        payload = {
            "sorts": [{"property": "Date", "direction": "descending"}],
            "page_size": 1,
        }
        response = await self._client.query(
            self._settings.notion_athlete_profile_database_id, payload
        )
        results = response.get("results", [])
        if not results:
            return AdviceAthleteProfile()
        props = results[0].get("properties", {})
        return AdviceAthleteProfile(
            ftp=props.get("FTP Watts", {}).get("number"),
            weight=props.get("Weight Kg", {}).get("number"),
            max_hr=props.get("Max HR", {}).get("number"),
            resting_hr=props.get("Resting HR", {}).get("number"),
            protein_min_g=props.get("Protein Minimum (g)", {}).get("number"),
            protein_target_g=props.get("Protein Target (g)", {}).get("number"),
            calorie_target_kcal=props.get("Calorie Target (kcal)", {}).get("number"),
            fat_min_g=props.get("Fat Minimum (g)", {}).get("number"),
            fat_max_g=props.get("Fat Maximum (g)", {}).get("number"),
            weekly_cycling_hours_target=props.get("Weekly Cycling Hours Target", {}).get("number"),
            weekly_cycling_load_target=props.get("Weekly Cycling Load Target", {}).get("number"),
            weekly_strength_sessions_target=props.get("Weekly Strength Sessions Target", {}).get(
                "number"
            ),
            timezone=props.get("Timezone", {})
            .get("rich_text", [{}])[0]
            .get("text", {})
            .get("content")
            if props.get("Timezone", {}).get("rich_text")
            else None,
        )

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
        if intensity_factor is None or tss is None:
            estimate = await self._estimate_metrics(detail)
            if estimate:
                if intensity_factor is None:
                    intensity_factor = estimate[0]
                if tss is None:
                    tss = estimate[1]

        tss_origin, load_family = self._resolve_load_provenance(detail, tss)

        start_date = detail.get("start_date")
        date_only = (
            start_date.split("T")[0]
            if isinstance(start_date, str) and start_date
            else datetime.now(timezone.utc).date().isoformat()
        )
        day_of_week = datetime.fromisoformat(date_only).strftime("%A")
        _ = attachment  # noqa: F841 - Preserve signature compatibility; currently unused.

        props: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": detail["name"]}}]},
            "Date": {"date": {"start": date_only}},
            "Duration [s]": {"number": detail.get("elapsed_time")},
            "Distance [m]": {"number": detail.get("distance")},
            "Elevation [m]": {"number": detail.get("total_elevation_gain")},
            "Type": {"rich_text": [{"text": {"content": str(detail.get("type") or "Gym")}}]},
            "Id": {"number": detail["id"]},
            "Day of week": {"select": {"name": day_of_week}},
        }
        self._add_date_prop(props, "Start Time", detail.get("start_date"))
        self._add_text_prop(props, "External ID", detail.get("external_id"))
        self._add_text_prop(props, "Provider Source", detail.get("provider_source"))
        self._add_text_prop(props, "Provider Client", detail.get("provider_client_name"))
        self._add_text_prop(props, "Device", detail.get("device_name"))
        self._add_text_prop(props, "Payload Key", detail.get("payload_key"))
        self._add_text_prop(props, "TSS Origin", tss_origin)
        self._add_text_prop(props, "Load Family", load_family)

        self._add_number_prop(props, "Average Cadence", detail.get("average_cadence"))
        self._add_number_prop(props, "Average Watts", detail.get("average_watts"))
        self._add_number_prop(props, "Weighted Average Watts", detail.get("weighted_average_watts"))
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

    async def _estimate_metrics(self, detail: Dict[str, Any]) -> Optional[tuple[float, float]]:
        athlete = await self.fetch_latest_athlete_profile()
        return estimate_if_tss_from_hr(
            hr_avg_session=detail.get("average_heartrate"),
            hr_max_session=detail.get("max_heartrate"),
            dur_s=detail.get("moving_time") or detail.get("elapsed_time"),
            hr_max_athlete=athlete.get("max_hr"),
            hr_rest_athlete=athlete.get("resting_hr"),
            kcal=detail.get("calories"),
        )

    @staticmethod
    def _resolve_load_provenance(
        detail: Dict[str, Any], tss: Optional[float]
    ) -> tuple[Optional[str], Optional[str]]:
        origin = detail.get("tss_origin")
        if origin is None and tss is not None:
            if detail.get("provider_training_load") is not None:
                origin = "provider"
            elif detail.get("weighted_average_watts") is not None:
                origin = "power_derived"
            elif detail.get("average_heartrate") is not None:
                origin = "hr_estimated"
            else:
                origin = "unknown"
        family = detail.get("load_family")
        if family is None and origin is not None:
            family = {
                "provider": "provider_training_load",
                "power_derived": "power_derived_tss",
                "hr_estimated": "hr_estimated_load",
            }.get(origin, "unknown_load")
        return origin, family

    async def fill_missing_metrics(self, page_id: str) -> Optional[WorkoutLog]:
        page = await self._client.retrieve(page_id)
        workout = self._parse_workout_page(page)
        if workout is None:
            return None

        athlete = await self.fetch_latest_athlete_profile()
        updated = self._augment_with_estimates(
            workout,
            hr_max_athlete=athlete.get("max_hr"),
            hr_rest_athlete=athlete.get("resting_hr"),
        )

        props = self._metric_update_props(workout, updated)
        if props:
            await self._client.update(page_id, {"properties": props})

        return updated

    @classmethod
    def _metric_update_props(cls, workout: WorkoutLog, updated: WorkoutLog) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        if workout.type != updated.type:
            props["Type"] = {"rich_text": [{"text": {"content": updated.type}}]}
        if workout.tss != updated.tss:
            cls._add_number_prop(props, "TSS", updated.tss)
        if workout.intensity_factor != updated.intensity_factor:
            cls._add_number_prop(props, "IF", updated.intensity_factor)
        return props

    @staticmethod
    def _add_number_prop(props: Dict[str, Any], name: str, value: Optional[float]) -> None:
        if value is not None:
            props[name] = {"number": value}

    @staticmethod
    def _add_text_prop(props: Dict[str, Any], name: str, value: Any) -> None:
        if value is not None:
            props[name] = {"rich_text": [{"text": {"content": str(value)}}]}

    @staticmethod
    def _add_date_prop(props: Dict[str, Any], name: str, value: Any) -> None:
        if isinstance(value, str) and value:
            props[name] = {"date": {"start": value}}

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

        def _get_text(name: str) -> Optional[str]:
            payload = props.get(name, {})
            values = payload.get("rich_text") or payload.get("title") or []
            return values[0].get("text", {}).get("content") if values else None

        try:
            type_value = NotionWorkoutAdapter._extract_workout_type(props)
            notes_value = NotionWorkoutAdapter._extract_workout_notes(props)
            return WorkoutLog(
                page_id=str(page.get("id") or ""),
                name=_get_title("Name"),
                date=_get_date("Date"),
                start_time=_parse_datetime(_get_date("Start Time") or _get_date("Date")),
                external_id=_get_text("External ID"),
                provider_source=_get_text("Provider Source"),
                provider_client_name=_get_text("Provider Client"),
                device_name=_get_text("Device"),
                payload_key=_get_text("Payload Key"),
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
                tss_origin=_get_text("TSS Origin"),
                load_family=_get_text("Load Family"),
                notes=notes_value,
            )
        except Exception:
            return None

    @staticmethod
    def _extract_workout_type(props: Dict[str, Any]) -> str:
        type_payload = props.get("Type", {})
        if rich_text := type_payload.get("rich_text"):
            return rich_text[0].get("text", {}).get("content", "")
        if select_payload := type_payload.get("select"):
            return select_payload.get("name", "")
        return ""

    @staticmethod
    def _extract_workout_notes(props: Dict[str, Any]) -> Optional[str]:
        notes_payload = props.get("Notes", {}).get("rich_text")
        if not notes_payload:
            return None
        return notes_payload[0].get("text", {}).get("content")

    @staticmethod
    def _augment_with_estimates(
        workout: WorkoutLog,
        *,
        hr_max_athlete: Optional[float],
        hr_rest_athlete: Optional[float],
    ) -> WorkoutLog:
        updates: Dict[str, Any] = {}

        needs_hr_metrics = (
            (workout.intensity_factor is None or workout.tss is None)
            and workout.average_heartrate is not None
            and workout.max_heartrate is not None
            and workout.duration_s > 0
            and hr_max_athlete is not None
        )

        if needs_hr_metrics:
            estimate = estimate_if_tss_from_hr(
                hr_avg_session=workout.average_heartrate,
                hr_max_session=workout.max_heartrate,
                dur_s=workout.duration_s,
                hr_max_athlete=hr_max_athlete,
                hr_rest_athlete=hr_rest_athlete,
                kcal=workout.kcal,
            )
            if estimate:
                if workout.intensity_factor is None:
                    updates["intensity_factor"] = estimate[0]
                if workout.tss is None:
                    updates["tss"] = estimate[1]

        if not workout.type:
            updates["type"] = "Gym"

        if updates:
            return workout.model_copy(update=updates)
        return workout


def create_notion_workout_adapter(*, settings: Settings, client: NotionAPI) -> WorkoutRepository:
    """Create a Notion workout adapter without relying on FastAPI wiring."""
    return NotionWorkoutAdapter(settings=settings, client=client)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
