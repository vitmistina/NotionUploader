from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from .config import NOTION_DATABASE_ID, NOTION_HEADERS
from .models import NutritionEntry, StatusResponse

async def submit_to_notion(entry: NutritionEntry) -> StatusResponse:
    """Create a page in the configured Notion database for the entry."""
    payload: Dict[str, Any] = {
        "parent": {"database_id": NOTION_DATABASE_ID},
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
    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.post(
            "https://api.notion.com/v1/pages", json=payload, headers=NOTION_HEADERS
        )
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

async def query_entries(filter_payload: Dict[str, Any]) -> List[NutritionEntry]:
    notion_url: str = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.post(
            notion_url, json={"filter": filter_payload}, headers=NOTION_HEADERS
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    results: List[Dict[str, Any]] = response.json().get("results", [])
    entries: List[NutritionEntry] = []
    for page in results:
        entry: Optional[NutritionEntry] = parse_page(page)
        if entry is not None:
            entries.append(entry)
    return entries

async def entries_on_date(date: str) -> List[NutritionEntry]:
    return await query_entries({"property": "Date", "date": {"equals": date}})

async def entries_in_range(start_date: str, end_date: str) -> List[NutritionEntry]:
    return await query_entries(
        {
            "and": [
                {"property": "Date", "date": {"on_or_after": start_date}},
                {"property": "Date", "date": {"on_or_before": end_date}},
            ]
        }
    )
