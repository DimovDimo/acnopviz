from __future__ import annotations

import pytest
from scripts.generate_improvement_fixtures import valid_bundle

from acnopviz.analysis.calendar import cash_calendar
from acnopviz.analysis.engine import (
    _discount_recommendations,
    data_quality,
    duplicate_candidates,
    expense_drift,
    overview,
)
from acnopviz.config import Settings
from acnopviz.ingest import validate_bundle
from acnopviz.synthetic import generate_dataset


def test_calendar_includes_invoice_due_on_snapshot_date():
    data = {
        "meta": {
            "as_of": "2026-10-31",
            "opening_cash_cents": "10000",
            "currency": "USD",
            "seed": "1",
        },
        "customers": [{"id": "C", "name": "C", "segment": "SMB", "payment_terms_days": 30}],
        "vendors": [],
        "invoices": [
            {
                "id": "A0",
                "customer_id": "C",
                "issue_date": "2026-09-01",
                "due_date": "2026-10-01",
                "amount_cents": 1000,
                "paid_date": "2026-10-01",
                "paid_amount_cents": 1000,
            },
            {
                "id": "A1",
                "customer_id": "C",
                "issue_date": "2026-10-01",
                "due_date": "2026-10-31",
                "amount_cents": 5000,
                "paid_date": None,
                "paid_amount_cents": None,
            },
        ],
        "bills": [],
        "cash_transactions": [],
    }
    cal = cash_calendar(data, horizon=1, paths=50, block=1, seed=1)
    assert cal["totals"]["ar_scheduled"] == 50.0
    assert cal["months"][0]["ar_receipts"] == 50.0


def test_discount_recommendations_respect_cumulative_cash_buffer():
    data = generate_dataset()
    data["bills"] = [
        {
            "id": f"B{i}",
            "vendor_id": "V01",
            "invoice_number": f"X{i}",
            "issue_date": "2026-10-29",
            "due_date": "2026-11-28",
            "amount_cents": 2000000,
            "paid_date": None,
            "paid_amount_cents": None,
            "category": "Software",
            "discount_percent": 2.0,
            "discount_days": 10,
        }
        for i in range(4)
    ]
    # Enough cash for one discounted payment plus buffer, but not two.
    data["meta"]["opening_cash_cents"] = str(int((25000 + 19600 + 100) * 100))
    data["cash_transactions"] = []
    recs = _discount_recommendations(data, 0.08)
    assert len(recs) == 1
    assert recs[0]["evidence"]["cash_after_selection"] >= 25000


def test_duplicate_detection_finds_chained_matches():
    bills = [
        {
            "id": str(i),
            "vendor_id": "V",
            "invoice_number": "INV",
            "amount_cents": 100,
            "issue_date": d,
        }
        for i, d in enumerate(["2026-01-01", "2026-01-11", "2026-01-21"])
    ]
    clusters = duplicate_candidates(bills)
    assert len(clusters) == 1
    assert {r["id"] for r in clusters[0]} == {"0", "1", "2"}


def test_expense_drift_excludes_partial_snapshot_month():
    data = generate_dataset()
    data["meta"]["as_of"] = "2026-10-15"
    tests = expense_drift(data)
    assert tests and all(t["n"] == 17 for t in tests)


def test_expense_drift_fills_missing_months():
    data = generate_dataset()
    data["meta"]["as_of"] = "2026-09-30"
    bills = []
    for month in range(1, 10):
        if month == 5:
            continue
        bills.append(
            {
                "id": f"B{month}",
                "vendor_id": "V01",
                "invoice_number": f"M{month}",
                "issue_date": f"2026-{month:02d}-10",
                "due_date": f"2026-{month:02d}-20",
                "amount_cents": month * 10000,
                "paid_date": None,
                "paid_amount_cents": None,
                "category": "Software",
                "discount_percent": 0,
                "discount_days": 0,
            }
        )
    data["bills"] = bills
    tests = expense_drift(data)
    software = next(t for t in tests if t["category"] == "Software")
    assert software["n"] == 9
    assert software["values"][4] == 0.0


def test_overview_includes_overdue_ap_in_open_payables():
    data = generate_dataset()
    data["bills"].append(
        {
            "id": "OVERDUE",
            "vendor_id": "V01",
            "invoice_number": "OD",
            "issue_date": "2026-09-01",
            "due_date": "2026-10-01",
            "amount_cents": 12345,
            "paid_date": None,
            "paid_amount_cents": None,
            "category": "Software",
            "discount_percent": 0,
            "discount_days": 0,
        }
    )
    o = overview(data)
    assert o["overdue_ap"] == 123.45
    assert o["open_ap"] >= 123.45
    assert o["open_ap_count"] == sum(not r["paid_date"] for r in data["bills"])


def test_settings_validate_bootstrap_and_port():
    with pytest.raises(ValueError):
        Settings(bootstrap_block=0)
    with pytest.raises(ValueError):
        Settings(bootstrap_paths=50)
    with pytest.raises(ValueError):
        Settings(port=70000)
    with pytest.raises(ValueError):
        Settings(as_of="2026-02-30")


def test_import_rejects_discount_window_after_due_date():
    v = valid_bundle()
    v["files"]["bills"] = v["files"]["bills"].replace("Marketing,2,10", "Marketing,2,999")
    report = validate_bundle(v["manifest"], v["files"])
    assert not report["ok"]
    assert any(e["field"] == "discount_days" for e in report["errors"])


def test_data_quality_flags_future_cash_and_orphan_sources():
    data = generate_dataset()
    data["cash_transactions"].append(
        {
            "id": "FUTURE",
            "txn_date": "2027-01-01",
            "amount_cents": 100,
            "category": "Receipts",
            "description": "future",
            "source_type": None,
            "source_id": None,
        }
    )
    assert data_quality(data)["failed"] > 0
    data = generate_dataset()
    data["cash_transactions"].append(
        {
            "id": "ORPHAN",
            "txn_date": "2026-10-31",
            "amount_cents": 100,
            "category": "Receipts",
            "description": "orphan",
            "source_type": "invoice",
            "source_id": "MISSING",
        }
    )
    assert data_quality(data)["failed"] > 0


def test_data_quality_flags_over_settlement():
    data = generate_dataset()
    inv = next(r for r in data["invoices"] if r["paid_date"])
    inv["paid_amount_cents"] = inv["amount_cents"] + 1
    assert data_quality(data)["failed"] > 0


def test_monthly_cash_series_excludes_partial_snapshot_month():
    from acnopviz.analysis.engine import monthly_cash_series

    data = generate_dataset()
    data["meta"]["as_of"] = "2026-10-15"
    series = monthly_cash_series(data["cash_transactions"], data["meta"]["as_of"])
    assert series[-1]["month"] == "2026-09"
