# v1.1 improvement fixtures

- `valid_bundle/`: small synthetic ledger that passes import validation.
- `invalid_bundle/`: unknown customer, negative bill amount, and settlement mismatch.
- `expected_validation.json`: expected validation reports.
- `cash_calendar_fixture.json`: seeded runoff calendar for the valid bundle.

Regenerate with `python scripts/generate_improvement_fixtures.py`.
