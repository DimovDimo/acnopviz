from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from acnopviz import __version__
from acnopviz.analysis.calendar import cash_calendar
from acnopviz.ingest import validate_bundle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic" / "improvements"


def valid_bundle() -> dict:
    manifest = {
        "name": "acnopviz-improvement-fixture",
        "version": __version__,
        "synthetic": True,
        "currency": "USD",
        "schema_version": 1,
        "seed": 111,
        "as_of": "2026-10-31",
        "opening_cash_cents": 10000,
    }
    rows = {
        "customers": [
            {
                "id": "C1",
                "name": "Fixture Customer One",
                "segment": "SMB",
                "payment_terms_days": 30,
            },
            {
                "id": "C2",
                "name": "Fixture Customer Two",
                "segment": "SMB",
                "payment_terms_days": 30,
            },
        ],
        "vendors": [
            {"id": "V1", "name": "Fixture Software", "category": "Software"},
            {"id": "V2", "name": "Fixture Marketing", "category": "Marketing"},
        ],
        "invoices": [
            {
                "id": "AR1",
                "customer_id": "C1",
                "issue_date": "2026-09-01",
                "due_date": "2026-10-01",
                "amount_cents": 5000,
                "paid_date": "2026-10-05",
                "paid_amount_cents": 5000,
            },
            {
                "id": "AR2",
                "customer_id": "C1",
                "issue_date": "2026-10-01",
                "due_date": "2026-10-31",
                "amount_cents": 8000,
                "paid_date": "",
                "paid_amount_cents": "",
            },
            {
                "id": "AR3",
                "customer_id": "C2",
                "issue_date": "2026-09-10",
                "due_date": "2026-10-10",
                "amount_cents": 3000,
                "paid_date": "",
                "paid_amount_cents": "",
            },
        ],
        "bills": [
            {
                "id": "AP1",
                "vendor_id": "V1",
                "invoice_number": "F-001",
                "issue_date": "2026-09-01",
                "due_date": "2026-10-01",
                "amount_cents": 2000,
                "paid_date": "2026-10-01",
                "paid_amount_cents": 2000,
                "category": "Software",
                "discount_percent": 0,
                "discount_days": 0,
            },
            {
                "id": "AP2",
                "vendor_id": "V2",
                "invoice_number": "F-002",
                "issue_date": "2026-10-20",
                "due_date": "2026-11-19",
                "amount_cents": 4000,
                "paid_date": "",
                "paid_amount_cents": "",
                "category": "Marketing",
                "discount_percent": 2,
                "discount_days": 10,
            },
        ],
        "cash_transactions": [
            {
                "id": "TX1",
                "txn_date": "2026-10-05",
                "amount_cents": 5000,
                "category": "Receipts",
                "description": "AR1 receipt",
                "source_type": "invoice",
                "source_id": "AR1",
            },
            {
                "id": "TX2",
                "txn_date": "2026-10-01",
                "amount_cents": -2000,
                "category": "Software",
                "description": "AP1 payment",
                "source_type": "bill",
                "source_id": "AP1",
            },
            {
                "id": "TX3",
                "txn_date": "2026-09-30",
                "amount_cents": -1000,
                "category": "Payroll",
                "description": "September payroll",
                "source_type": "",
                "source_id": "",
            },
            {
                "id": "TX4",
                "txn_date": "2026-10-31",
                "amount_cents": -1000,
                "category": "Payroll",
                "description": "October payroll",
                "source_type": "",
                "source_id": "",
            },
        ],
    }
    files = {}
    for table, data in rows.items():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
        files[table] = buf.getvalue()
    return {"manifest": manifest, "files": files}


def invalid_bundle() -> dict:
    bundle = valid_bundle()
    bundle["files"]["invoices"] = bundle["files"]["invoices"].replace("AR3,C2", "AR3,MISSING")
    bundle["files"]["bills"] = bundle["files"]["bills"].replace("4000,", "-4000,", 1)
    bundle["files"]["cash_transactions"] = bundle["files"]["cash_transactions"].replace(
        "-2000,", "-1999,", 1
    )
    return bundle


def write_bundle(bundle: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        json.dumps(bundle["manifest"], indent=2) + "\n", encoding="utf-8"
    )
    for table, text in bundle["files"].items():
        (directory / f"{table}.csv").write_text(text, encoding="utf-8")


def main() -> None:
    valid = valid_bundle()
    invalid = invalid_bundle()
    write_bundle(valid, OUT / "valid_bundle")
    write_bundle(invalid, OUT / "invalid_bundle")
    report = validate_bundle(valid["manifest"], valid["files"])
    invalid_report = validate_bundle(invalid["manifest"], invalid["files"])
    (OUT / "expected_validation.json").write_text(
        json.dumps({"valid": report, "invalid": invalid_report}, indent=2) + "\n", encoding="utf-8"
    )
    dataset, errors = __import__("acnopviz.ingest", fromlist=["parse_bundle"]).parse_bundle(
        valid["manifest"], valid["files"]
    )
    assert not errors and dataset is not None
    calendar = cash_calendar(dataset, horizon=3, paths=200, block=2, seed=111)
    (OUT / "cash_calendar_fixture.json").write_text(
        json.dumps(calendar, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "README.md").write_text(
        "# v1.1 improvement fixtures\n\n"
        "- `valid_bundle/`: small synthetic ledger that passes import validation.\n"
        "- `invalid_bundle/`: unknown customer, negative bill amount, and settlement mismatch.\n"
        "- `expected_validation.json`: expected validation reports.\n"
        "- `cash_calendar_fixture.json`: seeded runoff calendar for the valid bundle.\n\n"
        "Regenerate with `python scripts/generate_improvement_fixtures.py`.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "valid": report["ok"],
                "invalid_errors": len(invalid_report["errors"]),
                "out": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
