from __future__ import annotations

import click
import pytest

from src import import_linter_runner


def test_main_invokes_import_linter(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_main(**kwargs: object) -> None:
        recorded.update(kwargs)

    monkeypatch.setattr(import_linter_runner.lint_imports_command, "main", fake_main)

    assert import_linter_runner.main(["--verbose"]) == 0
    assert recorded == {
        "args": ["--verbose"],
        "prog_name": "import-linter",
        "standalone_mode": False,
    }


def test_main_returns_click_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_main(**_: object) -> None:
        raise click.exceptions.Exit(2)

    monkeypatch.setattr(import_linter_runner.lint_imports_command, "main", fake_main)

    assert import_linter_runner.main([]) == 2


def test_main_shows_click_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[bool] = []

    class FakeClickException(click.ClickException):
        def show(self, file: object | None = None) -> None:
            shown.append(True)

    def fake_main(**_: object) -> None:
        raise FakeClickException("broken")

    monkeypatch.setattr(import_linter_runner.lint_imports_command, "main", fake_main)

    assert import_linter_runner.main([]) == 1
    assert shown == [True]
