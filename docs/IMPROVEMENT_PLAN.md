# Improvement implementation plan v1.1.0

## Objective
Add commitment-aware liquidity timing, out-of-sample model validation, and safe synthetic ledger replacement without breaking the v1.0 review workflow.

## Work packages

| WP | Deliverable | Acceptance gate |
|---|---|---|
| WP1 | Research/plan/requirements for improvements | Docs identify gaps, sources, and testable IDs |
| WP2 | Synthetic improvement fixtures | Valid bundle, invalid bundle, expected validation report, calendar fixture |
| WP3 | Cash calendar engine | Open AR/AP scheduled once; recurring component excludes linked settlements; seeded uncertainty reproducible |
| WP4 | Walk-forward backtest | No future leakage; MAE/RMSE/bias/coverage; naive benchmark; bounded inputs |
| WP5 | CSV bundle ingestion | Strict parsing, cross-table validation, dry-run, fingerprint, explicit confirmation, atomic commit |
| WP6 | API + dashboard | New endpoints and views; existing flows still pass |
| WP7 | Verification | Unit/integration/E2E/performance/security tests; lint; dependency audit; bug fixes recorded |
| WP8 | Release docs | README/CHANGELOG/methodology/data dictionary/security/test report updated; archive rebuilt |

## Sequence
1. Freeze v1.0 behavior with existing tests.
2. Add fixture generator and new unit tests first (red).
3. Implement calendar, backtest, and ingestion modules (green).
4. Wire storage/API/UI; add integration and browser tests.
5. Run full suite, lint, audit, live smoke; fix defects.
6. Update docs and package v1.1.0.

## Compatibility
- Existing endpoints remain available.
- Existing recommendation IDs remain stable for unchanged data.
- Database schema is additive; no destructive migration required for v1.0 databases.
- Import is explicitly destructive to ledger/review state and requires confirmation.

## Risks and mitigations
- **Double counting:** separate linked settlements from recurring overhead; test with a hand-built ledger.
- **False confidence from backtest:** report fold count and label synthetic-only results.
- **Bad imports:** dry-run + revalidation at commit + transaction rollback + bounds.
- **UI complexity:** separate views, escaped rendering, no external assets.
