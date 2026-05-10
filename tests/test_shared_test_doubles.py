"""Self-tests for shared test doubles."""

from __future__ import annotations

import pytest

from tests.conftest import NotionAPIStub, RedisFake, StravaCoordinatorSpy, WithingsPortFake


def test_redis_fake_reports_unconsumed_expectation_payload() -> None:
    """Unconsumed Redis expectations fail with method and payload details."""

    fake = RedisFake()
    fake.expect_set("token", "value", ex=60)

    with pytest.raises(AssertionError, match="set\\(key='token', value='value', ex=60\\)"):
        fake.assert_no_pending_expectations()


def test_notion_api_stub_reports_unconsumed_expectation_payload() -> None:
    """Unconsumed Notion expectations identify the queued method and expected payload."""

    stub = NotionAPIStub()
    stub.expect_query(database_id="db", payload={"filter": {"property": "Date"}})

    with pytest.raises(AssertionError, match="query.*database_id.*db.*filter"):
        stub.assert_no_pending_expectations()


def test_withings_port_fake_reports_unconsumed_expectation_payload() -> None:
    """Unconsumed Withings expectations identify the queued method and expected payload."""

    fake = WithingsPortFake()
    fake.expect_fetch_measurements(days=7, returns=[{"weight": 70}])

    with pytest.raises(AssertionError, match="fetch_measurements.*days.*7.*weight"):
        fake.assert_no_pending_expectations()


def test_strava_coordinator_spy_reports_unconsumed_expectation_payload() -> None:
    """Unconsumed Strava expectations identify the queued method and expected payload."""

    spy = StravaCoordinatorSpy()
    spy.expect_process_activity(activity_id=42)

    with pytest.raises(AssertionError, match="process_activity.*activity_id.*42"):
        spy.assert_no_pending_expectations()
