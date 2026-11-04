# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-04

### Added
- **Committed cash calendar:** runoff forecast that schedules open AR with empirical customer payment-delay draws, schedules open AP at due dates, and resamples only unlinked recurring cash flows to avoid double counting. New `GET /api/cash-calendar` and dashboard view.
- **Walk-forward model validation:** expanding-window backtest of the historical monthly liquidity bootstrap with MAE, RMSE, bias, P10-P90 coverage, mean interval width, naive last-value benchmark, and per-fold details. New `GET /api/backtest` and dashboard view.
- **Validated CSV-bundle import:** strict manifest/CSV parsing, type/date/reference/settlement/reconciliation checks, dry-run validation, SHA-256 fingerprint, explicit `REPLACE` confirmation, atomic SQLite replacement, preserved audit history, and `dataset.import` audit event. New `GET /api/import/template`, `POST /api/import/validate`, `POST /api/import/commit`, and dashboard view.
- Synthetic improvement fixtures: valid bundle, invalid bundle, expected validation reports, and seeded cash-calendar fixture (`data/synthetic/improvements/`).
- Improvement research, implementation plan, and technical requirements docs.
- Expanded unit, integration, and Playwright E2E tests for calendar, backtest, ingestion, atomic rollback, bounds, and browser import flow.

### Changed
- Liquidity simulation gracefully handles imported ledgers with fewer historical months than the configured bootstrap block by falling back to one-month blocks (or a zero-flow placeholder for empty history).
- CI dependency audit now gates the workflow instead of being advisory-only.
- README, methodology, data dictionary, security notes, requirements, and test report updated for v1.1.

### Fixed
- Malformed CSV input no longer raises an unhandled `csv.Error`; it returns structured validation errors.
- Small valid imported ledgers no longer cause recommendation/liquidity endpoints to fail with a bootstrap block-length error.

### Security
- Import payload bounded to 2 MiB total and 5,000 rows per table; at most 100 validation errors reported.
- Commit revalidates and requires a matching fingerprint plus explicit confirmation; failed imports rollback atomically.

## [1.0.0] - 2026-11-04

### Added
- Local-first FastAPI + SQLite application with a dependency-free browser dashboard.
- Deterministic 18-month synthetic accounting ledger with CSV export and SHA-256 manifest.
- Explainable recommendation engine: Wilson collection intervals, duplicate controls, early-payment discount math, Theil-Sen/Kendall/Holm expense drift, moving-block bootstrap liquidity.
- Scenario lab, human review workflow, audit trail, transaction browser, data-quality checks, CSV exports, OpenAPI docs, CLI.
- Unit, integration, statistical, performance, and Playwright E2E tests; GitHub Actions CI, Dockerfile/compose, Makefile, and foundational docs.

### Fixed
- Bootstrap quantile axis, Wilson boundary clamping, synthetic discount settlement rounding, CSP/preview compatibility.

### Security
- Parameterized SQL, foreign keys ON, WAL, bounded inputs, strict CSP, nosniff, no permissive CORS, CSV formula-injection protection.
