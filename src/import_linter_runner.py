"""CLI shim for running Import Linter via ``uv run import-linter``."""

from __future__ import annotations

import sys
from typing import Sequence

import click
from importlinter.cli import lint_imports_command


def main(argv: Sequence[str] | None = None) -> int:
    """Invoke Import Linter's Click command and propagate the exit code."""
    args = list(argv) if argv is not None else None

    try:
        lint_imports_command.main(
            args=args,
            prog_name="import-linter",
            standalone_mode=False,
        )
    except click.exceptions.Exit as exc:  # pragma: no cover - click handles sys.exit
        return exc.exit_code
    except click.ClickException as exc:  # pragma: no cover - surfaced to stderr
        exc.show()
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - convenience execution path
    sys.exit(main(sys.argv[1:]))
