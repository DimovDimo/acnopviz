# Development plan

## Goal
Deliver a runnable, testable v1 of **acnopviz** that turns a synthetic accounting ledger into explainable optimization suggestions with a human review workflow.

## Phases and acceptance gates

| Phase | Work | Acceptance gate |
|---|---|---|
| 0. Research | Review AR aging, payment controls, cash forecasting, robust statistics, secure SDLC | `docs/RESEARCH.md` records sources and trade-offs |
| 1. Requirements | Define scope, data contract, APIs, non-functional requirements | `docs/REQUIREMENTS.md` has testable IDs |
| 2. Data | Deterministic 18-month synthetic ledger; planted duplicates, late payers, expense drift, discount terms | CSV manifest + reconciliation checks pass |
| 3. Core | Integer-cent money, SQLite repository, statistical engine, recommendation builder | Unit tests pass; no future-data leakage |
| 4. API/UI | FastAPI endpoints, dashboard, recommendation review, scenario lab, data quality, exports | Integration tests pass; browser can complete review flow |
| 5. Verification | Unit, integration, statistical, security, performance, E2E; lint/audit | `docs/TEST_REPORT.md` records actual results |
| 6. Release | README, changelog, Docker, CI, source archive | Fresh install + documented commands work |

## Architecture decision records

### ADR-001: Local-first monolith
**Decision:** FastAPI serves both JSON API and static dashboard; SQLite stores the demo ledger and review state.
**Why:** One command to run, no cloud credentials, easy inspection and testing.
**Trade-off:** Not a multi-tenant production service.

### ADR-002: Transparent statistics over black-box ML
**Decision:** Wilson intervals, Theil-Sen/Kendall/Holm, moving-block bootstrap, deterministic financial math.
**Why:** Small dataset, auditable assumptions, reproducible outputs.
**Trade-off:** No claim of optimal forecasting accuracy.

### ADR-003: Human review only
**Decision:** Recommendations can be accepted/dismissed with a note and audit trail; no payment execution or journal posting.
**Why:** False positives and accounting context require professional judgment.

### ADR-004: Integer cents and explicit as-of
**Decision:** Store money as integer cents; all analytics use a fixed snapshot date.
**Why:** Reproducibility and exact ledger arithmetic.

## Backlog after v1
- ERP/accounting connectors with idempotent sync and reconciliation.
- AuthN/AuthZ, tenant isolation, secrets management, encrypted backups.
- Real-data backtesting and calibration by segment/season.
- Richer cash calendar (known AR/AP due dates) and committed facilities.
- Approval queues, segregation of duties, and immutable external audit log.
- Accessibility audit with assistive technology and localization.
