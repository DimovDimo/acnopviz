# Technical requirements v1.1.0 improvements

## FR-101 Committed cash calendar
- Schedule open AR and AP from the snapshot; never include paid documents.
- AR timing uses empirical customer payment-delay draws (fallback: portfolio delays); overdue invoices use residual delay.
- AP is scheduled at due date (or next day if already overdue), gross amount, no automatic discount.
- Recurring component uses only cash transactions with `source_type` null/empty; linked invoice/bill settlements are excluded.
- Return monthly expected AR/AP/recurring/net/ending cash, P10/P50/P90 ending cash, probability of negative month-end balance, totals, and assumptions.
- Seeded results are reproducible; horizon 1-12; paths bounded by server settings.

## FR-102 Walk-forward backtest
- Expanding training window; default `min_train=9`, `horizon=3`, step 1.
- Each fold trains only on months before the test window.
- Compare bootstrap median cumulative net flow with naive last-value cumulative benchmark.
- Report MAE, RMSE, bias, P10-P90 coverage, mean interval width, fold count, and per-fold details.
- Reject invalid bounds; return an empty/insufficient-data result rather than leaking future data.

## FR-103 CSV bundle import
- Accept JSON body: `manifest` object plus `files` map with exactly `customers`, `vendors`, `invoices`, `bills`, `cash_transactions` CSV strings.
- Validate endpoint performs no writes. Commit endpoint requires `confirm: "REPLACE"` and the fingerprint returned by validation.
- Enforce exact headers, required fields, integer cents, finite discount percent, ISO dates, unique IDs, foreign keys, settlement consistency, source-link reconciliation, and no future-paid records.
- Bounds: total CSV payload ≤ 2 MiB; ≤ 5,000 rows per table; ≤ 100 reported errors.
- Commit revalidates and replaces ledger/meta/reviews in one SQLite transaction; appends `dataset.import` audit event; preserves prior audit history.
- Invalid bundles never partially modify the database.

## API additions
- `GET /api/cash-calendar?horizon=6`
- `GET /api/backtest?horizon=3&min_train=9`
- `POST /api/import/validate`
- `POST /api/import/commit`
- `GET /api/import/template` (manifest + empty CSV headers)

## Non-functional additions
| ID | Requirement |
|---|---|
| NFR-101 | New analytics are deterministic for identical data/seed |
| NFR-102 | Import validation and commit are bounded and return structured errors |
| NFR-103 | New UI views use escaped text, keyboard-focusable controls, and no external runtime assets |
| NFR-104 | Existing v1.0 tests continue to pass |
| NFR-105 | Full suite, lint, browser tests, and dependency audit are executed and recorded |

## Out of scope
New sales/purchase forecasting, default/credit-loss modeling, automatic discount execution, multipart upload, authentication, and production ERP connectors.
