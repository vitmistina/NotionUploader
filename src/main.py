from fastapi import FastAPI, HTTPException, Depends, Query, Path, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Literal
import httpx
import os

API_KEY = os.getenv("API_KEY")
NOTION_SECRET = os.getenv("LLM_Update")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


api_key_header = APIKeyHeader(name="x-api-key", scheme_name="ApiKeyAuth", auto_error=False)


def verify_api_key(x_api_key: str = Security(api_key_header)):
    if API_KEY is None:
        raise RuntimeError("API_KEY is not set")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(
    title="Nutrition Logger",
    version="2.0.0",
    description="Logs food and macro data to Vit's Notion table",
    dependencies=[Depends(verify_api_key)],
)


class NutritionEntry(BaseModel):
    food_item: str
    date: str  # Consider refining this to a date type later
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: Literal[
        "Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"
    ]
    notes: str = Field(..., min_length=1)


NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_SECRET}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


async def _submit_to_notion(entry: NutritionEntry) -> dict:
    """Create a page in the configured Notion database for the entry."""
    payload = {
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
        response = await client.post(
            "https://api.notion.com/v1/pages", json=payload, headers=NOTION_HEADERS
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return {"status": "success"}


def _parse_page(page: dict) -> NutritionEntry | None:
    props = page["properties"]
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


async def _query_entries(filter_payload: dict) -> list[NutritionEntry]:
    notion_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            notion_url, json={"filter": filter_payload}, headers=NOTION_HEADERS
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    results = response.json().get("results", [])
    entries = []
    for page in results:
        entry = _parse_page(page)
        if entry:
            entries.append(entry)
    return entries


async def _entries_on_date(date: str) -> list[NutritionEntry]:
    return await _query_entries({"property": "Date", "date": {"equals": date}})


async def _entries_in_range(start_date: str, end_date: str) -> list[NutritionEntry]:
    return await _query_entries(
        {
            "and": [
                {"property": "Date", "date": {"on_or_after": start_date}},
                {"property": "Date", "date": {"on_or_before": end_date}},
            ]
        }
    )


@app.post("/", status_code=200)
async def log_nutrition(entry: NutritionEntry):
    return await _submit_to_notion(entry)


@app.post("/v2/nutrition-entries", status_code=201)
async def create_nutrition_entry(entry: NutritionEntry):
    return await _submit_to_notion(entry)


@app.get("/foods", response_model=list[NutritionEntry])
async def get_foods_by_date(
    date: str = Query(
        ..., description="The date for which to retrieve food entries (YYYY-MM-DD)"
    )
):
    return await _entries_on_date(date)


@app.get("/v2/nutrition-entries/daily/{date}", response_model=list[NutritionEntry])
async def list_daily_nutrition_entries(
    date: str = Path(..., description="Date to fetch in YYYY-MM-DD format.")
):
    return await _entries_on_date(date)


@app.get("/foods-range", response_model=list[NutritionEntry])
async def get_foods_by_date_range(
    start_date: str = Query(..., description="The start date (YYYY-MM-DD, inclusive)"),
    end_date: str = Query(..., description="The end date (YYYY-MM-DD, inclusive)"),
):
    return await _entries_in_range(start_date, end_date)


@app.get("/v2/nutrition-entries/period", response_model=list[NutritionEntry])
async def list_nutrition_entries_by_period(
    start_date: str = Query(
        ..., description="Start date (inclusive) in YYYY-MM-DD format."
    ),
    end_date: str = Query(
        ..., description="End date (inclusive) in YYYY-MM-DD format."
    ),
):
    return await _entries_in_range(start_date, end_date)


@app.get("/openapi", include_in_schema=False)
@app.get("/v2/api-schema")
async def get_api_schema():
    """Return the OpenAPI schema for this API version."""
    return JSONResponse(app.openapi())

