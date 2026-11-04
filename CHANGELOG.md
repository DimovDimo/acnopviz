# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-04

### Added
- Local-first FastAPI + SQLite application with a dependency-free browser dashboard.
- Deterministic 18-month synthetic accounting ledger (customers, vendors, AR, AP, cash transactions) with CSV export and SHA-256 manifest.
- Explainable recommendation engine:
  - Wilson 95% interval collection prioritization.
  - Exact duplicate-payment candidate matching.
  - Early-payment discount yield vs financing APR and cash-buffer check.
  - Theil-Sen + Kendall tau + Holm-adjusted expense drift.
  - Seeded moving-block bootstrap liquidity stress test.
- Scenario lab with financing APR, overdue recovery uplift, expense reduction, and horizon controls.
- Human review workflow (new/accepted/dismissed + note) persisted in SQLite with an audit trail.
- Transaction browser, data-quality checks, synthetic manifest endpoint, CSV exports with formula-injection protection.
- OpenAPI docs, health endpoint, security headers, CLI (`seed`, `report`, `serve`).
- Unit, integration, statistical, performance, and Playwright end-to-end tests.
- GitHub Actions CI, Dockerfile/compose, Makefile, research/plan/requirements/methodology/data-dictionary/security/test-report docs.

### Fixed
- Bootstrap quantiles are computed across simulated paths per month (axis 0), not across months per path.
- Wilson interval bounds are explicitly clamped to exact 0/1 at boundary counts.
- Synthetic discounted AP settlements are rounded from integer cents once, avoiding double cent conversion.
- Dashboard avoids inline styles/scripts to satisfy the strict Content Security Policy.
- Removed `X-Frame-Options` so the app can run inside the Arena preview iframe.

### Security
- Parameterized SQL, foreign keys ON, WAL, bounded API inputs, strict CSP, nosniff, no permissive CORS.
- CSV formula-injection protection for exported text cells.

