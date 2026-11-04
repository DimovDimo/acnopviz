# Research note: building accounting optimization software

Research date: 2026-11-04. This note records the design evidence used for v1.0.0; it is not a market survey or a validation study on real accounting data.

## 1. Problem framing

Accounting optimization is a decision-support problem, not an automatic journal-entry problem. Useful outputs are specific, evidence-backed review actions: collect overdue receivables, inspect duplicate payments, compare early-payment discounts with financing cost, investigate expense drift, and size a liquidity buffer. The software should separate *statistical signals* from *deterministic control exceptions* and never present a flagged amount as confirmed savings.

## 2. What existing practice supports

- **Receivables aging and collection prioritization.** Aging reports group unpaid invoices by days past due and support collection prioritization and cash-flow planning [2](https://www.allianz-trade.com/en_US/insights/accounts-receivable-aging.html). J.P. Morgan describes AR forecasting, DSO, and payment terms as working-capital levers [5](https://www.jpmorgan.com/insights/treasury/receivables/accounts-receivable-management). acnopviz adds a Wilson interval around each customer's historical late-payment proportion so that small samples are not treated as precise risk estimates [1](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html).
- **Payment integrity controls.** GAO describes data matching and analytics as preventive/detective controls for improper payments [1](https://files.gao.gov/reports/GAO-25-108172/index.html). acnopviz therefore uses exact, explainable duplicate keys (vendor + normalized invoice number + amount + close issue dates), labels matches as *review candidates*, and requires human confirmation.
- **Cash forecasting and scenarios.** Treasury platforms combine cash positions, historical transactions, forecasts, and what-if scenarios [1](https://iongroup.com/solutions/treasury/cash-management/). acnopviz uses a transparent moving-block bootstrap of monthly operating cash flows rather than a black-box model. Blocks preserve short local dependence; the output is a simulated distribution, not a guaranteed forecast.
- **Early-payment terms.** "2/10 net 30" means a 2% discount for payment within 10 days, otherwise full payment in 30 days [5](https://www.jpmorgan.com/insights/treasury/receivables/accounts-receivable-management). The simple annualized discount yield is `(d / (1 - d)) * 365 / (net_days - discount_days)` [3](https://www.ultimatefinancecalculator.com/calculators/invoice-payment-terms-calculator/). acnopviz compares that yield with a user-supplied financing APR and also computes a dollar financing cost over the accelerated days.
- **Expense drift.** Theil-Sen is a robust slope estimator with a confidence interval [1](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html). acnopviz combines it with Kendall's tau and Holm adjustment across expense categories to reduce false discoveries from testing many categories.

## 3. Engineering approach

A small, local-first architecture is appropriate for the requested deliverable:

1. **Domain contract first:** customers, vendors, AR invoices, AP bills, cash transactions, and an explicit as-of date.
2. **Money as integer cents:** avoid binary floating-point accumulation in ledger totals.
3. **SQLite persistence:** parameterized SQL, foreign keys enabled explicitly (SQLite leaves them off by default) [3](https://www.sqlite.org/quirks.html), WAL for concurrent readers.
4. **FastAPI boundary:** typed request validation, OpenAPI docs, and dependency overrides for isolated tests [1](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
5. **Explainability:** every recommendation carries method, evidence IDs, assumptions, confidence/uncertainty, and a non-binding action.
6. **Human-in-the-loop:** accept/dismiss is a review state only; the app never sends payments or posts journals.
7. **Secure development lifecycle:** code review, automated analysis, and executable tests align with NIST SSDF PW.7/PW.8 [1](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218r1.ipd.pdf).

## 4. Statistical choices and trade-offs

| Candidate | Decision | Reason |
|---|---|---|
| Wilson late-payment interval | Included | Bounded, interpretable, better small-sample behavior than a raw percentage alone |
| Theil-Sen + Kendall + Holm | Included | Robust trend signal with multiple-testing control |
| Moving-block bootstrap | Included | Preserves short cash-flow dependence and exposes downside uncertainty |
| Benford's law | Excluded | Invoice amounts often have bounded ranges and negotiated prices; distribution assumptions are not generally justified |
| Deep learning forecast | Excluded | Only 18 synthetic months; insufficient data and poor explainability for this demo |
| Automatic tax optimization | Excluded | Jurisdiction-specific rules and professional judgment are outside scope |

## 5. Validation strategy

- Unit tests with hand-computed financial/statistical examples.
- Integration tests against temporary SQLite databases and the real ASGI app.
- Statistical sanity checks: reproducibility, monotonic scenario behavior, no future-data leakage, and trend detection on known signals.
- Browser end-to-end tests for navigation, review persistence, scenario controls, and exports.
- Data-quality checks for reconciliation, orphan references, invalid dates/amounts, and duplicates.
- Lint and dependency audit in CI.

## 6. Limitations

The bundled data is synthetic and intentionally contains review candidates. Results demonstrate software behavior, not empirical accuracy on a real business. Production use would require real-data validation, accounting policy review, authentication/authorization, encryption/backup policy, ERP reconciliation, jurisdiction-specific rules, and monitoring for drift.
