# Security notes

## Implemented in the demo
- Parameterized SQL for all user-influenced queries; table names in dynamic SQL come from fixed allow-lists.
- SQLite foreign keys enabled explicitly; WAL journal mode; synchronous FULL.
- Pydantic request validation and bounded query parameters (rates, horizons, pagination, note length, search length).
- Strict CSP: `default-src 'self'`; no inline scripts/styles; no external CDNs.
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, API `Cache-Control: no-store`.
- No permissive CORS middleware.
- CSV export prefixes formula-triggering text cells (`=`, `+`, `-`, `@`) with an apostrophe.
- Review notes are rendered as escaped text in the dashboard.
- No real credentials, payment execution, or journal posting.

## Not implemented (required before production)
- Authentication, authorization, RBAC, segregation of duties, tenant isolation.
- TLS termination, secrets management, encrypted backups, retention policy.
- Immutable/tamper-evident external audit logging.
- Rate limiting, request size limits, audit alerting, dependency pinning/lockfile policy.
- ERP connector security, idempotent sync, reconciliation controls.

## Reporting
Open a GitHub issue for non-sensitive bugs. For sensitive vulnerabilities, use a private security advisory once the repository is published. Do not include real accounting data in reports.
