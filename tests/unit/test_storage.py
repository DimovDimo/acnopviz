import sqlite3

import pytest

from acnopviz.storage import Storage
from acnopviz.synthetic import generate_dataset


def test_seed_and_load_roundtrip(tmp_path):
    store = Storage(tmp_path / "x.db")
    data = generate_dataset(1)
    store.seed(data)
    loaded = store.load()
    assert loaded["meta"]["seed"] == "1"
    assert len(loaded["invoices"]) == len(data["invoices"])
    assert loaded["reviews"] == []


def test_seed_refuses_overwrite_without_replace(tmp_path):
    store = Storage(tmp_path / "x.db")
    store.seed(generate_dataset(1))
    with pytest.raises(ValueError):
        store.seed(generate_dataset(2))
    store.seed(generate_dataset(2), replace=True)
    assert store.load()["meta"]["seed"] == "2"


def test_review_persists_and_audits(tmp_path):
    store = Storage(tmp_path / "x.db")
    store.seed(generate_dataset(1))
    store.set_review("rec-1", "accepted", "Looks reasonable")
    store.set_review("rec-1", "dismissed", "Changed mind")
    loaded = store.load()
    assert loaded["reviews"][0]["status"] == "dismissed"
    assert len(store.audit_log()) == 2


def test_foreign_keys_enforced(tmp_path):
    store = Storage(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError), store.connect() as conn:
        conn.execute(
            "INSERT INTO invoices VALUES ('bad','missing','2026-01-01','2026-01-31',100,NULL,NULL)"
        )
