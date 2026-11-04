.PHONY: install seed run test lint audit e2e

install:
	pip install -e ".[dev]"
	python -m playwright install chromium

seed:
	acnopviz seed --replace

run:
	acnopviz serve --host 0.0.0.0 --port 8000

lint:
	ruff check src tests
	ruff format --check src tests

test:
	pytest --cov=acnopviz --cov-report=term-missing

e2e:
	pytest -m e2e

audit:
	pip-audit
