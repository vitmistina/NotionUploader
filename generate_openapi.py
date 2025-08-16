"""Generate an OpenAPI schema file for the FastAPI application."""

from pathlib import Path
import json

from src.main import app


def generate_openapi() -> None:
    """Write the current OpenAPI schema to ``openapi.json``."""
    schema = app.openapi()
    schema["servers"] = [
        {"url": "https://notionuploader-groa.onrender.com"}
    ]

    # Mark all operations as non-consequential so they can be always allowed
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation["x-openai-isConsequential"] = False
                operation["is_consequential"] = False
    output_path = Path(__file__).resolve().parent / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))


if __name__ == "__main__":
    generate_openapi()

