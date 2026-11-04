from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Interval:
    estimate: float
    lower: float
    upper: float


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> Interval:
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("require n > 0 and 0 <= successes <= n")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    z = stats.norm.ppf(0.5 + confidence / 2)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lower = 0.0 if successes == 0 else max(0.0, float(center - half))
    upper = 1.0 if successes == n else min(1.0, float(center + half))
    return Interval(float(p), lower, upper)


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    if m == 0:
        return []
    order = np.argsort(p_values, kind="stable")
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        p = float(p_values[int(idx)])
        if not 0 <= p <= 1 or not math.isfinite(p):
            raise ValueError("p-values must be finite and in [0, 1]")
        running = max(running, (m - rank) * p)
        adjusted[int(idx)] = min(1.0, running)
    return adjusted


def trend_test(values: list[float]) -> dict[str, float | int]:
    """Theil-Sen slope with 95% CI and two-sided Kendall tau test."""
    y = np.asarray(values, dtype=float)
    if y.ndim != 1 or len(y) < 4 or not np.all(np.isfinite(y)):
        raise ValueError("trend requires at least four finite observations")
    x = np.arange(len(y), dtype=float)
    fit = stats.theilslopes(y, x, alpha=0.95)
    tau = stats.kendalltau(x, y)
    return {
        "n": len(y),
        "slope": float(fit.slope),
        "slope_low": float(fit.low_slope),
        "slope_high": float(fit.high_slope),
        "tau": float(tau.statistic),
        "p_value": float(tau.pvalue),
    }


def early_payment_yield(discount_fraction: float, net_days: int, discount_days: int) -> float:
    if not 0 < discount_fraction < 1:
        raise ValueError("discount fraction must be in (0, 1)")
    if net_days <= discount_days or discount_days < 0:
        raise ValueError("net days must exceed discount days")
    return discount_fraction / (1 - discount_fraction) * 365 / (net_days - discount_days)


def moving_block_bootstrap(
    monthly_net: list[float],
    starting_cash: float,
    horizon: int,
    paths: int = 2000,
    block: int = 3,
    seed: int = 42,
    monthly_savings: float = 0.0,
    one_time_cash: float = 0.0,
) -> dict:
    """Seeded moving-block bootstrap of monthly net operating cash flow.

    Blocks preserve short local dependence. This is a historical-resampling stress
    test, not a causal forecast or a model of committed future invoices.
    """
    flows = np.asarray(monthly_net, dtype=float)
    if flows.ndim != 1 or len(flows) < block or not np.all(np.isfinite(flows)):
        raise ValueError("need at least `block` finite monthly observations")
    if not 1 <= horizon <= 24 or not 100 <= paths <= 20000 or block < 1:
        raise ValueError("invalid horizon, paths, or block size")
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(horizon / block)
    starts = rng.integers(0, len(flows) - block + 1, size=(paths, n_blocks))
    idx = starts[:, :, None] + np.arange(block)[None, None, :]
    sampled = flows[idx.reshape(paths, -1)][:, :horizon] + monthly_savings
    ending = starting_cash + one_time_cash + np.cumsum(sampled, axis=1)
    min_balance = ending.min(axis=1)
    q = [0.10, 0.50, 0.90]
    # Quantiles are across simulated paths (axis 0), separately for each month.
    bands = np.quantile(ending, q, axis=0)
    negative = np.any(ending < 0, axis=1)
    reserve = max(0.0, -float(np.quantile(min_balance, 0.10)))
    return {
        "horizon": horizon,
        "paths": paths,
        "block": block,
        "seed": seed,
        "starting_cash": float(starting_cash + one_time_cash),
        "monthly_savings": float(monthly_savings),
        "one_time_cash": float(one_time_cash),
        "months": list(range(1, horizon + 1)),
        "p10": bands[0].tolist(),
        "p50": bands[1].tolist(),
        "p90": bands[2].tolist(),
        "prob_negative": float(negative.mean()),
        "prob_negative_month_end": float((ending[:, -1] < 0).mean()),
        "reserve_for_90pct_paths": reserve,
        "median_ending_cash": float(np.median(ending[:, -1])),
        "mean_monthly_net": float(flows.mean()),
        "observations": len(flows),
    }
