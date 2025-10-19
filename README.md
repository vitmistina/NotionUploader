# NotionUploader

FastAPI service that syncs nutrition, workout, and biometric data from external providers (Strava, Withings, custom integrations) into Notion databases. The API powers both manual uploads and automated webhooks deployed on Render.

## Architecture at a Glance
- **API surface**: `src/routes/` defines versioned FastAPI routers (nutrition, metrics, workouts, advice, Strava) secured by an API key middleware and exposed through `src/main.py`.
- **Integrations**: Provider-specific clients live in `src/services/` and `src/withings.py` / `src/strava.py`. Shared helpers reside in `src/metrics.py` and `src/notion/`.
- **Configuration**: `src/settings.py` centralizes environment variables with Pydantic settings and supports Render's uppercase environment naming.
- **Schemas**: `openapi.json` is generated from the running app via `python generate_openapi.py` when routes or models change.

## Prerequisites
- Python 3.11+
- Access to the required external credentials (Notion, Strava, Withings, Upstash Redis)

> **Virtual environments are mandatory** for both human contributors and automation. Always install dependencies inside `.venv/` using `python -m venv .venv` before touching `pip`.

## Quickstart
```bash
# 1. Create and activate an isolated environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install runtime and tooling dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Provide secrets (Render uses uppercase env vars automatically)
# Create .env and populate it with the variables listed below for local development

# 4. Launch the API locally
uvicorn src.main:app --reload
```

With the server running, `/` and `/healthz` provide lightweight health checks, while the authenticated API lives under `/v2`. Regenerate the OpenAPI description after changing models or routes:

```bash
python generate_openapi.py
```

## Configuration Reference
Define the following variables (case insensitive thanks to `SettingsConfigDict(case_sensitive=False)`):

| Variable | Description |
| --- | --- |
| `API_KEY` | Shared secret for API-key auth enforced by `src/security.py`. |
| `NOTION_SECRET` | Notion integration secret used by Notion client wrappers. |
| `NOTION_DATABASE_ID` | Target Notion database for nutrition entries. |
| `NOTION_WORKOUT_DATABASE_ID` | Notion database receiving workout logs. |
| `NOTION_ATHLETE_PROFILE_DATABASE_ID` | Profile database storing athlete metadata. |
| `STRAVA_VERIFY_TOKEN` | Verification token for Strava webhook handshakes. |
| `WBSAPI_URL` | Withings API base URL. |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Credentials for Redis-backed caching. |
| `WITHINGS_CLIENT_ID` / `WITHINGS_CLIENT_SECRET` | OAuth credentials for Withings integration. |
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | OAuth credentials for Strava integration. |

In Render, configure these values as dashboard environment variables; deployment webhooks automatically apply them.

## Testing & Quality Gates
```bash
source .venv/bin/activate
pytest -q
ruff check --fix src tests
ruff check src tests
```

Run tests and linting before every commit to keep CI green. Agents interacting with this repository should follow the same workflow inside their own virtual environment.

## Contribution Workflow Expectations
- **Stay in `.venv/`**: Never install requirements globally; recreate the virtual environment if dependency resolution drifts.
- **Sync contracts**: When FastAPI routes or models change, regenerate `openapi.json` with `python generate_openapi.py` and commit the result.
- **Review the README**: Treat this document as the source of truth for setup and deployment. Re-read it after each change and update any sections impacted by your modifications before merging.

## Deployment Notes
- Render deploys this service via webhook; health checks hit `/healthz`.
- The production OpenAPI schema is exposed at `/v2/api-schema` with the server URL pre-set to Render (`https://notionuploader-groa.onrender.com`).
- Ensure any schema or requirements changes are committed together so the Render build installs the correct dependencies.

## Repository Map
```
.
├── src/            # Application code, routers, services, settings
├── tests/          # Pytest suite covering API behavior and integrations
├── examples/       # Sample payloads and workflows for manual testing
├── generate_openapi.py
├── render.yaml     # Render infrastructure definition
├── requirements.txt
└── openapi.json    # Generated API contract (keep in sync with code)
```
