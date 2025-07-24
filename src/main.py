from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
import httpx
import os

app = FastAPI()

# ENV VARIABLE: NOTION_SECRET should be set in your Render dashboard
NOTION_SECRET = os.getenv("LLM_Update")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_SECRET:
    raise RuntimeError("LLM_Update secret not set")

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
