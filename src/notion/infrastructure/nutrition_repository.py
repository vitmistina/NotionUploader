from __future__ import annotations

from platform.config import Settings
from typing import Any, Dict, List, Optional

from ...models.nutrition import NutritionEntry
from ...services.interfaces import NotionAPI
from ..application.ports import NutritionRepository


class NotionNutritionAdapter(NutritionRepository):
    """Concrete Notion adapter handling nutrition persistence and queries."""

    def __init__(self, *, settings: Settings, client: NotionAPI) -> None:
        self._settings = settings
        self._client = client

    async def create_entry(self, entry: NutritionEntry) -> None:
        payload: Dict[str, Any] = {
            "parent": {"database_id": self._settings.notion_database_id},
            "properties": {
                "Food Item": {"title": [{"text": {"content": entry.food_item}}]},
                "Date": {"date": {"start": entry.date}},
                "Calories": {"number": entry.calories},
                "Protein (g)": {"number": entry.protein_g},
                "Carbs (g)": {"number": entry.carbs_g},
                "Fat (g)": {"number": entry.fat_g},
                "Meal Type": {"select": {"name": entry.meal_type}},
            },
        }
        if entry.notes:
            payload["properties"]["Notes"] = {
                "rich_text": [{"text": {"content": entry.notes}}],
            }
        await self._client.create(payload)

    async def list_entries_on_date(self, date: str) -> List[NutritionEntry]:
        return await self._query_entries(
            {"property": "Date", "date": {"equals": date}}
        )

    async def list_entries_in_range(
        self, start_date: str, end_date: str
    ) -> List[NutritionEntry]:
        return await self._query_entries(
            {
                "and": [
                    {"property": "Date", "date": {"on_or_after": start_date}},
                    {"property": "Date", "date": {"on_or_before": end_date}},
                ]
            }
        )

    async def _query_entries(self, filter_payload: Dict[str, Any]) -> List[NutritionEntry]:
        payload: Dict[str, Any] = {"filter": filter_payload}
        entries: List[NutritionEntry] = []
        while True:
            response: Dict[str, Any] = await self._client.query(
                self._settings.notion_database_id, payload
            )
            for page in response.get("results", []):
                entry = self._parse_page(page)
                if entry is not None:
                    entries.append(entry)
            if not response.get("has_more"):
                break
            payload["start_cursor"] = response.get("next_cursor")
        return entries

    @staticmethod
    def _parse_page(page: Dict[str, Any]) -> Optional[NutritionEntry]:
        props: Dict[str, Any] = page.get("properties", {})
        try:
            food_item = ""
            food_title = props.get("Food Item", {}).get("title", [])
            if food_title:
                food_item = food_title[0].get("text", {}).get("content", "")

            date_value = ""
            date_payload = props.get("Date", {}).get("date")
            if date_payload:
                date_value = date_payload.get("start", "") or ""

            notes_value = ""
            notes_payload = props.get("Notes", {}).get("rich_text", [])
            if notes_payload:
                notes_value = notes_payload[0].get("text", {}).get("content", "")

            meal_payload = props.get("Meal Type", {}).get("select")
            meal_type = meal_payload.get("name") if meal_payload else ""

            return NutritionEntry(
                page_id=page.get("id"),
                food_item=food_item,
                date=date_value,
                calories=props.get("Calories", {}).get("number"),
                protein_g=props.get("Protein (g)", {}).get("number"),
                carbs_g=props.get("Carbs (g)", {}).get("number"),
                fat_g=props.get("Fat (g)", {}).get("number"),
                meal_type=meal_type,
                notes=notes_value,
            )
        except Exception:
            return None


def create_notion_nutrition_adapter(
    *, settings: Settings, client: NotionAPI
) -> NutritionRepository:
    """Create a Notion nutrition adapter without relying on FastAPI wiring."""
    return NotionNutritionAdapter(settings=settings, client=client)
