# Test report v1.0.0

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
| `python -m ruff format --check src tests` | 18 files already formatted |
| `python -m pytest -q --cov=acnopviz --cov-report=term-missing` | **43 passed**, 0 failed, 0 warnings |
| Coverage | **98% line coverage** (702 statements, 11 missed) |
| `python -m pip_audit --progress-spinner off` | No known vulnerabilities found; local package `acnopviz` skipped because it is not on PyPI |
| Live smoke: `GET /api/health` | `{"status":"ok","version":"1.0.0",...}` |
| Browser console capture on dashboard | No console errors/warnings |

## Test types
- **Unit:** money rounding, Wilson interval, Holm adjustment, Theil-Sen/Kendall trend, discount yield, moving-block bootstrap, duplicate matching, recommendation stability, data-quality failure detection, SQLite constraints, CLI seed/report.
- **Integration:** real ASGI app with temporary SQLite; health/security headers; overview/manifest; recommendation detail; review persistence across app instances; validation; scenario monotonicity; transaction filter/search/pagination; SQL-injection-style search safety; CSV export completeness and formula protection; OpenAPI/static serving; recommendation latency < 2 s.
- **End-to-end:** Playwright Chromium desktop flow (overview → recommendation review → audit → scenario → transactions → data quality → methodology) and mobile navigation.
- **Statistical sanity:** deterministic dataset, no future-paid leakage, known increasing/decreasing/flat trends, bootstrap reproducibility, monotonic scenario improvement, planted signal detection.

## Bugs found and fixed during verification
1. **Bootstrap quantile axis:** quantiles were initially computed across months per path instead of across paths per month. Fixed to `axis=0`; added horizon/monotonicity assertions.
2. **Wilson boundary floating point:** upper bound could be `0.9999999999999999` for 10/10. Fixed explicit boundary clamping and float casting.
3. **Synthetic discount settlement double conversion:** discounted AP paid amount was converted to cents twice. Fixed to round once from integer cents.
4. **CSP/preview compatibility:** removed inline styles and `X-Frame-Options` so the strict CSP and Arena iframe preview work.
5. **E2E selector ambiguity:** navigation selector tightened to avoid matching the overview call-to-action button.

## Known limitations
- Results are validated on synthetic data only; no real-world accuracy or savings claim.
- CI dependency audit is allowed to report advisories without failing the demo pipeline (`continue-on-error`); production should gate on policy.
- Docker image build was not executed in this sandbox; Dockerfile/compose are provided and follow the same install/run path.
- Accessibility was checked via keyboard-focusable controls, labels, text chart alternatives, and browser smoke tests; a full assistive-technology audit is still recommended.
