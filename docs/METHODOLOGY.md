# Methodology

All analytics use the fixed snapshot date in `meta.as_of` (default `2026-10-31`). Money is stored as integer cents. Recommendations are review prompts, not automated actions.

## 1. Collection prioritization
For each customer, consider invoices with `due_date <= as_of`. A matured invoice is late if it was paid after its due date or remains unpaid past due. Compute the late proportion and a 95% Wilson score interval. Flag when:
- at least 8 matured invoices exist,
- the customer has open overdue exposure,
- the Wilson lower bound exceeds the portfolio late-payment baseline,
- the point estimate is at least 35%.

Priority score = overdue exposure × late proportion. The value shown is **overdue exposure**, not expected loss or guaranteed recovery.

## 2. Duplicate-payment candidates
Group AP bills by `(vendor_id, normalize(invoice_number), amount_cents)`, where normalization removes non-alphanumeric characters and uppercases. Within a group, cluster bills whose issue dates are within 14 days of the cluster anchor. Exposure = sum of amounts after the first bill. This is a deterministic control match; legitimate installments or corrected invoices can match.

## 3. Early-payment discounts
For open bills with `issue_date <= as_of <= issue_date + discount_days` and `due_date > discount_deadline`:

```text
d = discount_percent / 100
annualized_yield = d / (1 - d) * 365 / (net_days - discount_days)
pay_now = amount * (1 - d)
financing_cost = pay_now * financing_APR * accelerated_days / 365
net_savings = amount * d - financing_cost
```

Flag when yield > financing APR, net savings > 0, and cash after payment remains at least 25,000 USD. Simple interest and a 365-day year are assumed; fees, taxes, and credit-risk changes are excluded.

## 4. Expense drift
Aggregate AP bills by category and issue month. For categories with at least 8 months and 6 nonzero months, compute:
- Theil-Sen slope and 95% confidence interval,
- two-sided Kendall tau p-value,
- Holm adjustment across tested categories.

Flag upward drift when slope > 0, CI lower bound > 0, Holm-adjusted p < 0.05, and relative drift `slope * (months - 1) / median(first 3 months)` is at least 15%. The value shown is estimated monthly drift, not achievable savings.

## 5. Liquidity stress test
Compute monthly net operating cash flow from settled cash transactions. Resample contiguous 3-month blocks with replacement to build 2,000 seeded paths over the selected horizon. Add scenario levers:
- one-time overdue recovery uplift × overdue AR to starting cash,
- expense reduction × average historical monthly payments to each month.

Report P10/P50/P90 ending cash by month, probability of any negative month-end balance, and additional reserve equal to the negative 10th-percentile minimum balance (floored at zero). This is a historical-resampling stress test, not a guaranteed forecast.

## 6. Data quality
Checks include customer/vendor references, positive amounts, no future-paid documents, settlement presence, AR/AP settlement-to-cash reconciliation, unique IDs, and duplicate-candidate warnings. Reconciliation failures are `fail`; duplicate candidates are `warn`.

## 7. What this does not do
No Benford's law, deep learning, tax optimization, automatic payments, journal posting, or claims of validated real-world savings. See [RESEARCH.md](RESEARCH.md) for trade-offs.
