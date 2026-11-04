from __future__ import annotations

from typing import Any

import numpy as np

from .engine import monthly_cash_series
from .statistics import moving_block_bootstrap


def _metrics(
    pred: np.ndarray, actual: np.ndarray, lo: np.ndarray | None = None, hi: np.ndarray | None = None
) -> dict[str, float | None]:
    err = pred - actual
    out = {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "bias": float(np.mean(err)),
    }
    if lo is not None and hi is not None:
        out["coverage_p10_p90"] = float(np.mean((actual >= lo) & (actual <= hi)))
        out["mean_interval_width"] = float(np.mean(hi - lo))
    else:
        out["coverage_p10_p90"] = None
        out["mean_interval_width"] = None
    return out


def walk_forward_backtest(
    dataset: dict[str, Any],
    horizon: int = 3,
    min_train: int = 9,
    paths: int = 500,
    block: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    if not 1 <= horizon <= 6:
        raise ValueError("horizon must be between 1 and 6")
    if not 6 <= min_train <= 36:
        raise ValueError("min_train must be between 6 and 36")
    series = monthly_cash_series(dataset["cash_transactions"], dataset["meta"]["as_of"])
    net = [r["net"] for r in series]
    labels = [r["month"] for r in series]
    folds = []
    if len(net) >= min_train + horizon:
        for origin in range(min_train, len(net) - horizon + 1):
            train = net[:origin]
            test = np.asarray(net[origin : origin + horizon], dtype=float)
            sim = moving_block_bootstrap(train, 0.0, horizon, paths, block, seed + origin)
            pred = np.asarray(sim["p50"], dtype=float)
            lo = np.asarray(sim["p10"], dtype=float)
            hi = np.asarray(sim["p90"], dtype=float)
            actual = np.cumsum(test)
            naive = np.full(horizon, train[-1], dtype=float).cumsum()
            folds.append(
                {
                    "origin_month": labels[origin - 1],
                    "train_months": origin,
                    "test_months": labels[origin : origin + horizon],
                    "actual_cumulative_net": actual.tolist(),
                    "bootstrap_cumulative_p50": pred.tolist(),
                    "bootstrap_cumulative_p10": lo.tolist(),
                    "bootstrap_cumulative_p90": hi.tolist(),
                    "naive_last_cumulative": naive.tolist(),
                    "bootstrap_metrics": _metrics(pred, actual, lo, hi),
                    "naive_metrics": _metrics(naive, actual),
                }
            )
    if folds:
        boot = {
            k: float(np.mean([f["bootstrap_metrics"][k] for f in folds]))
            for k in ("mae", "rmse", "bias", "coverage_p10_p90", "mean_interval_width")
        }
        naive = {
            k: float(np.mean([f["naive_metrics"][k] for f in folds]))
            for k in ("mae", "rmse", "bias")
        }
        winner = "bootstrap" if boot["mae"] <= naive["mae"] else "naive_last"
    else:
        boot = naive = {}
        winner = None
    return {
        "status": "ok" if folds else "insufficient_data",
        "model": "historical_monthly_net_block_bootstrap",
        "horizon": horizon,
        "min_train": min_train,
        "paths": paths,
        "block": block,
        "seed": seed,
        "fold_count": len(folds),
        "bootstrap": boot,
        "naive_last": naive,
        "lower_mae_model": winner,
        "folds": folds,
        "limitations": [
            "Synthetic data only; results are not evidence of real-world forecasting skill",
            "Expanding-window folds overlap; fold errors are not independent",
            "Coverage is empirical P10–P90 coverage on cumulative net flow, not a guarantee",
            "Backtest evaluates the historical liquidity model, not the committed runoff calendar",
        ],
    }
