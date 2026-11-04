from __future__ import annotations

import calendar
import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from .money import to_cents

CUSTOMERS = [
    ("C01", "Northwind Studio", "Enterprise", 30, 0.10),
    ("C02", "Blue Harbor Retail", "Mid-market", 30, 0.45),
    ("C03", "Cedar Labs", "Enterprise", 45, 0.15),
    ("C04", "Delta Field Services", "Mid-market", 30, 0.65),
    ("C05", "Evergreen Health", "Enterprise", 45, 0.20),
    ("C06", "Fjord Logistics", "SMB", 30, 0.55),
    ("C07", "Golden Gate Media", "SMB", 30, 0.30),
    ("C08", "Horizon Education", "Mid-market", 30, 0.12),
]
VENDORS = [
    ("V01", "Cloudframe Systems", "Software", 2.0, 10),
    ("V02", "Signal Ads Co", "Marketing", 0.0, 0),
    ("V03", "Travelwise", "Travel", 0.0, 0),
    ("V04", "Ledger & Co Advisors", "Professional services", 1.0, 10),
    ("V05", "RouteOne Freight", "Logistics", 0.0, 0),
    ("V06", "Workplace Utilities", "Facilities", 0.0, 0),
    ("V07", "DevTools Union", "Software", 2.0, 10),
    ("V08", "Brandcraft Agency", "Marketing", 0.0, 0),
]


def month_ends(start: date, count: int) -> list[date]:
    out = []
    y, m = start.year, start.month
    for _ in range(count):
        out.append(date(y, m, calendar.monthrange(y, m)[1]))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def generate_dataset(seed: int = 20261104, as_of: str = "2026-10-31") -> dict[str, Any]:
    """Generate a reproducible 18-month demo ledger with planted review signals.

    Signals are not labels exposed to the analytics engine: late payers, duplicate
    bills, discount-eligible bills, and category drift arise from the records alone.
    """
    rng = np.random.default_rng(seed)
    snapshot = date.fromisoformat(as_of)
    start = date(2025, 5, 1)
    months = month_ends(start, 18)
    customers = [
        {"id": c[0], "name": c[1], "segment": c[2], "payment_terms_days": c[3]} for c in CUSTOMERS
    ]
    vendors = [{"id": v[0], "name": v[1], "category": v[2]} for v in VENDORS]
    invoices: list[dict[str, Any]] = []
    bills: list[dict[str, Any]] = []
    cash: list[dict[str, Any]] = []
    inv_n = bill_n = cash_n = 0

    def add_cash(
        day: date,
        cents: int,
        category: str,
        description: str,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> None:
        nonlocal cash_n
        cash_n += 1
        cash.append(
            {
                "id": f"TX{cash_n:05d}",
                "txn_date": day.isoformat(),
                "amount_cents": cents,
                "category": category,
                "description": description,
                "source_type": source_type,
                "source_id": source_id,
            }
        )

    for mi, me in enumerate(months):
        first = me.replace(day=1)
        # Accounts receivable: 12-16 invoices per month.
        for _ in range(int(rng.integers(12, 17))):
            cust = CUSTOMERS[int(rng.integers(0, len(CUSTOMERS)))]
            issue = first + timedelta(days=int(rng.integers(0, 27)))
            due = issue + timedelta(days=cust[3])
            amount = to_cents(round(float(rng.uniform(1800, 14000)), 2))
            late_prob = cust[4]
            if rng.random() < late_prob:
                delay = int(rng.integers(8, 46))
            else:
                delay = int(rng.integers(-6, 5))
            paid = due + timedelta(days=delay)
            # A subset of older invoices remains unpaid to create realistic overdue exposure.
            persistent_open = due < snapshot - timedelta(days=20) and rng.random() < (
                0.04 + late_prob * 0.12
            )
            inv_n += 1
            row = {
                "id": f"AR{inv_n:05d}",
                "customer_id": cust[0],
                "issue_date": issue.isoformat(),
                "due_date": due.isoformat(),
                "amount_cents": amount,
                "paid_date": None,
                "paid_amount_cents": None,
            }
            if paid <= snapshot and not persistent_open:
                row["paid_date"] = paid.isoformat()
                row["paid_amount_cents"] = amount
                add_cash(
                    paid,
                    amount,
                    "Receipts",
                    f"Receipt {row['id']} from {cust[1]}",
                    "invoice",
                    row["id"],
                )
            invoices.append(row)

        # Accounts payable: 9-13 bills per month, with software/marketing drift.
        for _ in range(int(rng.integers(9, 14))):
            # Software spend is modeled as a recurring contract below; exclude it
            # from the random bill mix so the planted drift is not drowned by noise.
            vendor = VENDORS[int(rng.choice([1, 2, 3, 4, 5, 7]))]
            issue = first + timedelta(days=int(rng.integers(0, 27)))
            due = issue + timedelta(days=30)
            base = float(rng.uniform(450, 5200))
            if vendor[2] == "Software":
                base *= 1 + 0.045 * mi
            elif vendor[2] == "Marketing":
                base *= 1 + 0.035 * mi
            amount = to_cents(round(base, 2))
            discount_pct, discount_days = vendor[3], vendor[4]
            pay_day = due
            paid_amount = amount
            if discount_pct and rng.random() < 0.35:
                pay_day = issue + timedelta(days=max(1, discount_days - 1))
                # amount is already integer cents; do not convert a second time.
                paid_amount = int(round(amount * (1 - discount_pct / 100)))
            bill_n += 1
            row = {
                "id": f"AP{bill_n:05d}",
                "vendor_id": vendor[0],
                "invoice_number": f"{vendor[0]}-{issue.strftime('%y%m')}-{bill_n:04d}",
                "issue_date": issue.isoformat(),
                "due_date": due.isoformat(),
                "amount_cents": amount,
                "paid_date": None,
                "paid_amount_cents": None,
                "category": vendor[2],
                "discount_percent": discount_pct,
                "discount_days": discount_days,
            }
            if pay_day <= snapshot:
                row["paid_date"] = pay_day.isoformat()
                row["paid_amount_cents"] = paid_amount
                add_cash(
                    pay_day,
                    -paid_amount,
                    vendor[2],
                    f"Payment {row['id']} to {vendor[1]}",
                    "bill",
                    row["id"],
                )
            bills.append(row)

        # Recurring category spend makes drift detectable above invoice-count noise.
        for vendor, base_amount, growth in ((VENDORS[0], 4200, 0.07), (VENDORS[1], 2600, 0.02)):
            issue = first + timedelta(days=4)
            bill_n += 1
            amount = to_cents(
                round(base_amount * (1 + growth * mi) * float(rng.uniform(0.98, 1.02)), 2)
            )
            iid = f"AP{bill_n:05d}"
            paid = issue + timedelta(days=29)
            row = {
                "id": iid,
                "vendor_id": vendor[0],
                "invoice_number": f"REC-{vendor[0]}-{mi:02d}",
                "issue_date": issue.isoformat(),
                "due_date": (issue + timedelta(days=30)).isoformat(),
                "amount_cents": amount,
                "paid_date": None,
                "paid_amount_cents": None,
                "category": vendor[2],
                "discount_percent": 0,
                "discount_days": 0,
            }
            if paid <= snapshot:
                row["paid_date"] = paid.isoformat()
                row["paid_amount_cents"] = amount
                add_cash(paid, -amount, vendor[2], f"Recurring payment {iid}", "bill", iid)
            bills.append(row)

        # Cash-only operating costs (not duplicated in AP analytics).
        payroll = to_cents(42000 + mi * 120 + float(rng.normal(0, 350)))
        rent = to_cents(8500)
        utilities = to_cents(round(float(rng.uniform(900, 1600)), 2))
        add_cash(me, -payroll, "Payroll", f"Payroll {me.strftime('%Y-%m')}")
        add_cash(me, -rent, "Facilities", f"Office rent {me.strftime('%Y-%m')}")
        add_cash(me, -utilities, "Facilities", f"Utilities {me.strftime('%Y-%m')}")

    # Planted duplicate-payment candidates: same vendor/number/amount, close issue dates.
    for k, vendor_id in enumerate(("V02", "V05", "V07")):
        issue = date(2026, 7 + k, 8)
        amount = to_cents(2400 + k * 750)
        number = f"DUP-2026-{k + 1:03d}"
        for copy in range(2):
            bill_n += 1
            iid = f"AP{bill_n:05d}"
            day = issue + timedelta(days=copy * 3)
            paid = day + timedelta(days=12)
            bills.append(
                {
                    "id": iid,
                    "vendor_id": vendor_id,
                    "invoice_number": number,
                    "issue_date": day.isoformat(),
                    "due_date": (day + timedelta(days=30)).isoformat(),
                    "amount_cents": amount,
                    "paid_date": paid.isoformat(),
                    "paid_amount_cents": amount,
                    "category": next(v[2] for v in VENDORS if v[0] == vendor_id),
                    "discount_percent": 0,
                    "discount_days": 0,
                }
            )
            add_cash(paid, -amount, "Duplicate candidate", f"Payment {iid} ({number})", "bill", iid)

    # Open, discount-eligible bills near the snapshot date.
    for k, vendor in enumerate((VENDORS[0], VENDORS[3], VENDORS[6])):
        issue = snapshot - timedelta(days=2 + k)
        bill_n += 1
        amount = to_cents(6800 + k * 2400)
        bills.append(
            {
                "id": f"AP{bill_n:05d}",
                "vendor_id": vendor[0],
                "invoice_number": f"EARLY-{k + 1:03d}",
                "issue_date": issue.isoformat(),
                "due_date": (issue + timedelta(days=30)).isoformat(),
                "amount_cents": amount,
                "paid_date": None,
                "paid_amount_cents": None,
                "category": vendor[2],
                "discount_percent": vendor[3],
                "discount_days": vendor[4],
            }
        )

    cash.sort(key=lambda r: (r["txn_date"], r["id"]))
    opening = to_cents(25000)
    dataset = {
        "meta": {
            "seed": str(seed),
            "as_of": as_of,
            "opening_cash_cents": str(opening),
            "currency": "USD",
            "schema_version": "1",
        },
        "customers": customers,
        "vendors": vendors,
        "invoices": invoices,
        "bills": bills,
        "cash_transactions": cash,
    }
    return dataset


def write_csv_dataset(dataset: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for table in ("customers", "vendors", "invoices", "bills", "cash_transactions"):
        rows = dataset[table]
        path = out_dir / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        files[path.name] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "name": "acnopviz-synthetic-ledger",
        "version": "1.0.0",
        "seed": int(dataset["meta"]["seed"]),
        "as_of": dataset["meta"]["as_of"],
        "currency": dataset["meta"]["currency"],
        "opening_cash_cents": int(dataset["meta"]["opening_cash_cents"]),
        "synthetic": True,
        "files": files,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
