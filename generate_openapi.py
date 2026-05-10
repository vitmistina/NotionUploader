"""Generate an OpenAPI schema file for the FastAPI application."""

import json
from pathlib import Path

from src.main import app, build_openapi_schema


def generate_openapi() -> None:
    """Write the current OpenAPI schema to ``openapi.json``."""
    schema = build_openapi_schema(app)
    output_path = Path(__file__).resolve().parent / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))


if __name__ == "__main__":
    generate_openapi()

