from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models.nutrition import NutritionEntry, StatusResponse
from .services.notion import NotionClient
from .settings import Settings

async def submit_to_notion(
    entry: NutritionEntry, settings: Settings, client: NotionClient
) -> StatusResponse:
    """Create a page in the configured Notion database for the entry."""
    payload: Dict[str, Any] = {
        "parent": {"database_id": settings.notion_database_id},
        "properties": {
            "Food Item": {"title": [{"text": {"content": entry.food_item}}]},
            "Date": {"date": {"start": entry.date}},
            "Calories": {"number": entry.calories},
            "Protein (g)": {"number": entry.protein_g},
            "Carbs (g)": {"number": entry.carbs_g},
            "Fat (g)": {"number": entry.fat_g},
            "Meal Type": {"select": {"name": entry.meal_type}},
            "Notes": {"rich_text": [{"text": {"content": entry.notes}}]},
        },
    }
    await client.create(payload)
    return StatusResponse(status="success")

def parse_page(page: Dict[str, Any]) -> Optional[NutritionEntry]:
    props: Dict[str, Any] = page["properties"]
    try:
        return NutritionEntry(
            food_item=props["Food Item"]["title"][0]["text"]["content"]
            if props["Food Item"]["title"]
            else "",
            date=props["Date"]["date"]["start"] if props["Date"]["date"] else "",
            calories=props["Calories"]["number"],
            protein_g=props["Protein (g)"]["number"],
            carbs_g=props["Carbs (g)"]["number"],
            fat_g=props["Fat (g)"]["number"],
            meal_type=
            props["Meal Type"]["select"]["name"] if props["Meal Type"]["select"] else "",
            notes=
            props["Notes"]["rich_text"][0]["text"]["content"]
            if props["Notes"]["rich_text"]
            else "",
        )
    except Exception:
        return None

async def query_entries(
    filter_payload: Dict[str, Any], settings: Settings, client: NotionClient
) -> List[NutritionEntry]:
    results: List[Dict[str, Any]] = await client.query(
        settings.notion_database_id, {"filter": filter_payload}
    )
    entries: List[NutritionEntry] = []
    for page in results:
        entry: Optional[NutritionEntry] = parse_page(page)
        if entry is not None:
            entries.append(entry)
    return entries

async def entries_on_date(
    date: str, settings: Settings, client: NotionClient
) -> List[NutritionEntry]:
    return await query_entries(
        {"property": "Date", "date": {"equals": date}}, settings, client
    )

async def entries_in_range(
    start_date: str,
    end_date: str,
    settings: Settings,
    client: NotionClient,
) -> List[NutritionEntry]:
    return await query_entries(
        {
            "and": [
                {"property": "Date", "date": {"on_or_after": start_date}},
                {"property": "Date", "date": {"on_or_before": end_date}},
            ]
        },
        settings,
        client,
    )
