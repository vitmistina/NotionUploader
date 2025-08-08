"""Generate an OpenAPI schema file for the FastAPI application."""

from pathlib import Path
import json

from src.main import app


def generate_openapi() -> None:
    """Write the current OpenAPI schema to ``openapi.json``."""
    schema = app.openapi()
    output_path = Path(__file__).resolve().parent / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))


if __name__ == "__main__":
    generate_openapi()

