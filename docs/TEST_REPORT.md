# Test report v1.1.0

Executed: 2026-11-04 (UTC) in the Arena sandbox.

## Environment
- OS: Linux (Debian trixie container)
- Python: 3.13.16
- Browser: Playwright Chromium 156.0.8078.4
- Key libraries: FastAPI, Uvicorn, NumPy 2.3.5, SciPy 1.17.1, Pydantic 2.14.2, pytest 9.0.3

## Commands and results

| Command | Result |
|---|---|
| `python -m ruff check src tests` | All checks passed |
| `python -m ruff format --check src tests` | 23 files already formatted |
| `python -m pytest -q --cov=acnopviz --cov-report=term-missing` | **63 passed**, 0 failed, 0 warnings |
| Coverage | **97% line coverage** (1121 statements, 38 missed) |
| `python -m pip_audit --progress-spinner off` | No known vulnerabilities found; local package `acnopviz` skipped because it is not on PyPI |
| Live smoke | `/api/health`, `/api/cash-calendar`, `/api/backtest`, import validate/commit exercised |
| Browser console capture | No dashboard console errors/warnings |

## Test types
- **Unit:** money, Wilson/Holm/Theil-Sen/bootstrap, duplicate matching, recommendation stability, cash-calendar scheduling/no-double-count/overdue residual/reproducibility/empty recurring history, backtest leakage/metrics/bounds, CSV ingestion valid/invalid/malformed/duplicate-header/manifest/field/reference/paid-consistency/bounds, SQLite atomic rollback and audit preservation, CLI.
- **Integration:** real ASGI app with temporary SQLite; existing v1.0 flows; cash-calendar and backtest endpoints; import validate read-only behavior; invalid commit 400; confirmation 422; fingerprint mismatch 409; successful commit changes manifest, clears reviews, appends audit; template endpoint; CSV export safety; latency.
- **End-to-end:** Playwright desktop review/scenario/transaction/quality/methodology flow, mobile navigation, and v1.1 cash-calendar → backtest → file-upload import flow.
- **Statistical sanity:** deterministic dataset, no future-paid leakage, known trend signals, bootstrap reproducibility, monotonic scenario improvement, planted signal detection, walk-forward fold boundaries.

## Bugs found and fixed during v1.1 verification
1. **Unhandled malformed CSV:** `csv.DictReader` could raise `csv.Error` during row iteration. Fixed by catching parser errors and returning structured validation failures.
2. **Short imported history:** valid small ledgers with fewer months than the configured bootstrap block caused liquidity/recommendation endpoints to raise `ValueError`. Fixed with a one-month-block fallback (zero-flow placeholder for empty history).
3. **E2E selector ambiguity (v1.0 carryover):** navigation selectors remain scoped to `.nav-item` to avoid matching call-to-action buttons.

## Known limitations
- Synthetic data only; backtest coverage on the bundled dataset is diagnostic and may be poor (the v1.1 run showed low empirical coverage), not a production calibration claim.
- Cash calendar is a runoff forecast and does not model new sales/purchases, defaults, taxes, capex, or financing.
- Docker image build was not executed in this sandbox; Dockerfile/compose follow the same install/run path.
- Accessibility was checked via keyboard-focusable controls, labels, text chart alternatives, and browser smoke tests; a full assistive-technology audit is still recommended.
