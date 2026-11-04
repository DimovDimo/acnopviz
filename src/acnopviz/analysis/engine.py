from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import numpy as np

from ..money import dollars
from .statistics import (
    early_payment_yield,
    holm_adjust,
    moving_block_bootstrap,
    trend_test,
    wilson_interval,
)

MIN_BUFFER = 25000.0


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _rid(kind: str, entity: str, as_of: str) -> str:
    return kind[:3] + "-" + hashlib.sha256(f"{kind}|{entity}|{as_of}".encode()).hexdigest()[:12]


def is_paid(row: dict[str, Any]) -> bool:
    return bool(row.get("paid_date")) and row.get("paid_amount_cents") is not None


def is_overdue(row: dict[str, Any], as_of: str) -> bool:
    return not is_paid(row) and row["due_date"] < as_of


def monthly_cash_series(cash: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"receipts": 0, "payments": 0})
    for tx in cash:
        if tx["txn_date"] > as_of:
            continue
        month = tx["txn_date"][:7]
        if tx["amount_cents"] >= 0:
            totals[month]["receipts"] += tx["amount_cents"]
        else:
            totals[month]["payments"] += -tx["amount_cents"]
    out = []
    for month in sorted(totals):
        r, p = totals[month]["receipts"], totals[month]["payments"]
        out.append(
            {"month": month, "receipts": dollars(r), "payments": dollars(p), "net": dollars(r - p)}
        )
    return out


def cash_balance(dataset: dict[str, Any]) -> float:
    cents = int(dataset["meta"].get("opening_cash_cents", "0"))
    cents += sum(
        tx["amount_cents"]
        for tx in dataset["cash_transactions"]
        if tx["txn_date"] <= dataset["meta"]["as_of"]
    )
    return dollars(cents)


def overview(dataset: dict[str, Any]) -> dict[str, Any]:
    as_of = dataset["meta"]["as_of"]
    invoices, bills = dataset["invoices"], dataset["bills"]
    overdue = [r for r in invoices if is_overdue(r, as_of)]
    open_ap = [r for r in bills if not is_paid(r) and r["due_date"] >= as_of]
    series = monthly_cash_series(dataset["cash_transactions"], as_of)
    last = series[-1] if series else {"receipts": 0, "payments": 0, "net": 0}
    aging = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    for r in invoices:
        if is_paid(r):
            continue
        days = (_d(as_of) - _d(r["due_date"])).days
        key = (
            "current"
            if days <= 0
            else "1_30"
            if days <= 30
            else "31_60"
            if days <= 60
            else "61_90"
            if days <= 90
            else "90_plus"
        )
        aging[key] += r["amount_cents"]
    return {
        "as_of": as_of,
        "currency": dataset["meta"]["currency"],
        "cash": cash_balance(dataset),
        "overdue_ar": dollars(sum(r["amount_cents"] for r in overdue)),
        "overdue_ar_count": len(overdue),
        "open_ap": dollars(sum(r["amount_cents"] for r in open_ap)),
        "open_ap_count": len(open_ap),
        "last_month_receipts": last["receipts"],
        "last_month_payments": last["payments"],
        "last_month_net": last["net"],
        "monthly_series": series,
        "aging": {k: dollars(v) for k, v in aging.items()},
        "counts": {
            "customers": len(dataset["customers"]),
            "vendors": len(dataset["vendors"]),
            "invoices": len(invoices),
            "bills": len(bills),
            "cash_transactions": len(dataset["cash_transactions"]),
        },
    }


def _collection_recommendations(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = dataset["meta"]["as_of"]
    by_customer: dict[str, list[dict]] = defaultdict(list)
    for inv in dataset["invoices"]:
        if inv["due_date"] <= as_of:
            by_customer[inv["customer_id"]].append(inv)
    matured = [r for rows in by_customer.values() for r in rows]

    def late(r: dict) -> bool:
        return (r.get("paid_date") and r["paid_date"] > r["due_date"]) or is_overdue(r, as_of)

    baseline = sum(late(r) for r in matured) / max(1, len(matured))
    names = {c["id"]: c["name"] for c in dataset["customers"]}
    out = []
    for cid, rows in by_customer.items():
        n = len(rows)
        k = sum(late(r) for r in rows)
        open_overdue = [r for r in rows if is_overdue(r, as_of)]
        if n < 8 or not open_overdue:
            continue
        interval = wilson_interval(k, n)
        if interval.lower <= baseline or interval.estimate < 0.35:
            continue
        exposure = sum(r["amount_cents"] for r in open_overdue)
        out.append(
            {
                "id": _rid("collection", cid, as_of),
                "kind": "collection",
                "entity": names[cid],
                "title": f"Prioritize collection review: {names[cid]}",
                "summary": f"{dollars(exposure):,.2f} USD is overdue. Historical late-payment rate is {interval.estimate:.1%} (95% Wilson CI {interval.lower:.1%}–{interval.upper:.1%}), above the portfolio baseline {baseline:.1%}.",
                "action": "Review the overdue invoices, confirm disputes or credits, and agree a dated collection plan. Do not treat the overdue balance as a loss or guaranteed recovery.",
                "estimated_value": dollars(exposure),
                "value_label": "Overdue exposure (not savings)",
                "priority": round(dollars(exposure) * interval.estimate, 2),
                "confidence": "Statistical signal",
                "method": "Wilson score interval for customer late-payment proportion; compare lower bound with portfolio baseline.",
                "assumptions": [
                    "Matured invoices are comparable within customer",
                    "Late payment is a binary outcome, not default probability",
                    "No seasonality or credit-limit adjustment",
                ],
                "evidence": {
                    "customer_id": cid,
                    "matured_invoices": n,
                    "late_invoices": k,
                    "late_rate": interval.estimate,
                    "ci_low": interval.lower,
                    "ci_high": interval.upper,
                    "portfolio_baseline": baseline,
                    "overdue_invoice_ids": [r["id"] for r in open_overdue],
                },
            }
        )
    return out


def _normalize_invoice_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def duplicate_candidates(
    bills: list[dict[str, Any]], window_days: int = 14
) -> list[list[dict[str, Any]]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for bill in bills:
        key = (
            bill["vendor_id"],
            _normalize_invoice_number(bill["invoice_number"]),
            bill["amount_cents"],
        )
        groups[key].append(bill)
    out = []
    for rows in groups.values():
        rows = sorted(rows, key=lambda r: (r["issue_date"], r["id"]))
        cluster = [rows[0]]
        for row in rows[1:]:
            if (_d(row["issue_date"]) - _d(cluster[0]["issue_date"])).days <= window_days:
                cluster.append(row)
            else:
                if len(cluster) > 1:
                    out.append(cluster)
                cluster = [row]
        if len(cluster) > 1:
            out.append(cluster)
    return out


def _duplicate_recommendations(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = dataset["meta"]["as_of"]
    names = {v["id"]: v["name"] for v in dataset["vendors"]}
    out = []
    for cluster in duplicate_candidates(dataset["bills"]):
        first = cluster[0]
        exposure = sum(r["amount_cents"] for r in cluster[1:])
        out.append(
            {
                "id": _rid("duplicate", first["id"], as_of),
                "kind": "duplicate",
                "entity": names[first["vendor_id"]],
                "title": f"Review possible duplicate payment: {names[first['vendor_id']]}",
                "summary": f"{len(cluster)} bills share vendor, normalized invoice number {first['invoice_number']}, and amount within 14 days. Potential duplicate exposure is {dollars(exposure):,.2f} USD.",
                "action": "Match each bill to the purchase order, receipt, and bank payment. Confirm whether this is a duplicate, installment, or corrected invoice before any recovery action.",
                "estimated_value": dollars(exposure),
                "value_label": "Potential duplicate exposure (unconfirmed)",
                "priority": dollars(exposure) * 1.2,
                "confidence": "Deterministic control match",
                "method": "Exact match on vendor + normalized invoice number + amount; issue dates within 14 days.",
                "assumptions": [
                    "Invoice numbers are reliable",
                    "Legitimate installments may share a number",
                    "Match is not proof of fraud or error",
                ],
                "evidence": {
                    "bill_ids": [r["id"] for r in cluster],
                    "invoice_number": first["invoice_number"],
                    "amounts": [dollars(r["amount_cents"]) for r in cluster],
                    "paid_count": sum(is_paid(r) for r in cluster),
                },
            }
        )
    return out


def discount_opportunities(
    dataset: dict[str, Any], financing_rate: float = 0.08
) -> list[dict[str, Any]]:
    as_of = _d(dataset["meta"]["as_of"])
    names = {v["id"]: v["name"] for v in dataset["vendors"]}
    out = []
    for bill in dataset["bills"]:
        if is_paid(bill) or bill["discount_percent"] <= 0:
            continue
        issue = _d(bill["issue_date"])
        deadline = issue + timedelta(days=bill["discount_days"])
        due = _d(bill["due_date"])
        if not issue <= as_of <= deadline or due <= deadline:
            continue
        d = bill["discount_percent"] / 100
        net_days = (due - issue).days
        yield_ = early_payment_yield(d, net_days, bill["discount_days"])
        if yield_ <= financing_rate:
            continue
        amount = bill["amount_cents"] / 100
        pay_now = amount * (1 - d)
        days = (due - deadline).days
        discount = amount * d
        financing_cost = pay_now * financing_rate * days / 365
        net = discount - financing_cost
        if net <= 0:
            continue
        out.append(
            {
                "bill_id": bill["id"],
                "vendor": names[bill["vendor_id"]],
                "amount": amount,
                "pay_now": pay_now,
                "discount": discount,
                "annualized_yield": yield_,
                "financing_cost": financing_cost,
                "net_savings": net,
                "deadline": deadline.isoformat(),
                "due_date": due.isoformat(),
                "days_accelerated": days,
            }
        )
    return out


def _discount_recommendations(
    dataset: dict[str, Any], financing_rate: float
) -> list[dict[str, Any]]:
    as_of = dataset["meta"]["as_of"]
    cash = cash_balance(dataset)
    out = []
    for opp in discount_opportunities(dataset, financing_rate):
        if cash - opp["pay_now"] < MIN_BUFFER:
            continue
        out.append(
            {
                "id": _rid("discount", opp["bill_id"], as_of),
                "kind": "discount",
                "entity": opp["vendor"],
                "title": f"Evaluate early-payment discount: {opp['vendor']}",
                "summary": f"Pay {opp['pay_now']:,.2f} USD by {opp['deadline']} instead of {opp['amount']:,.2f} on {opp['due_date']}. Simple annualized discount yield is {opp['annualized_yield']:.1%} versus financing APR {financing_rate:.1%}.",
                "action": "Confirm goods/services and contract terms, then compare the net benefit with liquidity needs. This is a review suggestion, not a payment instruction.",
                "estimated_value": round(opp["net_savings"], 2),
                "value_label": "Illustrative net savings after financing cost",
                "priority": round(opp["net_savings"], 2),
                "confidence": "Deterministic financial math",
                "method": "Annualized yield = d/(1-d) × 365/(net days − discount days); dollar financing cost = discounted payment × APR × accelerated days/365.",
                "assumptions": [
                    f"Financing APR is {financing_rate:.2%}",
                    "Simple interest, 365-day year",
                    f"Cash buffer remains at least {MIN_BUFFER:,.0f} USD after payment",
                    "No fees, taxes, or credit-risk change",
                ],
                "evidence": opp,
            }
        )
    return out


def expense_drift(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = dataset["meta"]["as_of"]
    months = sorted({b["issue_date"][:7] for b in dataset["bills"] if b["issue_date"] <= as_of})
    # Use only complete months; the demo snapshot is month-end.
    totals: dict[str, list[float]] = defaultdict(list)
    for category in sorted({b["category"] for b in dataset["bills"]}):
        for month in months:
            totals[category].append(
                sum(
                    b["amount_cents"]
                    for b in dataset["bills"]
                    if b["category"] == category and b["issue_date"][:7] == month
                )
                / 100
            )
    tests = []
    for category, values in totals.items():
        if len(values) < 8 or sum(v > 0 for v in values) < 6:
            continue
        t = trend_test(values)
        t["category"] = category
        t["values"] = values
        tests.append(t)
    adjusted = holm_adjust([float(t["p_value"]) for t in tests])
    out = []
    for t, p_adj in zip(tests, adjusted, strict=True):
        values = t["values"]
        base = float(np.median(values[:3]))
        relative = float(t["slope"]) * (len(values) - 1) / max(base, 1.0)
        t["p_adjusted"] = p_adj
        t["relative_change"] = relative
        t["flagged"] = bool(
            t["slope"] > 0 and t["slope_low"] > 0 and p_adj < 0.05 and relative >= 0.15
        )
        out.append(t)
    return out


def _expense_recommendations(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = dataset["meta"]["as_of"]
    months = sorted({b["issue_date"][:7] for b in dataset["bills"] if b["issue_date"] <= as_of})
    out = []
    for t in expense_drift(dataset):
        if not t["flagged"]:
            continue
        category = str(t["category"])
        out.append(
            {
                "id": _rid("expense", category, as_of),
                "kind": "expense",
                "entity": category,
                "title": f"Investigate upward expense drift: {category}",
                "summary": f"{category} bills show a robust upward slope of {t['slope']:,.2f} USD/month (95% CI {t['slope_low']:,.2f} to {t['slope_high']:,.2f}); Holm-adjusted p={t['p_adjusted']:.4f}.",
                "action": "Review vendor contracts, usage, and one-off purchases. The slope is a review signal, not an amount that can automatically be cut.",
                "estimated_value": round(float(t["slope"]), 2),
                "value_label": "Estimated monthly drift (not savings)",
                "priority": round(float(t["slope"]) * 6, 2),
                "confidence": "Statistical signal",
                "method": "Theil–Sen slope with 95% CI; two-sided Kendall tau; Holm adjustment across expense categories; minimum 15% relative drift.",
                "assumptions": [
                    "Monthly bill totals are comparable",
                    "No causal claim about why spend changed",
                    "Trend may not persist",
                    "Accrual bill dates, not cash payment dates",
                ],
                "evidence": {
                    "category": category,
                    "months": months,
                    "values": t["values"],
                    **{k: v for k, v in t.items() if k not in ("values", "category")},
                },
            }
        )
    return out


def liquidity_simulation(
    dataset: dict[str, Any],
    horizon: int = 6,
    paths: int = 2000,
    block: int = 3,
    seed: int = 42,
    financing_rate: float = 0.08,
    recovery_uplift: float = 0.0,
    expense_reduction: float = 0.0,
) -> dict[str, Any]:
    series = monthly_cash_series(dataset["cash_transactions"], dataset["meta"]["as_of"])
    net = [r["net"] for r in series]
    cash = cash_balance(dataset)
    # Small imported ledgers may have fewer months than the configured block.
    # Fall back to one-month blocks (or a zero-flow placeholder) instead of failing.
    effective_block = min(block, len(net)) if net else 1
    bootstrap_net = net if net else [0.0]
    base = moving_block_bootstrap(bootstrap_net, cash, horizon, paths, effective_block, seed)
    avg_payments = float(np.mean([r["payments"] for r in series])) if series else 0.0
    monthly_savings = avg_payments * expense_reduction
    one_time = overview(dataset)["overdue_ar"] * recovery_uplift
    scenario = moving_block_bootstrap(
        bootstrap_net, cash, horizon, paths, effective_block, seed, monthly_savings, one_time
    )
    return {
        "baseline": base,
        "scenario": scenario,
        "financing_rate": financing_rate,
        "recovery_uplift": recovery_uplift,
        "expense_reduction": expense_reduction,
        "assumptions": [
            "Historical monthly net flows are resampled in blocks",
            "Recovery uplift is one-time cash in month 1",
            "Expense reduction applies to average historical monthly payments",
            "No new financing, taxes, capex, or committed invoice calendar",
            "Discount recommendations are evaluated separately and not added to cash paths",
        ],
    }


def _liquidity_recommendation(
    dataset: dict[str, Any], horizon: int, paths: int, block: int, seed: int
) -> list[dict[str, Any]]:
    sim = liquidity_simulation(dataset, horizon, paths, block, seed)["baseline"]
    if sim["prob_negative"] <= 0.05 and sim["reserve_for_90pct_paths"] <= 0:
        return []
    as_of = dataset["meta"]["as_of"]
    reserve = sim["reserve_for_90pct_paths"]
    return [
        {
            "id": _rid("liquidity", f"portfolio-{horizon}", as_of),
            "kind": "liquidity",
            "entity": "Portfolio",
            "title": "Review liquidity buffer for downside cash paths",
            "summary": f"In {sim['paths']:,} seeded {horizon}-month block-bootstrap paths, {sim['prob_negative']:.1%} dip below zero. The additional reserve covering the 10th-percentile minimum balance is {reserve:,.2f} USD.",
            "action": "Compare the simulated reserve with committed receipts/payments and available facilities. Validate the historical window before changing cash policy.",
            "estimated_value": round(reserve, 2),
            "value_label": "Illustrative additional reserve (not savings)",
            "priority": round(reserve * 0.2 + sim["prob_negative"] * 10000, 2),
            "confidence": "Scenario simulation",
            "method": "Moving-block bootstrap of monthly net operating cash flows; report probability of any negative month-end balance and 10th-percentile minimum-balance shortfall.",
            "assumptions": [
                "Historical dependence approximated by 3-month blocks",
                "No committed future invoice calendar",
                "No new financing or extraordinary items",
                "Simulation is not a guaranteed forecast",
            ],
            "evidence": sim,
        }
    ]


def data_quality(dataset: dict[str, Any]) -> dict[str, Any]:
    as_of = dataset["meta"]["as_of"]
    customers = {c["id"] for c in dataset["customers"]}
    vendors = {v["id"] for v in dataset["vendors"]}
    checks = []

    def add(name: str, ok: bool, detail: str, severity: str = "fail") -> None:
        checks.append({"name": name, "status": "pass" if ok else severity, "detail": detail})

    add(
        "AR customer references",
        all(r["customer_id"] in customers for r in dataset["invoices"]),
        "Every invoice references a known customer.",
    )
    add(
        "AP vendor references",
        all(r["vendor_id"] in vendors for r in dataset["bills"]),
        "Every bill references a known vendor.",
    )
    add(
        "Positive document amounts",
        all(r["amount_cents"] > 0 for r in dataset["invoices"] + dataset["bills"]),
        "Invoice and bill amounts are positive integer cents.",
    )
    add(
        "No future-paid documents",
        all(
            not r.get("paid_date") or r["paid_date"] <= as_of
            for r in dataset["invoices"] + dataset["bills"]
        ),
        "Paid dates do not exceed the snapshot date.",
    )
    add(
        "Paid documents have settlement",
        all(
            not is_paid(r) or r["paid_amount_cents"] > 0
            for r in dataset["invoices"] + dataset["bills"]
        ),
        "Paid documents carry a positive settlement amount.",
    )
    ar_paid = sum(r["paid_amount_cents"] or 0 for r in dataset["invoices"])
    ar_cash = sum(
        tx["amount_cents"] for tx in dataset["cash_transactions"] if tx["source_type"] == "invoice"
    )
    ap_paid = sum(r["paid_amount_cents"] or 0 for r in dataset["bills"])
    ap_cash = -sum(
        tx["amount_cents"] for tx in dataset["cash_transactions"] if tx["source_type"] == "bill"
    )
    add(
        "AR settlement reconciliation",
        ar_paid == ar_cash,
        f"AR settlements {dollars(ar_paid):,.2f} equal linked cash receipts {dollars(ar_cash):,.2f}.",
    )
    add(
        "AP settlement reconciliation",
        ap_paid == ap_cash,
        f"AP settlements {dollars(ap_paid):,.2f} equal linked cash payments {dollars(ap_cash):,.2f}.",
    )
    add(
        "Unique document IDs",
        len({r["id"] for r in dataset["invoices"] + dataset["bills"]})
        == len(dataset["invoices"]) + len(dataset["bills"]),
        "AR and AP identifiers are unique.",
    )
    dupes = duplicate_candidates(dataset["bills"])
    add(
        "Duplicate-payment candidates",
        not dupes,
        f"{len(dupes)} candidate cluster(s) require human review.",
        severity="warn",
    )
    failed = sum(c["status"] == "fail" for c in checks)
    warned = sum(c["status"] == "warn" for c in checks)
    return {
        "as_of": as_of,
        "checks": checks,
        "passed": sum(c["status"] == "pass" for c in checks),
        "failed": failed,
        "warnings": warned,
        "status": "fail" if failed else "warn" if warned else "pass",
    }


def build_recommendations(
    dataset: dict[str, Any],
    financing_rate: float = 0.08,
    horizon: int = 6,
    paths: int = 2000,
    block: int = 3,
    seed: int = 42,
) -> list[dict[str, Any]]:
    recs = (
        _collection_recommendations(dataset)
        + _duplicate_recommendations(dataset)
        + _discount_recommendations(dataset, financing_rate)
        + _expense_recommendations(dataset)
        + _liquidity_recommendation(dataset, horizon, paths, block, seed)
    )
    reviews = {r["recommendation_id"]: r for r in dataset.get("reviews", [])}
    for rec in recs:
        review = reviews.get(rec["id"])
        rec["review_status"] = review["status"] if review else "new"
        rec["review_note"] = review["note"] if review else ""
        rec["review_updated_at"] = review["updated_at"] if review else None
    return sorted(recs, key=lambda r: (-r["priority"], r["id"]))
