"""Shared test fixtures and doubles."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import main
from src.intervals_icu.application import IntervalsSyncResult
from src.services.interfaces import NotionAPI
from src.services.notion import get_notion_client
from platform.clients import RedisClient, get_redis
from platform.config import Settings, get_settings
from src.platform.wiring import (
    provide_intervals_sync_coordinator,
    provide_withings_port,
)
from src.withings.application.ports import WithingsMeasurementsPort

from tests.fakes import NotionWorkoutFake


_MISSING = object()


class RedisFake(RedisClient):
    """In-memory Redis double that records interactions."""

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self._expected_gets: list[tuple[str | None, Optional[str]]] = []
        self._expected_sets: list[tuple[str | None, Optional[str], object]] = []
        self._last_get: str | None = None
        self._last_set: tuple[str, str, Optional[int]] | None = None
        self.expirations: Dict[str, Optional[int]] = {}

    def expect_get(self, key: str | None = None, *, returns: Optional[str] = None) -> "RedisFake":
        """Queue an expected ``get`` call and optional return value."""

        self._expected_gets.append((key, returns))
        return self

    def expect_set(
        self,
        key: str | None = None,
        value: Optional[str] = None,
        *,
        ex: object = _MISSING,
    ) -> "RedisFake":
        """Queue an expected ``set`` call."""

        self._expected_sets.append((key, value, ex))
        return self

    def assert_last_get(self, key: str) -> None:
        """Assert the most recent ``get`` call was for ``key``."""

        assert self._last_get == key, f"Expected last get for {key!r}, saw {self._last_get!r}"

    def assert_last_set(
        self, key: str, value: Optional[str] = None, *, ex: Optional[int] = None
    ) -> None:
        """Assert the most recent ``set`` call matched the provided values."""

        assert self._last_set is not None, "No set() call was recorded"
        last_key, last_value, last_ex = self._last_set
        assert last_key == key, f"Expected last set for {key!r}, saw {last_key!r}"
        if value is not None:
            assert last_value == value, f"Expected last set value {value!r}, saw {last_value!r}"
        if ex is not None:
            assert last_ex == ex, f"Expected last set ex {ex!r}, saw {last_ex!r}"

    def assert_no_pending_expectations(self) -> None:
        """Assert all queued Redis expectations were consumed."""

        pending = []
        pending.extend(
            f"get(key={key!r}, returns={returns!r})" for key, returns in self._expected_gets
        )
        pending.extend(
            f"set(key={key!r}, value={value!r}, ex={ex!r})"
            for key, value, ex in self._expected_sets
        )
        assert not pending, "Unconsumed Redis expectations: " + "; ".join(pending)

    def get(self, key: str) -> Optional[str]:
        self._last_get = key
        if self._expected_gets:
            expected_key, returns = self._expected_gets.pop(0)
            if expected_key is not None and expected_key != key:
                raise AssertionError(f"Expected get({expected_key!r}) but received get({key!r})")
            if returns is not None:
                self.store[key] = returns
            return returns
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self._last_set = (key, value, ex)
        if self._expected_sets:
            expected_key, expected_value, expected_ex = self._expected_sets.pop(0)
            if expected_key is not None and expected_key != key:
                raise AssertionError(
                    f"Expected set({expected_key!r}, …) but received set({key!r}, …)"
                )
            if expected_value is not None and expected_value != value:
                raise AssertionError(f"Expected set value {expected_value!r}, saw {value!r}")
            if expected_ex is not _MISSING and expected_ex != ex:
                raise AssertionError(f"Expected set expiration {expected_ex!r}, saw {ex!r}")
        self.store[key] = value
        self.expirations[key] = ex


@dataclass
class _Expectation:
    expected: Dict[str, Any]
    returns: Any = None
    raises: Exception | None = None


class NotionAPIStub(NotionAPI):
    """Stubbed Notion API with expectation helpers."""

    def __init__(self) -> None:
        self._expectations: Dict[str, list[_Expectation]] = {
            "query": [],
            "create": [],
            "update": [],
            "retrieve": [],
        }
        self._last_calls: Dict[str, tuple[tuple[Any, ...], Dict[str, Any]]] = {}
        self._call_history: Dict[str, list[tuple[tuple[Any, ...], Dict[str, Any]]]] = {}

    def expect_query(
        self,
        database_id: str | None = None,
        payload: Dict[str, Any] | None = None,
        *,
        returns: Any = None,
        raises: Exception | None = None,
    ) -> "NotionAPIStub":
        self._expectations["query"].append(
            _Expectation({"database_id": database_id, "payload": payload}, returns, raises)
        )
        return self

    def expect_create(
        self,
        payload: Dict[str, Any] | None = None,
        *,
        returns: Any = None,
        raises: Exception | None = None,
    ) -> "NotionAPIStub":
        self._expectations["create"].append(_Expectation({"payload": payload}, returns, raises))
        return self

    def expect_update(
        self,
        page_id: str | None = None,
        payload: Dict[str, Any] | None = None,
        *,
        returns: Any = None,
        raises: Exception | None = None,
    ) -> "NotionAPIStub":
        self._expectations["update"].append(
            _Expectation({"page_id": page_id, "payload": payload}, returns, raises)
        )
        return self

    def expect_retrieve(
        self,
        page_id: str | None = None,
        *,
        returns: Any = None,
        raises: Exception | None = None,
    ) -> "NotionAPIStub":
        self._expectations["retrieve"].append(_Expectation({"page_id": page_id}, returns, raises))
        return self

    def assert_last_query(
        self, database_id: str | None = None, payload: Dict[str, Any] | None = None
    ) -> None:
        self._assert_last_call("query", database_id, payload)

    def assert_last_create(self, payload: Dict[str, Any] | None = None) -> None:
        self._assert_last_call("create", payload=payload)

    def assert_last_update(
        self, page_id: str | None = None, payload: Dict[str, Any] | None = None
    ) -> None:
        self._assert_last_call("update", page_id, payload)

    def assert_last_retrieve(self, page_id: str | None = None) -> None:
        self._assert_last_call("retrieve", page_id)

    async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._handle_call("query", database_id, payload)

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._handle_call("create", payload)

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._handle_call("update", page_id, payload)

    async def retrieve(self, page_id: str) -> Dict[str, Any]:
        return await self._handle_call("retrieve", page_id)

    async def _handle_call(self, name: str, *args: Any) -> Any:
        payload: Dict[str, Any] = {}
        match name:
            case "query":
                payload = {"database_id": args[0], "payload": args[1]}
            case "create":
                payload = {"payload": args[0]}
            case "update":
                payload = {"page_id": args[0], "payload": args[1]}
            case "retrieve":
                payload = {"page_id": args[0]}

        self._last_calls[name] = (args, payload)
        self._call_history.setdefault(name, []).append((args, payload))
        expectations = self._expectations[name]
        if expectations:
            expectation = expectations.pop(0)
            for key, expected_value in expectation.expected.items():
                if expected_value is not None and payload.get(key) != expected_value:
                    raise AssertionError(
                        f"Expected {name} {key}={expected_value!r} but got {payload.get(key)!r}"
                    )
            if expectation.raises:
                raise expectation.raises
            return expectation.returns
        return {}

    def _assert_last_call(
        self,
        name: str,
        identifier: str | None = None,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        assert name in self._last_calls, f"No {name} call was recorded"
        _, recorded_payload = self._last_calls[name]
        if identifier is not None:
            target_key = "database_id" if name == "query" else "page_id"
            assert recorded_payload.get(target_key) == identifier, (
                f"Expected last {name} {target_key}={identifier!r}"
            )
        if payload is not None:
            assert recorded_payload.get("payload") == payload, (
                f"Expected last {name} payload to match"
            )

    def last_query_payload(self) -> Dict[str, Any] | None:
        return self._last_payload("query")

    def last_create_payload(self) -> Dict[str, Any] | None:
        return self._last_payload("create")

    def last_update_payload(self) -> Dict[str, Any] | None:
        return self._last_payload("update")

    def query_history(self) -> list[Dict[str, Any]]:
        return [payload["payload"] for _, payload in self._call_history.get("query", [])]

    def assert_no_pending_expectations(self) -> None:
        """Assert all queued Notion API expectations were consumed."""

        pending = [
            f"{method}({expectation.expected!r}, returns={expectation.returns!r}, "
            f"raises={expectation.raises!r})"
            for method, expectations in self._expectations.items()
            for expectation in expectations
        ]
        assert not pending, "Unconsumed Notion API expectations: " + "; ".join(pending)

    def _last_payload(self, name: str) -> Dict[str, Any] | None:
        if name not in self._last_calls:
            return None
        _, payload = self._last_calls[name]
        return payload.get("payload")


class WithingsPortFake(WithingsMeasurementsPort):
    """Fake Withings port exposing expectation helpers."""

    def __init__(self) -> None:
        self._expected_refresh: list[_Expectation] = []
        self._expected_fetch: list[_Expectation] = []
        self._last_refresh: bool = False
        self._last_fetch: tuple[int, ...] | None = None

    def expect_refresh_access_token(
        self, *, returns: str | None = None, raises: Exception | None = None
    ) -> "WithingsPortFake":
        self._expected_refresh.append(_Expectation({}, returns, raises))
        return self

    def expect_fetch_measurements(
        self, days: int | None = None, *, returns: Any = None, raises: Exception | None = None
    ) -> "WithingsPortFake":
        expected = {"days": days}
        self._expected_fetch.append(_Expectation(expected, returns, raises))
        return self

    def assert_last_refresh(self) -> None:
        assert self._last_refresh, "refresh_access_token() was not called"

    def assert_last_fetch(self, days: int | None = None) -> None:
        assert self._last_fetch is not None, "fetch_measurements() was not called"
        if days is not None:
            assert self._last_fetch[0] == days, (
                f"Expected fetch_measurements({days}), saw {self._last_fetch[0]}"
            )

    def assert_no_pending_expectations(self) -> None:
        """Assert all queued Withings expectations were consumed."""

        pending = [
            f"refresh_access_token({expectation.expected!r}, returns={expectation.returns!r}, "
            f"raises={expectation.raises!r})"
            for expectation in self._expected_refresh
        ]
        pending.extend(
            f"fetch_measurements({expectation.expected!r}, returns={expectation.returns!r}, "
            f"raises={expectation.raises!r})"
            for expectation in self._expected_fetch
        )
        assert not pending, "Unconsumed Withings expectations: " + "; ".join(pending)

    async def refresh_access_token(self) -> str:
        self._last_refresh = True
        if self._expected_refresh:
            expectation = self._expected_refresh.pop(0)
            if expectation.raises:
                raise expectation.raises
            if expectation.returns is not None:
                return expectation.returns
        return ""

    async def fetch_measurements(self, days: int) -> Any:
        self._last_fetch = (days,)
        if self._expected_fetch:
            expectation = self._expected_fetch.pop(0)
            expected_days = expectation.expected.get("days")
            if expected_days is not None and expected_days != days:
                raise AssertionError(f"Expected fetch_measurements({expected_days}) but got {days}")
            if expectation.raises:
                raise expectation.raises
            return expectation.returns
        return []



class IntervalsSyncCoordinatorSpy:
    """Spy double for ``IntervalsSyncCoordinator`` interactions."""

    def __init__(self) -> None:
        self.requested_lookbacks: list[int | None] = []
        self._results: list[IntervalsSyncResult] = []
        self._expected_lookbacks: list[int | None] = []

    def expect_sync(
        self, *, lookback_days: int | None, returns: IntervalsSyncResult
    ) -> "IntervalsSyncCoordinatorSpy":
        self._expected_lookbacks.append(lookback_days)
        self._results.append(returns)
        return self

    def assert_last_sync(self, lookback_days: int | None = None) -> None:
        assert self.requested_lookbacks, "sync_recent() was not invoked"
        assert self.requested_lookbacks[-1] == lookback_days

    def assert_no_pending_expectations(self) -> None:
        pending = [f"sync_recent(lookback_days={value!r})" for value in self._expected_lookbacks]
        assert not pending, "Unconsumed Intervals expectations: " + "; ".join(pending)

    async def sync_recent(self, lookback_days: int | None = None) -> IntervalsSyncResult:
        self.requested_lookbacks.append(lookback_days)
        if self._results:
            expected = self._expected_lookbacks.pop(0)
            if expected != lookback_days:
                raise AssertionError(
                    f"Expected sync_recent(lookback_days={expected!r}) but got {lookback_days!r}"
                )
            return self._results.pop(0)
        from datetime import date

        return IntervalsSyncResult(
            status="ok",
            oldest=date(2026, 7, 7),
            newest=date(2026, 7, 14),
            lookback_days=lookback_days or 7,
            discovered=0,
            eligible=0,
            processed=0,
            skipped=0,
            failed=0,
        )


@pytest.fixture
def settings() -> Settings:
    """Canonical settings instance reused across tests."""

    return Settings(
        api_key="test-key",
        notion_secret="notion-secret",
        notion_database_id="notion-db",
        notion_workout_database_id="workout-db",
        notion_athlete_profile_database_id="profile-db",
        wbsapi_url="https://wbs.example.com",
        upstash_redis_rest_url="https://redis.example.com",
        upstash_redis_rest_token="redis-token",
        withings_client_id="withings-client",
        withings_client_secret="withings-secret",
        intervals_api_key="intervals-secret",
    )


@pytest.fixture
def redis_fake() -> Iterator[RedisFake]:
    fake = RedisFake()
    yield fake
    fake.assert_no_pending_expectations()


@pytest.fixture
def notion_api_stub() -> Iterator[NotionAPIStub]:
    stub = NotionAPIStub()
    yield stub
    stub.assert_no_pending_expectations()


@pytest.fixture
def withings_port_fake() -> Iterator[WithingsPortFake]:
    fake = WithingsPortFake()
    yield fake
    fake.assert_no_pending_expectations()


@pytest.fixture
def notion_workout_fake(settings: Settings) -> NotionWorkoutFake:
    """Preconfigured Notion fake specialised for workout repository tests."""

    return NotionWorkoutFake(settings)


@pytest.fixture
def intervals_sync_coordinator_spy() -> Iterator[IntervalsSyncCoordinatorSpy]:
    spy = IntervalsSyncCoordinatorSpy()
    yield spy
    spy.assert_no_pending_expectations()


@pytest.fixture
def app(
    settings: Settings,
    redis_fake: RedisFake,
    notion_api_stub: NotionAPIStub,
    withings_port_fake: WithingsPortFake,
    intervals_sync_coordinator_spy: IntervalsSyncCoordinatorSpy,
) -> Iterator[FastAPI]:
    """Configured FastAPI application instance for integration tests."""

    app = main.app
    overrides = {
        get_settings: lambda: settings,
        get_redis: lambda: redis_fake,
        get_notion_client: lambda: notion_api_stub,
        provide_withings_port: lambda: withings_port_fake,
        provide_intervals_sync_coordinator: lambda: intervals_sync_coordinator_spy,
    }
    app.dependency_overrides.update(overrides)
    try:
        yield app
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)


@pytest.fixture
def client(app: FastAPI, event_loop: asyncio.AbstractEventLoop) -> Iterator[httpx.AsyncClient]:
    """Async HTTP client bound to the FastAPI app."""

    transport = httpx.ASGITransport(app=app)
    api_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    yield api_client
    event_loop.run_until_complete(api_client.aclose())


class FrozenClock:
    """Mutable clock used by the ``freeze_time`` fixture."""

    def __init__(self, current: datetime) -> None:
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        self._current = current

    @property
    def current(self) -> datetime:
        return self._current

    def set(self, new_value: datetime) -> None:
        if new_value.tzinfo is None:
            new_value = new_value.replace(tzinfo=timezone.utc)
        self._current = new_value

    def advance(self, **delta: Any) -> None:
        self._current += timedelta(**delta)

    def timestamp(self) -> float:
        return self._current.timestamp()


@pytest.fixture
def freeze_time(monkeypatch: pytest.MonkeyPatch) -> FrozenClock:
    """Freeze ``datetime``/``time`` helpers for deterministic tests."""

    clock = FrozenClock(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    class _FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:  # type: ignore[override]
            return clock.current.replace(tzinfo=None)

        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return clock.current
            return clock.current.astimezone(tz)

    monkeypatch.setattr("src.notion.infrastructure.workout_repository.datetime", _FrozenDateTime)
    monkeypatch.setattr("time.time", lambda: clock.timestamp(), raising=False)

    return clock
