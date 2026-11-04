from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import date, timedelta
from typing import Any

MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_ROWS_PER_TABLE = 5000
MAX_ERRORS = 100

TABLES: dict[str, list[str]] = {
    "customers": ["id", "name", "segment", "payment_terms_days"],
    "vendors": ["id", "name", "category"],
    "invoices": [
        "id",
        "customer_id",
        "issue_date",
        "due_date",
        "amount_cents",
        "paid_date",
        "paid_amount_cents",
    ],
    "bills": [
        "id",
        "vendor_id",
        "invoice_number",
        "issue_date",
        "due_date",
        "amount_cents",
        "paid_date",
        "paid_amount_cents",
        "category",
        "discount_percent",
        "discount_days",
    ],
    "cash_transactions": [
        "id",
        "txn_date",
        "amount_cents",
        "category",
        "description",
        "source_type",
        "source_id",
    ],
}
REQUIRED = {
    "customers": {"id", "name", "segment", "payment_terms_days"},
    "vendors": {"id", "name", "category"},
    "invoices": {"id", "customer_id", "issue_date", "due_date", "amount_cents"},
    "bills": {
        "id",
        "vendor_id",
        "invoice_number",
        "issue_date",
        "due_date",
        "amount_cents",
        "category",
        "discount_percent",
        "discount_days",
    },
    "cash_transactions": {"id", "txn_date", "amount_cents", "category", "description"},
}


class _Errors:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, table: str, row: int | None, field: str | None, message: str) -> None:
        if len(self.items) < MAX_ERRORS:
            self.items.append({"table": table, "row": row, "field": field, "message": message})

    @property
    def full(self) -> bool:
        return len(self.items) >= MAX_ERRORS


def _date(value: str, table: str, row: int, field: str, errors: _Errors) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.add(table, row, field, "expected ISO date YYYY-MM-DD")
        return None


def _int(
    value: str,
    table: str,
    row: int,
    field: str,
    errors: _Errors,
    *,
    minimum: int | None = None,
    nonzero: bool = False,
) -> int | None:
    try:
        out = int(value)
    except ValueError:
        errors.add(table, row, field, "expected integer")
        return None
    if minimum is not None and out < minimum:
        errors.add(table, row, field, f"must be >= {minimum}")
    if nonzero and out == 0:
        errors.add(table, row, field, "must be nonzero")
    return out


def _parse_csv(table: str, text: str, errors: _Errors) -> list[dict[str, str]]:
    if not isinstance(text, str):
        errors.add(table, None, None, "expected CSV string")
        return []
    try:
        reader = csv.DictReader(io.StringIO(text), strict=True)
        headers = reader.fieldnames or []
    except csv.Error as exc:
        errors.add(table, None, None, f"malformed CSV: {exc}")
        return []
    if len(headers) != len(set(headers)):
        errors.add(table, 1, None, "duplicate header names")
    if set(headers) != set(TABLES[table]):
        missing = sorted(set(TABLES[table]) - set(headers))
        extra = sorted(set(headers) - set(TABLES[table]))
        errors.add(table, 1, None, f"header mismatch; missing={missing}, extra={extra}")
        return []
    rows = []
    try:
        for i, row in enumerate(reader, start=2):
            if errors.full:
                break
            if i - 1 > MAX_ROWS_PER_TABLE:
                errors.add(table, i, None, f"row limit exceeded ({MAX_ROWS_PER_TABLE})")
                break
            if None in row or any(v is None for v in row.values()):
                errors.add(table, i, None, "column count does not match header")
                continue
            for field in REQUIRED[table]:
                if not str(row.get(field, "")).strip():
                    errors.add(table, i, field, "required value is empty")
            rows.append({k: v.strip() for k, v in row.items()})
    except csv.Error as exc:
        errors.add(table, None, None, f"malformed CSV: {exc}")
    return rows


def _manifest(manifest: Any, errors: _Errors) -> dict[str, str]:
    if not isinstance(manifest, dict):
        errors.add("manifest", None, None, "expected object")
        return {}
    if manifest.get("synthetic") is not True:
        errors.add("manifest", None, "synthetic", "must be true for this demo importer")
    if manifest.get("currency") != "USD":
        errors.add("manifest", None, "currency", "only USD is supported")
    if str(manifest.get("schema_version")) != "1":
        errors.add("manifest", None, "schema_version", "must be 1")
    if not str(manifest.get("name", "")).strip():
        errors.add("manifest", None, "name", "required")
    as_of = _date(str(manifest.get("as_of", "")), "manifest", 0, "as_of", errors)
    seed = _int(str(manifest.get("seed", "")), "manifest", 0, "seed", errors)
    opening = _int(
        str(manifest.get("opening_cash_cents", "")),
        "manifest",
        0,
        "opening_cash_cents",
        errors,
        minimum=0,
    )
    if as_of is None or seed is None or opening is None:
        return {}
    return {
        "seed": str(seed),
        "as_of": as_of.isoformat(),
        "opening_cash_cents": str(opening),
        "currency": "USD",
        "schema_version": "1",
    }


def parse_bundle(manifest: Any, files: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    errors = _Errors()
    if not isinstance(files, dict) or set(files) != set(TABLES):
        errors.add("files", None, None, f"expected exactly keys {sorted(TABLES)}")
        return None, errors.items
    total = sum(len(v.encode("utf-8")) for v in files.values() if isinstance(v, str))
    if total > MAX_TOTAL_BYTES:
        errors.add("files", None, None, f"total CSV payload exceeds {MAX_TOTAL_BYTES} bytes")
        return None, errors.items
    meta = _manifest(manifest, errors)
    raw = {t: _parse_csv(t, files[t], errors) for t in TABLES}
    if errors.items:
        return None, errors.items

    dataset: dict[str, Any] = {
        "meta": meta,
        "customers": [],
        "vendors": [],
        "invoices": [],
        "bills": [],
        "cash_transactions": [],
    }
    as_of = meta["as_of"]
    for table in ("customers", "vendors"):
        seen = set()
        for i, r in enumerate(raw[table], start=2):
            if r["id"] in seen:
                errors.add(table, i, "id", "duplicate id")
            seen.add(r["id"])
            row = dict(r)
            if table == "customers":
                row["payment_terms_days"] = _int(
                    r["payment_terms_days"], table, i, "payment_terms_days", errors, minimum=1
                )
            dataset[table].append(row)
    customer_ids = {r["id"] for r in dataset["customers"]}
    vendor_ids = {r["id"] for r in dataset["vendors"]}

    for i, r in enumerate(raw["invoices"], start=2):
        row = dict(r)
        row["amount_cents"] = _int(
            r["amount_cents"], "invoices", i, "amount_cents", errors, minimum=1
        )
        issue = _date(r["issue_date"], "invoices", i, "issue_date", errors)
        due = _date(r["due_date"], "invoices", i, "due_date", errors)
        if r["customer_id"] not in customer_ids:
            errors.add("invoices", i, "customer_id", "unknown customer")
        if issue and due and issue > due:
            errors.add("invoices", i, "due_date", "due date before issue date")
        paid_date = (
            _date(r["paid_date"], "invoices", i, "paid_date", errors) if r["paid_date"] else None
        )
        paid_amount = (
            _int(r["paid_amount_cents"], "invoices", i, "paid_amount_cents", errors, minimum=1)
            if r["paid_amount_cents"]
            else None
        )
        if bool(paid_date) != bool(paid_amount):
            errors.add(
                "invoices",
                i,
                "paid_date",
                "paid_date and paid_amount_cents must be provided together",
            )
        if paid_date:
            if paid_date.isoformat() > as_of:
                errors.add("invoices", i, "paid_date", "paid date after as_of")
            if issue and paid_date < issue:
                errors.add("invoices", i, "paid_date", "paid date before issue date")
            if paid_amount != row["amount_cents"]:
                errors.add("invoices", i, "paid_amount_cents", "demo AR requires full settlement")
        row.update(
            {
                "paid_date": paid_date.isoformat() if paid_date else None,
                "paid_amount_cents": paid_amount,
            }
        )
        dataset["invoices"].append(row)

    for i, r in enumerate(raw["bills"], start=2):
        row = dict(r)
        row["amount_cents"] = _int(r["amount_cents"], "bills", i, "amount_cents", errors, minimum=1)
        row["discount_days"] = _int(
            r["discount_days"], "bills", i, "discount_days", errors, minimum=0
        )
        try:
            dp = float(r["discount_percent"])
            if not math.isfinite(dp) or not 0 <= dp < 100:
                raise ValueError
            row["discount_percent"] = dp
        except ValueError:
            errors.add("bills", i, "discount_percent", "expected finite percent in [0, 100)")
        issue = _date(r["issue_date"], "bills", i, "issue_date", errors)
        due = _date(r["due_date"], "bills", i, "due_date", errors)
        if r["vendor_id"] not in vendor_ids:
            errors.add("bills", i, "vendor_id", "unknown vendor")
        if issue and due and issue > due:
            errors.add("bills", i, "due_date", "due date before issue date")
        if issue and due and row.get("discount_days") is not None:
            net_days = (due - issue).days
            if row["discount_days"] >= net_days:
                errors.add(
                    "bills", i, "discount_days", "discount window must end before the net due date"
                )
        paid_date = (
            _date(r["paid_date"], "bills", i, "paid_date", errors) if r["paid_date"] else None
        )
        paid_amount = (
            _int(r["paid_amount_cents"], "bills", i, "paid_amount_cents", errors, minimum=1)
            if r["paid_amount_cents"]
            else None
        )
        if bool(paid_date) != bool(paid_amount):
            errors.add(
                "bills", i, "paid_date", "paid_date and paid_amount_cents must be provided together"
            )
        if paid_date:
            if paid_date.isoformat() > as_of:
                errors.add("bills", i, "paid_date", "paid date after as_of")
            if issue and paid_date < issue:
                errors.add("bills", i, "paid_date", "paid date before issue date")
            expected = row["amount_cents"]
            if (
                issue
                and row.get("discount_percent", 0) > 0
                and paid_date <= issue + timedelta(days=row["discount_days"])
            ):
                expected = int(round(row["amount_cents"] * (1 - row["discount_percent"] / 100)))
            if paid_amount not in (row["amount_cents"], expected):
                errors.add(
                    "bills",
                    i,
                    "paid_amount_cents",
                    "settlement must equal gross or eligible discounted amount",
                )
        row.update(
            {
                "paid_date": paid_date.isoformat() if paid_date else None,
                "paid_amount_cents": paid_amount,
            }
        )
        dataset["bills"].append(row)

    inv_by_id = {r["id"]: r for r in dataset["invoices"]}
    bill_by_id = {r["id"]: r for r in dataset["bills"]}
    linked: dict[tuple[str, str], list[dict]] = {}
    for i, r in enumerate(raw["cash_transactions"], start=2):
        row = dict(r)
        row["amount_cents"] = _int(
            r["amount_cents"], "cash_transactions", i, "amount_cents", errors, nonzero=True
        )
        txn = _date(r["txn_date"], "cash_transactions", i, "txn_date", errors)
        if txn and txn.isoformat() > as_of:
            errors.add("cash_transactions", i, "txn_date", "transaction after as_of")
        st = r["source_type"] or None
        sid = r["source_id"] or None
        if st not in (None, "invoice", "bill"):
            errors.add("cash_transactions", i, "source_type", "expected invoice, bill, or empty")
        if bool(st) != bool(sid):
            errors.add(
                "cash_transactions",
                i,
                "source_id",
                "source_type and source_id must be provided together",
            )
        if st and sid:
            doc = inv_by_id.get(sid) if st == "invoice" else bill_by_id.get(sid)
            if doc is None:
                errors.add("cash_transactions", i, "source_id", "unknown source document")
            else:
                linked.setdefault((st, sid), []).append(row)
                if not doc["paid_date"]:
                    errors.add("cash_transactions", i, "source_id", "linked document is not paid")
                elif txn and txn.isoformat() != doc["paid_date"]:
                    errors.add(
                        "cash_transactions", i, "txn_date", "does not match document paid_date"
                    )
                if st == "invoice" and row["amount_cents"] != doc["paid_amount_cents"]:
                    errors.add(
                        "cash_transactions",
                        i,
                        "amount_cents",
                        "AR receipt must equal settlement amount",
                    )
                if st == "bill" and row["amount_cents"] != -doc["paid_amount_cents"]:
                    errors.add(
                        "cash_transactions",
                        i,
                        "amount_cents",
                        "AP payment must equal negative settlement amount",
                    )
        row.update({"source_type": st, "source_id": sid})
        dataset["cash_transactions"].append(row)

    for kind, docs in (("invoice", dataset["invoices"]), ("bill", dataset["bills"])):
        for doc in docs:
            n = len(linked.get((kind, doc["id"]), []))
            if doc["paid_date"] and n != 1:
                errors.add(
                    kind + "s",
                    None,
                    doc["id"],
                    f"paid document requires exactly one linked cash transaction (found {n})",
                )
            if not doc["paid_date"] and n:
                errors.add(
                    kind + "s", None, doc["id"], "open document has linked cash transactions"
                )
    for table in TABLES:
        ids = [r["id"] for r in dataset[table]]
        if len(ids) != len(set(ids)):
            errors.add(table, None, "id", "duplicate ids")
    if errors.items:
        return None, errors.items
    return dataset, []


def fingerprint(dataset: dict[str, Any]) -> str:
    canonical = json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_bundle(manifest: Any, files: Any) -> dict[str, Any]:
    dataset, errors = parse_bundle(manifest, files)
    if dataset is None:
        return {"ok": False, "errors": errors, "counts": {}, "fingerprint": None}
    return {
        "ok": True,
        "errors": [],
        "counts": {t: len(dataset[t]) for t in TABLES},
        "fingerprint": fingerprint(dataset),
        "as_of": dataset["meta"]["as_of"],
    }
