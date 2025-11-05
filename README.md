# NotionUploader

FastAPI service that syncs nutrition, workout, and biometric data from external providers (Strava, Withings, custom integrations) into Notion databases. The API powers both manual uploads and automated webhooks deployed on Render.

## Architecture at a Glance
- **API surface**: `src/routes/` defines versioned FastAPI routers (nutrition, metrics, workouts, advice, Strava) secured by an API key middleware and exposed through `src/main.py`.
- **Integrations**: Provider-specific clients live in `src/services/` and `src/withings.py` / `src/strava.py`. Shared helpers reside in `src/domain/` and `src/notion/`.
- **Configuration**: `src/platform/config.py` centralizes environment variables with Pydantic settings and supports Render's uppercase environment naming.
- **Schemas**: `openapi.json` is generated from the running app via `uv run python generate_openapi.py` when routes or models change.

## Prerequisites
- Python 3.11+
- Access to the required external credentials (Notion, Strava, Withings, Upstash Redis)

> **Project-local environments are mandatory** for both human contributors and automation. Create them with `uv` so dependency resolution stays consistent across contributors and CI.

## Quickstart
```bash
# 1. Create an isolated environment managed by uv
uv venv
source .venv/bin/activate   # POSIX shells
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows Command Prompt: .venv\Scripts\activate.bat

# 2. Install runtime and tooling dependencies declared in pyproject.toml / uv.lock
uv sync --dev

# 3. Provide secrets (Render uses uppercase env vars automatically)
# Create .env and populate it with the variables listed below for local development

# 4. Launch the API locally
uv run uvicorn src.main:app --reload
```

With the server running, `/` and `/healthz` provide lightweight health checks, while the authenticated API lives under `/v2`. Regenerate the OpenAPI description after changing models or routes:

```bash
uv run python generate_openapi.py
```

## Configuration Reference
Define the following variables (case insensitive thanks to `SettingsConfigDict(case_sensitive=False)`):

| Variable | Description |
| --- | --- |
| `API_KEY` | Shared secret for API-key auth enforced by `src/platform/security.py`. |
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
uv run import-linter
uv run ruff check
uv run pytest --cov=src --cov-report=term-missing
```

Run the import boundary checks, linter, and coverage-enabled tests before every commit to keep CI green. Agents interacting with this repository should follow the same workflow inside their own virtual environment.

## Contribution Workflow Expectations
- **Stay in `.venv/`**: Never install dependencies globally; recreate the virtual environment with `uv venv` / `uv sync` if dependency resolution drifts.
- **Sync contracts**: When FastAPI routes or models change, regenerate `openapi.json` with `uv run python generate_openapi.py` and commit the result.
- **Review the README**: Treat this document as the source of truth for setup and deployment. Re-read it after each change and update any sections impacted by your modifications before merging.

## Deployment Notes
- Render deploys this service via webhook; health checks hit `/healthz`.
- The production OpenAPI schema is exposed at `/v2/api-schema` with the server URL pre-set to Render (`https://notionuploader-groa.onrender.com`).
- Ensure any schema or dependency changes are committed together so the Render build installs the correct versions from `uv.lock`.

## Repository Map
```
.
├── src/            # Application code, routers, services, and platform wiring
├── tests/          # Pytest suite covering API behavior and integrations
├── examples/       # Sample payloads and workflows for manual testing
├── generate_openapi.py
├── render.yaml     # Render infrastructure definition
├── pyproject.toml  # Project metadata and dependency declarations
├── uv.lock         # Locked dependency versions resolved by uv
└── openapi.json    # Generated API contract (keep in sync with code)
```
