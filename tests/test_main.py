from __future__ import annotations

from src.main import _extract_upstream_host


class _ExcWithoutRequest:
    pass


class _ExcWithoutUrl:
    request = object()


def test_extract_upstream_host_returns_none_without_request() -> None:
    assert _extract_upstream_host(_ExcWithoutRequest()) is None  # type: ignore[arg-type]


def test_extract_upstream_host_returns_none_without_url() -> None:
    assert _extract_upstream_host(_ExcWithoutUrl()) is None  # type: ignore[arg-type]
