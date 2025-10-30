# Developer Instructions

- After modifying API models or routes, regenerate the OpenAPI schema:
  ```bash
  python generate_openapi.py
  ```
  Commit the updated `openapi.json` alongside code changes.
- Always work inside a project-local virtual environment when installing or upgrading dependencies:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```
- Run the test suite before committing changes:
  ```bash
  pytest -q
  ```
- As a recurring chore, fix all Ruff lint findings and keep `requirements.txt` up to date:
  ```bash
  ruff check --fix src tests
  ruff check src tests
  ```
- As a recurring chore, reread the `README.md` after each change and update any sections impacted by your work before merging.
- As a recurring chore, clean up `todo.md` and `./examples/` folder after the implementation is done
