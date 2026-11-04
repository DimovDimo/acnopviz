from __future__ import annotations

import pytest
from scripts.generate_improvement_fixtures import invalid_bundle, valid_bundle

from acnopviz.analysis.backtest import walk_forward_backtest
from acnopviz.analysis.calendar import cash_calendar, recurring_monthly_net
from acnopviz.ingest import parse_bundle, validate_bundle
from acnopviz.storage import Storage
from acnopviz.synthetic import generate_dataset


def hand_dataset():
    return {
        "meta": {
            "as_of": "2026-10-31",
            "opening_cash_cents": "100000",
            "currency": "USD",
            "seed": "1",
        },
        "customers": [{"id": "C1", "name": "C", "segment": "SMB", "payment_terms_days": 30}],
        "vendors": [{"id": "V1", "name": "V", "category": "Software"}],
        "invoices": [
            {
                "id": "AR0",
                "customer_id": "C1",
                "issue_date": "2026-09-01",
                "due_date": "2026-10-01",
                "amount_cents": 10000,
                "paid_date": "2026-10-05",
                "paid_amount_cents": 10000,
            },
            {
                "id": "AR1",
                "customer_id": "C1",
                "issue_date": "2026-10-15",
                "due_date": "2026-11-15",
                "amount_cents": 50000,
                "paid_date": None,
                "paid_amount_cents": None,
            },
        ],
        "bills": [
            {
                "id": "AP0",
                "vendor_id": "V1",
                "invoice_number": "X",
                "issue_date": "2026-09-01",
                "due_date": "2026-10-01",
                "amount_cents": 20000,
                "paid_date": "2026-10-01",
                "paid_amount_cents": 20000,
                "category": "Software",
                "discount_percent": 0,
                "discount_days": 0,
            },
            {
                "id": "AP1",
                "vendor_id": "V1",
                "invoice_number": "Y",
                "issue_date": "2026-10-10",
                "due_date": "2026-11-10",
                "amount_cents": 30000,
                "paid_date": None,
                "paid_amount_cents": None,
                "category": "Software",
                "discount_percent": 0,
                "discount_days": 0,
            },
        ],
        "cash_transactions": [
            {
                "id": "T1",
                "txn_date": "2026-10-05",
                "amount_cents": 10000,
                "source_type": "invoice",
                "source_id": "AR0",
            },
            {
                "id": "T2",
                "txn_date": "2026-10-01",
                "amount_cents": -20000,
                "source_type": "bill",
                "source_id": "AP0",
            },
            {
                "id": "T3",
                "txn_date": "2026-09-30",
                "amount_cents": -5000,
                "source_type": None,
                "source_id": None,
            },
            {
                "id": "T4",
                "txn_date": "2026-10-31",
                "amount_cents": -5000,
                "source_type": None,
                "source_id": None,
            },
        ],
    }


def test_calendar_schedules_open_docs_and_excludes_linked_cash():
    data = hand_dataset()
    recurring = recurring_monthly_net(data)
    assert [r["net"] for r in recurring] == [-50.0, -50.0]
    cal = cash_calendar(data, horizon=2, paths=200, block=2, seed=1)
    m0 = cal["months"][0]
    assert m0["ar_receipts"] == 500.0
    assert m0["ap_payments"] == 300.0
    assert m0["recurring_net"] == -50.0
    assert m0["expected_ending_cash"] == 950.0
    assert cal["months"][1]["expected_ending_cash"] == 900.0
    assert cal["prob_negative"] == 0.0


def test_calendar_overdue_residual_delay():
    data = hand_dataset()
    data["invoices"][1]["due_date"] = "2026-10-01"  # 30 days overdue; historical delay is 4
    cal = cash_calendar(data, horizon=1, paths=100, block=1, seed=1)
    assert cal["months"][0]["ar_receipts"] == 500.0


def test_calendar_reproducible_and_bounds():
    data = hand_dataset()
    assert cash_calendar(data, 2, 100, 2, 7) == cash_calendar(data, 2, 100, 2, 7)
    with pytest.raises(ValueError):
        cash_calendar(data, horizon=13)


def test_backtest_no_leakage_and_metrics(dataset):
    a = walk_forward_backtest(dataset, paths=200, seed=3)
    b = walk_forward_backtest(dataset, paths=200, seed=3)
    assert a == b
    assert a["status"] == "ok" and a["fold_count"] == 7
    for fold in a["folds"]:
        assert fold["train_months"] >= 9
        assert len(fold["test_months"]) == 3
    assert {"mae", "rmse", "bias", "coverage_p10_p90"} <= set(a["bootstrap"])
    small = {"meta": {"as_of": "2026-10-31"}, "cash_transactions": []}
    assert walk_forward_backtest(small)["status"] == "insufficient_data"
    with pytest.raises(ValueError):
        walk_forward_backtest(dataset, horizon=7)


def test_ingest_valid_and_invalid_fixtures():
    v = valid_bundle()
    report = validate_bundle(v["manifest"], v["files"])
    assert report["ok"] and report["counts"]["invoices"] == 3
    dataset, errors = parse_bundle(v["manifest"], v["files"])
    assert dataset is not None and not errors
    bad = invalid_bundle()
    report = validate_bundle(bad["manifest"], bad["files"])
    assert not report["ok"] and len(report["errors"]) >= 3


def test_ingest_rejects_malformed_and_duplicate_headers():
    v = valid_bundle()
    v["files"]["customers"] = 'id,name,segment,payment_terms_days\nC1,"unclosed,30\n'
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
    v = valid_bundle()
    v["files"]["vendors"] = "id,name,id,category\nV1,A,V1,B\n"
    assert not validate_bundle(v["manifest"], v["files"])["ok"]


def test_storage_import_atomic_rollback_and_audit(tmp_path, monkeypatch):
    store = Storage(tmp_path / "x.db")
    store.seed(generate_dataset(1))
    store.set_review("rec-1", "accepted", "old")
    before = store.load()
    audit_before = store.audit_log()
    v = valid_bundle()
    dataset, _ = parse_bundle(v["manifest"], v["files"])

    def boom(conn, data):
        raise RuntimeError("fail after deletes")

    monkeypatch.setattr(Storage, "_write_ledger", staticmethod(boom))
    with pytest.raises(RuntimeError):
        store.import_dataset(dataset, {"fingerprint": "x"})
    assert store.load()["meta"] == before["meta"]
    assert len(store.load()["invoices"]) == len(before["invoices"])
    assert store.audit_log() == audit_before
    monkeypatch.undo()
    store.import_dataset(dataset, {"fingerprint": "abc"})
    after = store.load()
    assert after["meta"]["seed"] == "111"
    assert after["reviews"] == []
    assert store.audit_log()[0]["event_type"] == "dataset.import"
    assert len(store.audit_log()) == len(audit_before) + 1


def test_calendar_empty_recurring_history():
    data = hand_dataset()
    data["cash_transactions"] = [t for t in data["cash_transactions"] if t.get("source_type")]
    cal = cash_calendar(data, horizon=2, paths=100, block=3, seed=1)
    assert cal["totals"]["recurring_monthly_median"] == 0.0
    assert cal["months"][0]["recurring_net"] == 0.0


def test_backtest_invalid_min_train(dataset):
    with pytest.raises(ValueError):
        walk_forward_backtest(dataset, min_train=37)


def _mutate(table: str, old: str, new: str) -> dict:
    v = valid_bundle()
    assert old in v["files"][table]
    v["files"][table] = v["files"][table].replace(old, new, 1)
    return v


def test_ingest_structure_and_manifest_errors():
    v = valid_bundle()
    assert not validate_bundle(v["manifest"], {"customers": ""})["ok"]
    v["files"]["customers"] = 123
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
    for field, value in [
        ("synthetic", False),
        ("currency", "EUR"),
        ("schema_version", 2),
        ("as_of", "bad"),
        ("opening_cash_cents", -1),
        ("seed", "x"),
    ]:
        v = valid_bundle()
        v["manifest"][field] = value
        assert not validate_bundle(v["manifest"], v["files"])["ok"]


def test_ingest_field_and_reference_errors():
    cases = [
        ("customers", "SMB,30", "SMB,0"),
        ("invoices", "AR2,C1", "AR2,MISSING"),
        ("invoices", "8000,", "0,"),
        ("invoices", "2026-10-01,2026-10-31", "2026-10-01,2026-09-01"),
        ("invoices", "2026-10-05", "2026-11-05"),
        ("invoices", "5000,2026-10-05", "5000,2026-10-05"),
        ("bills", "Marketing,2,10", "Marketing,100,10"),
        ("bills", "4000,", "4000,"),
        ("cash_transactions", "TX3,2026-09-30,-1000", "TX3,2026-09-30,0"),
        ("cash_transactions", "invoice,AR1", "other,AR1"),
        ("cash_transactions", "invoice,AR1", "invoice,"),
        ("cash_transactions", "invoice,AR1", "invoice,MISSING"),
    ]
    for table, old, new in cases:
        if old == new:
            continue
        v = _mutate(table, old, new)
        assert not validate_bundle(v["manifest"], v["files"])["ok"], (table, old, new)


def test_ingest_paid_consistency_and_duplicate_ids():
    v = valid_bundle()
    v["files"]["invoices"] = v["files"]["invoices"].replace("2026-10-05,5000", "2026-10-05,4999")
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
    v = valid_bundle()
    v["files"]["cash_transactions"] = (
        "\n".join(
            line
            for line in v["files"]["cash_transactions"].splitlines()
            if not line.startswith("TX1")
        )
        + "\n"
    )
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
    v = valid_bundle()
    v["files"]["customers"] += "C1,Dup,SMB,30\n"
    assert not validate_bundle(v["manifest"], v["files"])["ok"]


def test_ingest_bounds(monkeypatch):
    import acnopviz.ingest as ingest

    v = valid_bundle()
    monkeypatch.setattr(ingest, "MAX_TOTAL_BYTES", 10)
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
    monkeypatch.setattr(ingest, "MAX_TOTAL_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(ingest, "MAX_ROWS_PER_TABLE", 1)
    assert not validate_bundle(v["manifest"], v["files"])["ok"]
