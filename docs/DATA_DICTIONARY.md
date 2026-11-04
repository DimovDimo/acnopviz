# Data dictionary

Synthetic dataset: 18 complete months (2025-05 through 2026-10), as-of 2026-10-31, seed 20261104, currency USD. Money columns ending in `_cents` are integer cents. JSON APIs expose decimal currency units.

## meta
| Key | Meaning |
|---|---|
| seed | Deterministic generator seed |
| as_of | Snapshot date; analytics never use paid/cash records after this date |
| opening_cash_cents | Opening bank balance before synthetic cash transactions |
| currency | USD |
| schema_version | Demo schema version |

## customers.csv
`id`, `name`, `segment`, `payment_terms_days`.

## vendors.csv
`id`, `name`, `category`.

## invoices.csv (AR)
| Column | Type | Notes |
|---|---|---|
| id | text | Unique AR identifier |
| customer_id | text FK | customers.id |
| issue_date / due_date | ISO date | due = issue + customer terms |
| amount_cents | integer > 0 | Gross invoice amount |
| paid_date | ISO date or null | Settlement date if paid by snapshot |
| paid_amount_cents | integer or null | Settled amount; equals gross in this demo |

## bills.csv (AP)
| Column | Type | Notes |
|---|---|---|
| id | text | Unique AP identifier |
| vendor_id | text FK | vendors.id |
| invoice_number | text | Vendor invoice number; duplicates may be planted |
| issue_date / due_date | ISO date | Net 30 in this demo |
| amount_cents | integer > 0 | Gross bill amount |
| paid_date / paid_amount_cents | optional | Settlement if paid by snapshot |
| category | text | Expense category |
| discount_percent | real 0-<100 | Early-payment discount percent |
| discount_days | integer | Days from issue to discount deadline |

## cash_transactions.csv
| Column | Type | Notes |
|---|---|---|
| id | text | Unique cash identifier |
| txn_date | ISO date | Settlement date |
| amount_cents | signed integer | Positive receipt, negative payment |
| category | text | Receipts, expense category, Payroll, Facilities, etc. |
| description | text | Human-readable description |
| source_type | invoice/bill/null | Linked document type |
| source_id | text/null | Linked document ID |

## reviews / audit (SQLite only)
- `reviews`: recommendation_id, status (`new`, `accepted`, `dismissed`), note, updated_at.
- `audit`: autoincrement id, event_type, entity_id, detail_json, created_at (UTC).

## Planted signals
The generator intentionally creates late-paying customers, three duplicate bill pairs, discount-eligible open bills, and recurring software spend drift. The analytics engine receives only ordinary ledger records; it does not receive signal labels.
