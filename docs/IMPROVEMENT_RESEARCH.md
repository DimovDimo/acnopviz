# Improvement research v1.1.0

Research date: 2026-11-04. This note extends the v1.0 research with the three improvements selected after auditing the running project.

## Gap 1: Liquidity scenarios ignored known commitments

v1.0 resampled total historical monthly net cash flow. That is useful as a stress test, but it does not schedule the open AR/AP already on the balance sheet. Direct cash-flow forecasting uses expected receipts and payments-AR, AP, payroll, and other scheduled movements and is most appropriate for short-term liquidity decisions [1](https://www.atlar.com/learn/what-are-the-direct-and-indirect-forecasting-methods). Treasury guidance similarly starts from a reconciled bank balance, AR timing, and AP/payroll outflows [4](https://treasury.ripple.com/posts/what-is-cash-flow-forecasting-how-to-build-a-cash-flow-forecast).

**Selected improvement:** a *committed cash calendar (runoff)* that schedules open AR using empirical customer payment-delay draws, schedules open AP at due dates, and resamples only historical cash flows **not linked to invoices/bills** as recurring overhead. Excluding linked settlements from the recurring component prevents double counting. The forecast explicitly does not create new sales or purchases after the snapshot.

## Gap 2: No out-of-sample forecast validation

v1.0 reported bootstrap quantiles but never measured whether they were calibrated. Backtesting applies a forecasting procedure retrospectively; rolling-origin / walk-forward validation repeatedly trains on past data and evaluates later periods [1](https://skforecast.org/0.14.0/user_guides/backtesting.html). Forecast evaluation should include error, bias, and interval coverage rather than a single point metric [3](https://growth-onomics.com/best-practices-forecast-model-evaluation/).

**Selected improvement:** expanding-window walk-forward backtest of the historical monthly liquidity model. Each fold uses only training months, compares bootstrap median cumulative net flow with a naive last-value benchmark, and reports MAE, RMSE, bias, and P10-P90 coverage. Small fold counts are surfaced as a limitation.

## Gap 3: No safe replacement-data path

The only way to change data was destructive reseeding. CSV is a common exchange format; RFC 4180 describes header/record structure, quoting, and doubled-quote escaping [3](https://freejsontocsv.com/learn/rfc-4180-csv/). SQLite transactions make multi-table changes atomic: either all changes commit or none do [3](https://www.sqlite.org/lockingv3.html).

**Selected improvement:** a validated CSV-bundle importer with a dry-run endpoint, strict schema/type/date/reference/reconciliation checks, size/row bounds, a content fingerprint, explicit replace confirmation, and a single-transaction commit. Review state is cleared on replacement because old evidence no longer applies; an import audit event is appended atomically.

## Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| ERP/live bank connectors | Deferred | Requires credentials, sync reconciliation, and production security beyond this demo |
| Deep-learning cash forecast | Rejected | 18 synthetic months is too small; explainability and validation matter more |
| Benford duplicate scoring | Rejected | Existing exact control is more interpretable for this data shape |
| Multi-file upload endpoint | Deferred | JSON CSV bundle is easier to validate atomically and test without multipart dependencies |
| Auth/RBAC | Deferred | Still required before production; v1.1 focuses on analytical and data-integrity gaps |

## References to implementation

- Cash calendar: `src/acnopviz/analysis/calendar.py`
- Backtest: `src/acnopviz/analysis/backtest.py`
- Import validation: `src/acnopviz/ingest.py`
- Atomic replacement: `Storage.import_dataset`
- UI: Cash calendar, Model validation, Import data views
