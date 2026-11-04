from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import numpy as np

from ..money import dollars
from .engine import cash_balance, is_paid


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _month_index(as_of: date, day: date) -> int:
    """0 = first month after the snapshot month."""
    return (day.year - as_of.year) * 12 + day.month - as_of.month - 1


def _month_label(as_of: date, idx: int) -> str:
    m = as_of.month + idx + 1
    y = as_of.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def _delays(invoices: list[dict[str, Any]]) -> tuple[dict[str, list[int]], list[int]]:
    by_customer: dict[str, list[int]] = defaultdict(list)
    portfolio: list[int] = []
    for inv in invoices:
        if inv.get("paid_date"):
            delay = (_d(inv["paid_date"]) - _d(inv["due_date"])).days
            by_customer[inv["customer_id"]].append(delay)
            portfolio.append(delay)
    return by_customer, portfolio or [0]


def recurring_monthly_net(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Historical cash flows not linked to AR/AP settlements.

    Linked settlements are represented by the open-document calendar instead;
    excluding them here prevents double counting.
    """
    as_of = dataset["meta"]["as_of"]
    totals: dict[str, int] = defaultdict(int)
    for tx in dataset["cash_transactions"]:
        if tx["txn_date"] > as_of:
            continue
        if tx.get("source_type") in ("invoice", "bill"):
            continue
        totals[tx["txn_date"][:7]] += tx["amount_cents"]
    return [{"month": m, "net": dollars(c)} for m, c in sorted(totals.items())]


def cash_calendar(
    dataset: dict[str, Any],
    horizon: int = 6,
    paths: int = 2000,
    block: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    if not 1 <= horizon <= 12:
        raise ValueError("horizon must be between 1 and 12")
    as_of = _d(dataset["meta"]["as_of"])
    cash = cash_balance(dataset)
    rng = np.random.default_rng(seed)
    open_ar = [r for r in dataset["invoices"] if not is_paid(r)]
    open_ap = [r for r in dataset["bills"] if not is_paid(r)]
    delays_by_customer, portfolio_delays = _delays(dataset["invoices"])

    ar_paths = np.zeros((paths, horizon), dtype=float)
    ar_expected = np.zeros(horizon, dtype=float)
    for inv in open_ar:
        due = _d(inv["due_date"])
        amount = inv["amount_cents"] / 100
        delays = delays_by_customer.get(inv["customer_id"]) or portfolio_delays
        overdue_days = max(0, (as_of - due).days)
        draws = rng.choice(delays, size=paths)
        for p, delay in enumerate(draws):
            delay = int(delay)
            if overdue_days:
                receipt = as_of + timedelta(days=max(1, delay - overdue_days))
            else:
                receipt = due + timedelta(days=max(0, delay))
            idx = _month_index(as_of, receipt)
            if 0 <= idx < horizon:
                ar_paths[p, idx] += amount
        median_delay = int(round(float(np.median(delays))))
        if overdue_days:
            receipt = as_of + timedelta(days=max(1, median_delay - overdue_days))
        else:
            receipt = due + timedelta(days=max(0, median_delay))
        idx = _month_index(as_of, receipt)
        if 0 <= idx < horizon:
            ar_expected[idx] += amount

    ap_monthly = np.zeros(horizon, dtype=float)
    ap_scheduled = 0
    for bill in open_ap:
        due = _d(bill["due_date"])
        pay_day = due if due > as_of else as_of + timedelta(days=1)
        idx = _month_index(as_of, pay_day)
        if 0 <= idx < horizon:
            ap_monthly[idx] += bill["amount_cents"] / 100
            ap_scheduled += bill["amount_cents"]

    recurring = [r["net"] for r in recurring_monthly_net(dataset)]
    if recurring:
        eff_block = min(block, len(recurring))
        flows = np.asarray(recurring, dtype=float)
        n_blocks = int(np.ceil(horizon / eff_block))
        starts = rng.integers(0, len(flows) - eff_block + 1, size=(paths, n_blocks))
        idx = starts[:, :, None] + np.arange(eff_block)[None, None, :]
        recurring_paths = flows[idx.reshape(paths, -1)][:, :horizon]
        recurring_expected = float(np.median(flows))
    else:
        recurring_paths = np.zeros((paths, horizon), dtype=float)
        recurring_expected = 0.0

    net_paths = ar_paths - ap_monthly[None, :] + recurring_paths
    ending = cash + np.cumsum(net_paths, axis=1)
    bands = np.quantile(ending, [0.10, 0.50, 0.90], axis=0)
    expected_net = ar_expected - ap_monthly + recurring_expected
    expected_ending = cash + np.cumsum(expected_net)
    negative = np.any(ending < 0, axis=1)
    min_balance = ending.min(axis=1)

    months = []
    for i in range(horizon):
        months.append(
            {
                "month": _month_label(as_of, i),
                "ar_receipts": round(float(ar_expected[i]), 2),
                "ap_payments": round(float(ap_monthly[i]), 2),
                "recurring_net": round(recurring_expected, 2),
                "expected_net": round(float(expected_net[i]), 2),
                "expected_ending_cash": round(float(expected_ending[i]), 2),
                "p10_ending_cash": round(float(bands[0, i]), 2),
                "p50_ending_cash": round(float(bands[1, i]), 2),
                "p90_ending_cash": round(float(bands[2, i]), 2),
            }
        )
    return {
        "as_of": dataset["meta"]["as_of"],
        "horizon": horizon,
        "paths": paths,
        "block": block,
        "seed": seed,
        "starting_cash": cash,
        "months": months,
        "prob_negative": float(negative.mean()),
        "reserve_for_90pct_paths": max(0.0, -float(np.quantile(min_balance, 0.10))),
        "totals": {
            "open_ar": dollars(sum(r["amount_cents"] for r in open_ar)),
            "open_ap": dollars(sum(r["amount_cents"] for r in open_ap)),
            "ar_scheduled": round(float(ar_expected.sum()), 2),
            "ap_scheduled": dollars(ap_scheduled),
            "recurring_monthly_median": round(recurring_expected, 2),
        },
        "assumptions": [
            "Runoff calendar: schedules open AR/AP only; no new sales or purchases are created",
            "AR timing draws from historical customer payment delays; overdue invoices use residual delay",
            "AP pays gross at due date (next day if already overdue); discounts are not auto-applied",
            "Recurring overhead resamples historical cash flows not linked to invoice/bill settlements",
            "No default losses, taxes, capex, financing, or committed facility draws",
        ],
    }
