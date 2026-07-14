"""Self-tests for shared test doubles."""

from __future__ import annotations

import pytest

from tests.conftest import NotionAPIStub, RedisFake, IntervalsSyncCoordinatorSpy, WithingsPortFake


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


def test_intervals_sync_coordinator_spy_reports_unconsumed_expectation_payload() -> None:
    """Unconsumed Intervals expectations identify the queued method and expected payload."""

    spy = IntervalsSyncCoordinatorSpy()
    spy.expect_sync(
        lookback_days=42,
        returns=__import__(
            "src.intervals_icu.application", fromlist=["IntervalsSyncResult"]
        ).IntervalsSyncResult(
            status="ok",
            oldest=__import__("datetime").date(2026, 7, 7),
            newest=__import__("datetime").date(2026, 7, 14),
            lookback_days=42,
            discovered=0,
            eligible=0,
            processed=0,
            skipped=0,
            failed=0,
        ),
    )

    with pytest.raises(AssertionError, match="sync_recent.*lookback_days.*42"):
        spy.assert_no_pending_expectations()
