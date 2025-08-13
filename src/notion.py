from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from .models import NutritionEntry, StatusResponse
from .settings import Settings

async def submit_to_notion(entry: NutritionEntry, settings: Settings) -> StatusResponse:
    """Create a page in the configured Notion database for the entry."""
    headers = {
        "Authorization": f"Bearer {settings.notion_secret}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
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
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response: httpx.Response = await client.post(
                "https://api.notion.com/v1/pages",
                json=payload,
                headers=headers,
            )
    except httpx.ReadTimeout as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=504, detail="Request to Notion timed out") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
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
    filter_payload: Dict[str, Any], settings: Settings
) -> List[NutritionEntry]:
    notion_url: str = f"https://api.notion.com/v1/databases/{settings.notion_database_id}/query"
    headers = {
        "Authorization": f"Bearer {settings.notion_secret}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response: httpx.Response = await client.post(
                notion_url,
                json={"filter": filter_payload},
                headers=headers,
            )
    except httpx.ReadTimeout as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=504, detail="Request to Notion timed out") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    results: List[Dict[str, Any]] = response.json().get("results", [])
    entries: List[NutritionEntry] = []
    for page in results:
        entry: Optional[NutritionEntry] = parse_page(page)
        if entry is not None:
            entries.append(entry)
    return entries

async def entries_on_date(date: str, settings: Settings) -> List[NutritionEntry]:
    return await query_entries(
        {"property": "Date", "date": {"equals": date}}, settings
    )

async def entries_in_range(
    start_date: str, end_date: str, settings: Settings
) -> List[NutritionEntry]:
    return await query_entries(
        {
            "and": [
                {"property": "Date", "date": {"on_or_after": start_date}},
                {"property": "Date", "date": {"on_or_before": end_date}},
            ]
        },
        settings,
    )
