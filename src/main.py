from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal
import httpx
import os

API_KEY = os.getenv("API_KEY")
NOTION_SECRET = os.getenv("LLM_Update")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


def verify_api_key(x_api_key: str = Header(...)):
    if API_KEY is None:
        raise RuntimeError("API_KEY is not set")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

app = FastAPI(dependencies=[Depends(verify_api_key)])


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Nutrition Logger",
        version="1.0.0",
        description="Logs food and macro data to Vit's Notion table",
        routes=app.routes,
    )
    openapi_schema["servers"] = [
        {"url": "https://notionuploader-groa.onrender.com"}
    ]
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "ApiKeyAuth"
    ] = {
        "type": "apiKey",
        "in": "header",
        "name": "x-api-key",
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


class NutritionEntry(BaseModel):
    food_item: str
    date: str  # You could refine this to date format later
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: Literal[
        "Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"
    ]
    notes: str = Field(..., min_length=1)


@app.post("/")
async def log_nutrition(entry: NutritionEntry):
    notion_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_SECRET}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # This payload assumes your Notion table uses property names exactly as shown
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
            "Notes": {"rich_text": [{"text": {"content": entry.notes}}]}
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(notion_url, json=payload, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return {"status": "success"}


@app.get("/foods", response_model=list[NutritionEntry])
async def get_foods_by_date(date: str = Query(..., description="The date for which to retrieve food entries (YYYY-MM-DD)")):
    notion_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_SECRET}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    # Notion filter for exact date match
    payload = {
        "filter": {
            "property": "Date",
            "date": {"equals": date}
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(notion_url, json=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    results = response.json().get("results", [])
    entries = []
    for page in results:
        props = page["properties"]
        try:
            entry = NutritionEntry(
                food_item=props["Food Item"]["title"][0]["text"]["content"] if props["Food Item"]["title"] else "",
                date=props["Date"]["date"]["start"] if props["Date"]["date"] else "",
                calories=props["Calories"]["number"],
                protein_g=props["Protein (g)"]["number"],
                carbs_g=props["Carbs (g)"]["number"],
                fat_g=props["Fat (g)"]["number"],
                meal_type=props["Meal Type"]["select"]["name"] if props["Meal Type"]["select"] else "",
                notes=props["Notes"]["rich_text"][0]["text"]["content"] if props["Notes"]["rich_text"] else ""
            )
            entries.append(entry)
        except Exception as e:
            continue  # skip malformed entries
    return entries


@app.get("/openapi", include_in_schema=False)
async def get_openapi_endpoint():
    """Return the OpenAPI schema for this application."""
    return JSONResponse(app.openapi())
