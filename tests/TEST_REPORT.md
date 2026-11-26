# Test report

## Scope and status

Test coverage was expanded for feed parsing/matching, marketplace price shapes,
robots/cache/TTL behavior, AI-provider responses, auth/schema boundaries,
seed-database isolation, CLI dry-run/reset behavior, API ownership and database
invariants, and browser flows. No application source code was changed; failing
tests below are left visible as findings.

| Area | Result |
| --- | --- |
| Frontend unit (`npm.cmd run test:frontend`) | 11 passed |
| Backend and API/database (`pytest tests\\backend`) | 231 passed, 16 failed |
| Real-server Playwright E2E | 3 passed |
| Full pytest run | 247 passed, 16 failed |
| Backend coverage | 91% (1,343 statements; 121 missed) |
| Postman collection | JSON parsed successfully; collection not run in Postman |
| Mutation testing | Blocked: WSL is not installed; mutmut refuses native Windows |

The full pytest run also produced three existing deprecation warnings from
Starlette/FastAPI startup event handling.

## Failing tests / application findings

The 16 failing cases group into nine findings:

1. Local AI response JSON errors escape as `ValueError` rather than `AIUnavailable`.
2. Anthropic empty-text responses are returned as empty strings.
3. Structured AI responses containing reasoning only are accepted as empty output.
4. `max_price=0` is ignored by the product-list filter.
5. `update_prices` commits earlier product updates when a later product causes a refusal.
6. YML parsing accepts zero/negative prices and raises `OverflowError` for infinities.
7. YML parsing accepts non-RUB currencies without conversion.
8. Feed matching accepts one-token names and products with mismatched volumes.
9. Wildberries price extraction returns negative prices.

The backend tests report 16 failures because several findings have multiple
boundary cases (for example, currencies and invalid numeric prices).

## Mutation testing limitation

Mutmut is pinned to 3.8.1 and the obsolete configuration was replaced with
`source_paths` and `pytest_add_cli_args_test_selection`. No mutants were run:
the host has no WSL installation, and mutmut 3.8.1 reports that Windows
execution must use WSL. The requested separate clean clone was therefore not
created or mutated.

## Environment and revision

- Python 3.12.10; pytest 8.3.3; Playwright 1.55.0; Chromium 140.0.7339.16
- Node.js 24.13.1; npm 11.8.0; mutmut 3.8.1
- Branch reference: `Negnyi-Roman-Strastnoe-sogitelistvo`
- HEAD reference SHA: `2a18856669ed2ed16fb79d472e577ff29cd6da0a`
- Git CLI is unavailable in this environment, so worktree status could not be
  independently verified. The SHA identifies the branch HEAD, not the local
  uncommitted test changes that were executed.

## Reproducible commands

```powershell
npm.cmd run test:frontend
.\.venv\Scripts\python.exe -m pytest -q tests\backend
.\.venv\Scripts\python.exe -m pytest -q tests\frontend\e2e -m e2e
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term-missing:skip-covered tests\backend
```
