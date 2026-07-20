from datetime import date, datetime, timezone

import pytest

from src.models.advice_context import (
    AdviceAthleteProfile,
    AdviceContext,
    AnalysisWindow,
    BodyAnalysis,
    CrossDomainAnalysis,
    NutritionAnalysis,
    NutritionCoverage,
    SourceStatus,
    TrainingAnalysis,
)
from src.platform.wiring import get_advice_context_use_case

pytestmark = pytest.mark.asyncio


class StubAdviceContextUseCase:
    async def __call__(self, **kwargs):
        _ = kwargs
        day = date(2026, 7, 16)
        return AdviceContext(
            generated_at=datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
            window=AnalysisWindow(
                timezone="UTC",
                start_date=day,
                end_date=day,
                requested_days=1,
                calendar_days=[day],
                current_local_date=day,
                includes_current_day=True,
            ),
            source_status=[
                SourceStatus(source="nutrition", status="ok", record_count=0),
                SourceStatus(source="withings", status="ok", record_count=0),
                SourceStatus(source="workouts", status="ok", record_count=0),
                SourceStatus(source="athlete_profile", status="ok", record_count=0),
            ],
            athlete_profile=AdviceAthleteProfile(),
            nutrition=NutritionAnalysis(
                coverage=NutritionCoverage(
                    requested_days=1,
                    days_with_entries=0,
                    days_without_entries=1,
                    recorded_day_ratio=0,
                    missing_dates=[day],
                    statistics_excluded_dates=[day],
                ),
                daily=[],
            ),
            body=BodyAnalysis(),
            training=TrainingAnalysis(),
            cross_domain=CrossDomainAnalysis(),
        )


async def test_advice_context_route_exposes_stable_contract(client, app, settings) -> None:
    app.dependency_overrides[get_advice_context_use_case] = StubAdviceContextUseCase
    try:
        response = await client.get(
            "/v2/advice-context",
            params={"days": 1, "timezone": "UTC"},
            headers={"x-api-key": settings.api_key},
        )
    finally:
        app.dependency_overrides.pop(get_advice_context_use_case, None)

    assert response.status_code == 200
    assert response.json()["context_version"] == "2.0"


@pytest.mark.parametrize(
    "path,params",
    [
        ("/v2/advice-context", {"timezone": "Invalid/Zone"}),
        ("/v2/summary-advice", {"timezone": "Invalid/Zone"}),
        ("/v2/nutrition-entries/daily/2026-07-16", {"timezone": "Invalid/Zone"}),
        (
            "/v2/nutrition-entries/period",
            {
                "start_date": "2026-07-15",
                "end_date": "2026-07-16",
                "timezone": "Invalid/Zone",
            },
        ),
    ],
)
async def test_timezone_aware_routes_reject_unknown_zone(
    client, settings, path: str, params: dict[str, str]
) -> None:
    response = await client.get(path, params=params, headers={"x-api-key": settings.api_key})

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "timezone",
                "loc": ["query", "timezone"],
                "msg": "Unknown IANA timezone",
                "input": "Invalid/Zone",
            }
        ]
    }
