from acnopviz.analysis.engine import (
    build_recommendations,
    cash_balance,
    data_quality,
    discount_opportunities,
    duplicate_candidates,
    expense_drift,
    is_overdue,
    monthly_cash_series,
    overview,
)
from acnopviz.synthetic import generate_dataset


def test_synthetic_deterministic():
    assert generate_dataset(42) == generate_dataset(42)
    assert generate_dataset(42) != generate_dataset(43)


def test_synthetic_reconciles_and_has_signals(dataset):
    q = data_quality(dataset)
    assert q["failed"] == 0
    assert q["warnings"] == 1
    kinds = {r["kind"] for r in build_recommendations(dataset)}
    assert {"collection", "duplicate", "discount", "expense"} <= kinds
    assert cash_balance(dataset) > 0


def test_no_future_paid_leakage(dataset):
    as_of = dataset["meta"]["as_of"]
    assert all(
        not r["paid_date"] or r["paid_date"] <= as_of
        for r in dataset["invoices"] + dataset["bills"]
    )
    assert all(tx["txn_date"] <= as_of for tx in dataset["cash_transactions"])


def test_overdue_definition():
    row = {"due_date": "2026-10-01", "paid_date": None, "paid_amount_cents": None}
    assert is_overdue(row, "2026-10-31")
    row["paid_date"] = "2026-10-15"
    row["paid_amount_cents"] = 100
    assert not is_overdue(row, "2026-10-31")


def test_duplicate_candidates_and_near_match():
    bills = [
        {
            "id": "1",
            "vendor_id": "V",
            "invoice_number": "INV-001",
            "amount_cents": 1000,
            "issue_date": "2026-01-01",
        },
        {
            "id": "2",
            "vendor_id": "V",
            "invoice_number": "inv 001",
            "amount_cents": 1000,
            "issue_date": "2026-01-05",
        },
        {
            "id": "3",
            "vendor_id": "V",
            "invoice_number": "INV-002",
            "amount_cents": 1000,
            "issue_date": "2026-01-05",
        },
        {
            "id": "4",
            "vendor_id": "V",
            "invoice_number": "INV-001",
            "amount_cents": 1001,
            "issue_date": "2026-01-05",
        },
        {
            "id": "5",
            "vendor_id": "V",
            "invoice_number": "INV-001",
            "amount_cents": 1000,
            "issue_date": "2026-03-01",
        },
    ]
    clusters = duplicate_candidates(bills)
    assert len(clusters) == 1
    assert {r["id"] for r in clusters[0]} == {"1", "2"}


def test_discount_opportunities_respect_rate(dataset):
    low = discount_opportunities(dataset, 0.08)
    high = discount_opportunities(dataset, 0.50)
    assert len(low) >= 3
    assert len(high) < len(low)
    for opp in low:
        assert opp["annualized_yield"] > 0.08
        assert opp["net_savings"] > 0


def test_expense_drift_flags_software(dataset):
    flagged = [t for t in expense_drift(dataset) if t["flagged"]]
    assert any(t["category"] == "Software" for t in flagged)
    for t in flagged:
        assert t["slope_low"] > 0 and t["p_adjusted"] < 0.05


def test_monthly_series_excludes_future():
    cash = [
        {"txn_date": "2026-10-15", "amount_cents": 1000},
        {"txn_date": "2026-11-01", "amount_cents": 9999},
    ]
    series = monthly_cash_series(cash, "2026-10-31")
    assert len(series) == 1 and series[0]["receipts"] == 10.0


def test_recommendation_ids_stable(dataset):
    a = build_recommendations(dataset)
    b = build_recommendations(dataset)
    assert [r["id"] for r in a] == [r["id"] for r in b]
    assert len({r["id"] for r in a}) == len(a)


def test_overview_totals_match_documents(dataset):
    o = overview(dataset)
    assert o["overdue_ar_count"] == sum(is_overdue(r, o["as_of"]) for r in dataset["invoices"])
    assert o["counts"]["invoices"] == len(dataset["invoices"])


def test_liquidity_recommendation_present(dataset):
    kinds = {r["kind"] for r in build_recommendations(dataset)}
    assert "liquidity" in kinds


def test_data_quality_flags_broken_reconciliation(dataset):
    dataset["cash_transactions"][0]["amount_cents"] += 12345
    q = data_quality(dataset)
    assert q["failed"] > 0
    assert q["status"] == "fail"
