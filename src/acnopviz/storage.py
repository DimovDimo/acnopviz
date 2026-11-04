from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, segment TEXT NOT NULL, payment_terms_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS vendors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
  issue_date TEXT NOT NULL, due_date TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
  paid_date TEXT, paid_amount_cents INTEGER CHECK(paid_amount_cents IS NULL OR paid_amount_cents >= 0)
);
CREATE TABLE IF NOT EXISTS bills (
  id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES vendors(id), invoice_number TEXT NOT NULL,
  issue_date TEXT NOT NULL, due_date TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
  paid_date TEXT, paid_amount_cents INTEGER CHECK(paid_amount_cents IS NULL OR paid_amount_cents >= 0),
  category TEXT NOT NULL, discount_percent REAL NOT NULL DEFAULT 0 CHECK(discount_percent >= 0 AND discount_percent < 100),
  discount_days INTEGER NOT NULL DEFAULT 0 CHECK(discount_days >= 0)
);
CREATE TABLE IF NOT EXISTS cash_transactions (
  id TEXT PRIMARY KEY, txn_date TEXT NOT NULL, amount_cents INTEGER NOT NULL,
  category TEXT NOT NULL, description TEXT NOT NULL, source_type TEXT, source_id TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  recommendation_id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('new','accepted','dismissed')),
  note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  detail_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_bills_vendor ON bills(vendor_id);
CREATE INDEX IF NOT EXISTS idx_bills_due ON bills(due_date);
CREATE INDEX IF NOT EXISTS idx_cash_date ON cash_transactions(txn_date);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def is_empty(self) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0

    def seed(self, dataset: dict[str, Any], *, replace: bool = False) -> None:
        with self.connect() as conn:
            if not replace and conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
                raise ValueError("database already seeded; use replace=True to rebuild")
            for table in (
                "cash_transactions",
                "bills",
                "invoices",
                "vendors",
                "customers",
                "reviews",
                "audit",
                "meta",
            ):
                conn.execute(f"DELETE FROM {table}")  # fixed allow-list, never user input
            self._write_ledger(conn, dataset)

    @staticmethod
    def _write_ledger(conn: sqlite3.Connection, dataset: dict[str, Any]) -> None:
        conn.executemany("INSERT INTO meta VALUES (?,?)", list(dataset["meta"].items()))
        conn.executemany(
            "INSERT INTO customers VALUES (?,?,?,?)",
            [
                (r["id"], r["name"], r["segment"], r["payment_terms_days"])
                for r in dataset["customers"]
            ],
        )
        conn.executemany(
            "INSERT INTO vendors VALUES (?,?,?)",
            [(r["id"], r["name"], r["category"]) for r in dataset["vendors"]],
        )
        conn.executemany(
            "INSERT INTO invoices VALUES (?,?,?,?,?,?,?)",
            [
                (
                    r["id"],
                    r["customer_id"],
                    r["issue_date"],
                    r["due_date"],
                    r["amount_cents"],
                    r.get("paid_date"),
                    r.get("paid_amount_cents"),
                )
                for r in dataset["invoices"]
            ],
        )
        conn.executemany(
            "INSERT INTO bills VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    r["id"],
                    r["vendor_id"],
                    r["invoice_number"],
                    r["issue_date"],
                    r["due_date"],
                    r["amount_cents"],
                    r.get("paid_date"),
                    r.get("paid_amount_cents"),
                    r["category"],
                    r.get("discount_percent", 0),
                    r.get("discount_days", 0),
                )
                for r in dataset["bills"]
            ],
        )
        conn.executemany(
            "INSERT INTO cash_transactions VALUES (?,?,?,?,?,?,?)",
            [
                (
                    r["id"],
                    r["txn_date"],
                    r["amount_cents"],
                    r["category"],
                    r["description"],
                    r.get("source_type"),
                    r.get("source_id"),
                )
                for r in dataset["cash_transactions"]
            ],
        )

    def import_dataset(self, dataset: dict[str, Any], detail: dict[str, Any]) -> None:
        """Atomically replace ledger/meta/reviews, preserve audit history, append import event."""
        now = utc_now()
        with self.connect() as conn:
            for table in (
                "cash_transactions",
                "bills",
                "invoices",
                "vendors",
                "customers",
                "reviews",
                "meta",
            ):
                conn.execute(f"DELETE FROM {table}")  # fixed allow-list
            self._write_ledger(conn, dataset)
            conn.execute(
                "INSERT INTO audit(event_type,entity_id,detail_json,created_at) VALUES (?,?,?,?)",
                ("dataset.import", detail.get("fingerprint", ""), json.dumps(detail), now),
            )

    def load(self) -> dict[str, Any]:
        with self.connect() as conn:

            def rows(table: str) -> list[dict[str, Any]]:
                return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]  # fixed allow-list

            meta = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM meta")}
            return {
                "meta": meta,
                "customers": rows("customers"),
                "vendors": rows("vendors"),
                "invoices": rows("invoices"),
                "bills": rows("bills"),
                "cash_transactions": rows("cash_transactions"),
                "reviews": rows("reviews"),
            }

    def set_review(self, recommendation_id: str, status: str, note: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO reviews(recommendation_id,status,note,updated_at) VALUES (?,?,?,?)
                   ON CONFLICT(recommendation_id) DO UPDATE SET
                   status=excluded.status, note=excluded.note, updated_at=excluded.updated_at""",
                (recommendation_id, status, note, now),
            )
            conn.execute(
                "INSERT INTO audit(event_type,entity_id,detail_json,created_at) VALUES (?,?,?,?)",
                (
                    "recommendation.review",
                    recommendation_id,
                    json.dumps({"status": status, "note": note}),
                    now,
                ),
            )
        return {
            "recommendation_id": recommendation_id,
            "status": status,
            "note": note,
            "updated_at": now,
        }

    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail_json"])} for r in rows]
