from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_cents(value: float | int | str | Decimal) -> int:
    """Round a decimal currency amount to integer cents (half up)."""
    d = Decimal(str(value))
    if not d.is_finite():
        raise ValueError("currency amount must be finite")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def dollars(cents: int) -> float:
    return float(Decimal(cents) / Decimal(100))


def pct(value: float, digits: int = 2) -> float:
    return round(value * 100, digits)
