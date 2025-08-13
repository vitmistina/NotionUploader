# Developer Instructions

- After modifying API models or routes, regenerate the OpenAPI schema:
  ```bash
  python generate_openapi.py
  ```
  Commit the updated `openapi.json` alongside code changes.
- Run the test suite before committing changes:
  ```bash
  pytest -q
  ```
