# v1.1.1 correctness audit report

Date: 2026-11-04. Scope: second review pass over v1.1.0 focusing on correctness, data integrity, API consistency, and dashboard reliability. Each finding below was reproduced with a failing regression test before being patched.

| # | Area | Reproduced defect | Fix | Regression coverage |
|---|---|---|---|---|
| 1 | Cash calendar | Open AR due on `as_of` with zero drawn/median delay scheduled to month index `-1` and disappeared from totals/months. | `_receipt_date` schedules due/overdue invoices from snapshot with residual delay `max(1, delay - days_overdue)`. | `test_calendar_includes_invoice_due_on_snapshot_date` |
| 2 | Discounts | Each discount checked the cash buffer independently; accepting several could breach `MIN_BUFFER`. | Rank by net savings; apply cumulative `selected_pay_now`; expose `cash_after_selection`. | `test_discount_recommendations_respect_cumulative_cash_buffer` |
| 3 | Duplicates | Anchor-based 14-day clustering missed chained matches (day 0/10/20). | Connected-component clustering within each vendor/invoice/amount group. | `test_duplicate_detection_finds_chained_matches` |
| 4 | Expense drift | Partial snapshot month included when `as_of` was not month-end. | Complete-month range only; mid-month snapshots exclude current month. | `test_expense_drift_excludes_partial_snapshot_month` |
| 5 | Expense drift | Missing months were skipped, breaking equal-spacing assumption of Theil-Sen. | Continuous month range with zero-filled gaps. | `test_expense_drift_fills_missing_months` |
| 6 | Monthly cash series | Partial snapshot month could bias recurring overhead/backtest training. | Same complete-month rule applied to monthly cash series. | `test_monthly_cash_series_excludes_partial_snapshot_month` |
| 7 | Overview | “Open payables” excluded overdue unpaid AP. | Include all unpaid bills; add `overdue_ap`/`overdue_ap_count`; update dashboard footnote. | `test_overview_includes_overdue_ap_in_open_payables` |
| 8 | Configuration | Invalid `ACNOPVIZ_BOOTSTRAP_BLOCK=0`, paths, port, or date could cause runtime errors/500s. | `Settings.__post_init__` validates date/host/port/paths/block and fails fast. | `test_settings_validate_bootstrap_and_port`, `test_invalid_settings_fail_fast` |
| 9 | Import | Discount window could reach/pass net due date. | Reject `discount_days >= net_days`. | `test_import_rejects_discount_window_after_due_date` |
| 10 | Data quality | Future cash, orphan source links, over-settlement, duplicate cash IDs, invalid date order not checked. | Added integrity checks and one-to-one cash-source reconciliation. | `test_data_quality_flags_future_cash_and_orphan_sources`, `test_data_quality_flags_over_settlement` |
| 11 | Recommendation API | Detail/review used default analysis parameters, so horizon/rate-specific list items could 404. | Detail/review accept `financing_rate` and `horizon` query params. | `test_recommendation_detail_and_review_accept_analysis_parameters` |
| 12 | Audit UI | `dataset.import` events rendered `Status: undefined`. | Event-specific audit detail rendering. | E2E import flow asserts no `undefined` |
| 13 | Import UI | Editing files after validation left commit enabled for the stale bundle. | File-change invalidates validation and disables commit. | `test_import_file_change_invalidates_validation` |
| 14 | Dashboard async | Calendar/backtest/scenario/template handlers could produce unhandled rejections. | Catch async failures and show alert banner. | `test_async_action_errors_are_shown` |
| 15 | Charts | Last x-axis label could clip at right edge. | Anchor first/last labels inward. | `test_calendar_chart_last_label_is_not_clipped` |
| 16 | Import template | Template manifest version was hardcoded and lagged package version. | Use package `__version__` in template and fixture generator. | `test_import_template_version_matches_package` |

## Verification

- `python -m pytest -q --cov=acnopviz --cov-report=term-missing`: **80 passed**, 96% line coverage.
- `python -m ruff check src tests` and `ruff format --check`: clean.
- `python -m pip_audit`: no known vulnerabilities (local package skipped).
- Live smoke and Playwright screenshots refreshed for v1.1.1.

## Not changed / known limitations

- Synthetic demo only; no payment execution or journal posting.
- Backtest coverage remains diagnostic, not a production calibration claim.
- Import-time `create_app()` seeding remains the documented uvicorn entrypoint behavior.
- Recommendation review state is still keyed by recommendation ID; parameter-specific IDs (e.g., liquidity horizon) are preserved, but future work could add evidence hashes for stricter review invalidation.
