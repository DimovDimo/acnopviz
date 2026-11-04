# Technical requirements v1.0.0

## Functional

| ID | Requirement | Verification |
|---|---|---|
| FR-01 | Seed a deterministic synthetic ledger with customers, vendors, AR, AP, and cash transactions | Unit + integration tests; CSV manifest |
| FR-02 | Compute cash, overdue AR, open AP, monthly operating net, and recommendation counts | API integration tests |
| FR-03 | Prioritize overdue customers using historical late-payment proportion and Wilson 95% interval | Unit tests; evidence includes counts and invoice IDs |
| FR-04 | Detect duplicate AP candidates by vendor, normalized invoice number, amount, and issue-date proximity | Planted duplicates detected; near matches not flagged |
| FR-05 | Compare open early-payment discounts with financing APR and cash buffer | Hand-computed 2/10 net 30 example |
| FR-06 | Detect expense drift with Theil-Sen slope CI, Kendall tau, and Holm adjustment | Known increasing/decreasing/flat series tests |
| FR-07 | Simulate liquidity with seeded moving-block bootstrap and report downside probability/quantiles | Reproducibility and horizon tests |
| FR-08 | Scenario lab accepts financing APR, overdue recovery uplift, expense reduction, and horizon | Bounds validation; monotonic cash improvement |
| FR-09 | Persist accept/dismiss/new review state and note; write audit events | Restart-persistence integration test |
| FR-10 | Export recommendations and transactions as CSV with formula-injection protection | CSV tests |
| FR-11 | Show data-quality checks and synthetic-data manifest | API + browser tests |
| FR-12 | Serve dashboard, OpenAPI docs, and health endpoint | E2E + integration tests |

## Data contract

- Money: integer cents in storage; JSON exposes decimal currency units as numbers.
- Dates: ISO `YYYY-MM-DD`; fixed demo as-of `2026-10-31`.
- AR invoice: unique ID, customer FK, issue/due dates, amount, optional paid date/amount.
- AP bill: unique ID, vendor FK, invoice number, issue/due dates, amount, category, optional paid date/amount, discount percent/days.
- Cash transaction: unique ID, date, signed amount, category, description, optional source reference.
- Review: recommendation ID, status (`new`, `accepted`, `dismissed`), note ≤ 1000 chars, updated timestamp.
- Audit: monotonic integer ID, event type, entity ID, JSON detail, UTC timestamp.

## API contract

- `GET /api/health`
- `GET /api/overview`
- `GET /api/recommendations?financing_rate=0.08&horizon=6`
- `GET /api/recommendations/{id}`
- `PATCH /api/recommendations/{id}/review`
- `POST /api/scenario`
- `GET /api/transactions?type=all|ar|ap|cash&search=&limit=&offset=`
- `GET /api/data-quality`
- `GET /api/audit`
- `GET /api/dataset/manifest`
- `GET /api/export/recommendations.csv`
- `GET /api/export/transactions.csv`
- `GET /docs`, `GET /openapi.json`, `GET /`

Unknown recommendation IDs return 404. Invalid numeric inputs return 422. Review updates are idempotent for the same payload. CSV exports are bounded by the demo dataset size.

## Non-functional

| ID | Requirement |
|---|---|
| NFR-01 | Python 3.11+; install with `pip install -e .[dev]` |
| NFR-02 | Runtime works without external network calls, API keys, or CDNs |
| NFR-03 | Parameterized SQL; foreign keys ON; WAL; bounded query parameters |
| NFR-04 | Security headers: CSP (`default-src 'self'`), nosniff, referrer policy; no permissive CORS |
| NFR-05 | Recommendation list responds within 2 s on the bundled dataset in the test environment |
| NFR-06 | Seeded analytics are reproducible for identical inputs and seed |
| NFR-07 | Keyboard-navigable dashboard; visible focus; labels on controls; text alternatives for charts |
| NFR-08 | CI runs lint, unit/integration tests, browser tests, and dependency audit |
| NFR-09 | No real customer data, credentials, payment execution, or journal posting |
| NFR-10 | Documentation includes research, plan, requirements, methodology, data dictionary, test report, README, changelog |

## Out of scope
Tax/legal advice, production ERP integration, multi-tenant auth, automatic payments, statutory financial statements, and claims of validated real-world savings.


## v1.1.0 improvements
See [IMPROVEMENT_REQUIREMENTS.md](IMPROVEMENT_REQUIREMENTS.md) for FR-101-FR-103 and NFR-101-NFR-105.
