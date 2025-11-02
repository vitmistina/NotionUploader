# Developer Instructions

- `todo.md` usually can contain desired outcomes and improvements, read the file and implement
- After modifying API models or routes, regenerate the OpenAPI schema:
  ```bash
  python generate_openapi.py
  ```
  Commit the updated `openapi.json` alongside code changes.
- Always work inside a project-local virtual environment when installing or upgrading dependencies:
  ```bash
  python -m venv .venv
  source .venv/Scripts/activate
  ```
- Run the test suite before committing changes:
  ```bash
  pytest -q
  ```
- Enforce the coverage quality gate before merging:
  ```bash
  pytest --cov=src --cov-report=term-missing --cov-report=json --cov-fail-under=90
  python scripts/coverage_gate.py coverage.json --total-threshold=90 --per-file-threshold=75
  ```
- As a recurring chore, fix all Ruff lint findings and keep `requirements.txt` up to date:
  ```bash
  ruff check --fix src tests
  ruff check src tests
  ```
- As a recurring chore, reread the `README.md` after each change and update any sections impacted by your work before merging.
- As a recurring chore, clean up `todo.md` and `./examples/` folder after the implementation is done
