# Test workflow

Run commands from the repository root in PowerShell unless noted otherwise.

## Frontend unit tests

```powershell
npm.cmd run test:frontend
```

## Backend and API/database tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\backend
```

These tests use temporary SQLite databases and mock network or AI-provider calls.

## Browser end-to-end tests

The E2E suite launches the real FastAPI/static frontend server on `127.0.0.1:8011`,
assigns a temporary SQLite database before application startup, creates an isolated
browser context per test, and replaces only the external AI completion boundary.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q tests\frontend\e2e -m e2e
```

## Postman smoke collection

Import `api/yadro_api_smoke.postman_collection.json` into Postman. Start the local
backend first; the collection defaults to `http://127.0.0.1:8000` and creates a
new test account on each run.

## Mutation tests

Mutmut 3 requires `fork` support. On Windows, run it only inside WSL and in a
separate clean clone, not in the active working tree. The configuration and
focused test selection are in `backend/pyproject.toml`; the pinned tool is in
`backend/requirements-dev.txt`.
