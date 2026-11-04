# acnopviz

**Statistically-based accounting optimization suggestions (explainable, local-first, human-reviewed).**

acnopviz turns a synthetic accounting ledger into a prioritized review queue: overdue receivables, duplicate-payment candidates, early-payment discount opportunities, expense drift, and liquidity stress tests. Every suggestion shows its method, evidence, assumptions, and uncertainty. It never executes payments or posts journal entries.

> **Status:** v1.0.0 demo on synthetic data. Not accounting, tax, legal, or investment advice. Production use requires real-data validation, accounting policy review, and security hardening.

![acnopviz dashboard](docs/dashboard.png)

## Features

- **Dashboard:** cash, overdue AR, open AP, monthly cash flow, receivables aging.
- **Recommendations:** Wilson-interval collection signals, exact duplicate controls, discount-vs-financing math, Theil-Sen/Kendall/Holm expense drift, block-bootstrap liquidity.
- **Scenario lab:** financing APR, one-time overdue recovery uplift, recurring expense reduction, 1-12 month horizon.
- **Review workflow:** accept/dismiss/new with reviewer notes, persisted in SQLite and appended to an audit trail.
- **Data browser & exports:** searchable AR/AP/cash ledger, CSV exports with spreadsheet formula-injection protection.
- **Data quality:** reconciliation, reference integrity, date/amount checks, duplicate-candidate warnings, reproducible synthetic manifest.
- **API docs:** OpenAPI/Swagger at `/docs`.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Generate deterministic synthetic CSVs + SQLite database
acnopviz seed --replace

# Run the app
acnopviz serve --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. API docs: <http://localhost:8000/docs>.

If you only want runtime dependencies: `pip install -e .`

### Docker

```bash
docker compose up --build
# http://localhost:8000
```

## CLI

```bash
acnopviz seed --seed 20261104 --as-of 2026-10-31 --db data/acnopviz.db --csv-dir data/synthetic --replace
acnopviz report --db data/acnopviz.db
acnopviz serve --host 0.0.0.0 --port 8000
```

Environment variables: `ACNOPVIZ_DB`, `ACNOPVIZ_SEED`, `ACNOPVIZ_AS_OF`, `ACNOPVIZ_HOST`, `ACNOPVIZ_PORT`, `ACNOPVIZ_BOOTSTRAP_PATHS`, `ACNOPVIZ_BOOTSTRAP_BLOCK`.

## Testing

```bash
python -m playwright install chromium
python -m ruff check src tests
python -m pytest --cov=acnopviz --cov-report=term-missing
python -m pytest -m e2e          # browser tests only
python -m pip_audit              # dependency audit (network required)
```

See [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) for the executed results and known limitations.

## Project layout

```text
src/acnopviz/
  analysis/        statistical engine and recommendation builder
  static/          dependency-free dashboard (HTML/CSS/JS)
  api.py           FastAPI boundary
  storage.py       SQLite persistence + audit
  synthetic.py     deterministic demo ledger generator
  cli.py           seed / report / serve
tests/
  unit/            money, statistics, engine, storage, CLI
  integration/     real ASGI app + temporary SQLite
  e2e/             Playwright browser flows
data/synthetic/    generated CSVs + manifest.json
docs/              research, plan, requirements, methodology, data dictionary, test report
```

## Documentation

- [Research note](docs/RESEARCH.md)
- [Development plan](docs/DEVELOPMENT_PLAN.md)
- [Technical requirements](docs/REQUIREMENTS.md)
- [Methodology](docs/METHODOLOGY.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Security notes](docs/SECURITY.md)
- [Test report](docs/TEST_REPORT.md)
- [Changelog](CHANGELOG.md)

## Key limitations

- Synthetic data only; no empirical accuracy claim on real businesses.
- Liquidity simulation resamples historical monthly net flows; it does not model a committed invoice calendar, taxes, capex, or new financing.
- Duplicate matches are review candidates, not proof of fraud or error.
- Local demo has no authentication/authorization or tenant isolation. Do not expose it publicly with real data.

## License

MIT see [LICENSE](LICENSE).
