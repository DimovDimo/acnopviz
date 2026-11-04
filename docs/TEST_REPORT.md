# Test report v1.1.1

Executed: 2026-11-04.

## Environment
- OS: Linux (Debian)
- Python: 3.13.16
- Browser: Chromе
- Key libraries: FastAPI, Uvicorn, NumPy, SciPy, Pydantic, pytest, pytest-cov, Ruff, pip-audit

## Commands and results

| Command | Result |
|---|---|
| `python -m ruff check src tests` | All checks passed |
| `python -m ruff format --check src tests` | Clean |
| `python -m pytest -q --cov=acnopviz --cov-report=term-missing` | **80 passed**, 0 failed |
| Coverage | **96% line coverage** (1206 statements, 45 missed) |
| `python -m pip_audit --progress-spinner off` | No known vulnerabilities found; local package `acnopviz` skipped because it is not on PyPI |
| Live smoke | `/api/health`, `/api/cash-calendar`, `/api/backtest`, import template/validate exercised |
| Browser console capture | No dashboard console errors/warnings |

## Test types
- **Unit:** money, statistics, recommendations, cash calendar, backtest, ingestion, storage, CLI, and v1.1.1 audit regressions (due-today AR, cumulative discount buffer, chained duplicates, complete-month analytics, overdue AP, settings validation, discount-window validation, data-quality integrity).
- **Integration:** ASGI app with temporary SQLite; v1.0 flows; calendar/backtest endpoints; import validate/commit/fingerprint/confirmation/rollback; recommendation detail/review with analysis parameters; CSV export safety; latency.
- **End-to-end:** Playwright desktop review/scenario/transaction/quality/methodology flow, mobile navigation, cash-calendar → backtest → import flow, audit rendering, import file invalidation, async error handling, chart label anchoring.

## Bugs found and fixed in v1.1.1
See [AUDIT_REPORT.md](AUDIT_REPORT.md) for the reproduced finding/fix/test matrix. Summary: due-today AR omission, cumulative discount buffer, chained duplicate clustering, partial/missing month analytics, overdue AP omission, invalid settings, discount-window validation, data-quality gaps, recommendation parameter handling, audit UI undefined status, stale import validation, unhandled async UI errors, clipped chart labels, and stale import-template version metadata.

## Known limitations
- Synthetic data only; backtest coverage on the bundled dataset is diagnostic and may be poor, not a production calibration claim.
- Demo audit log is not tamper-proof; no auth/RBAC, ERP connectors, payment execution, or journal posting.
- Local package is skipped by pip-audit because it is not published on PyPI.
