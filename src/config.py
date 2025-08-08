from __future__ import annotations

import os
from typing import Final, Optional, Dict

API_KEY: Optional[str] = os.getenv("API_KEY")
NOTION_SECRET: Optional[str] = os.getenv("LLM_Update")
NOTION_DATABASE_ID: Optional[str] = os.getenv("NOTION_DATABASE_ID")

NOTION_HEADERS: Final[Dict[str, str]] = {
    "Authorization": f"Bearer {NOTION_SECRET}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
