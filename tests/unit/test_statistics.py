import math

import pytest

from acnopviz.analysis.statistics import (
    early_payment_yield,
    holm_adjust,
    moving_block_bootstrap,
    trend_test,
    wilson_interval,
)


def test_wilson_known_value():
    ci = wilson_interval(56, 100)
    assert math.isclose(ci.estimate, 0.56)
    assert math.isclose(ci.lower, 0.4622810465, abs_tol=1e-8)
    assert math.isclose(ci.upper, 0.6532797337, abs_tol=1e-8)


def test_wilson_boundaries():
    assert wilson_interval(0, 10).lower == 0.0
    assert wilson_interval(10, 10).upper == 1.0
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_holm_adjustment():
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([]) == []
    with pytest.raises(ValueError):
        holm_adjust([1.2])


def test_trend_detects_increase_and_decrease():
    up = trend_test([1, 2, 3, 4, 5, 6, 7, 8])
    down = trend_test([8, 7, 6, 5, 4, 3, 2, 1])
    flat = trend_test([5, 5, 5, 5, 5, 5])
    assert up["slope"] == 1 and up["slope_low"] > 0 and up["p_value"] < 0.05
    assert down["slope"] == -1 and down["slope_high"] < 0
    assert flat["slope"] == 0
    with pytest.raises(ValueError):
        trend_test([1, 2, 3])


def test_early_payment_yield_2_10_net_30():
    assert early_payment_yield(0.02, 30, 10) == pytest.approx(0.3724489796)
    with pytest.raises(ValueError):
        early_payment_yield(0.02, 10, 10)
    with pytest.raises(ValueError):
        early_payment_yield(0, 30, 10)


def test_bootstrap_reproducible_and_horizon():
    flows = [100, -50, 75, 20, -10, 60, 30, -20, 40]
    a = moving_block_bootstrap(flows, 1000, 6, paths=500, block=3, seed=7)
    b = moving_block_bootstrap(flows, 1000, 6, paths=500, block=3, seed=7)
    assert a == b
    assert len(a["p50"]) == 6
    assert 0 <= a["prob_negative"] <= 1
    assert a["p10"][-1] <= a["p50"][-1] <= a["p90"][-1]


def test_bootstrap_savings_shift_cash_up():
    flows = [10, -20, 5, 15, -5, 8]
    base = moving_block_bootstrap(flows, 100, 4, paths=400, block=2, seed=3)
    better = moving_block_bootstrap(
        flows, 100, 4, paths=400, block=2, seed=3, monthly_savings=50, one_time_cash=25
    )
    assert better["median_ending_cash"] > base["median_ending_cash"]
    assert better["prob_negative"] <= base["prob_negative"]


def test_bootstrap_invalid_inputs():
    with pytest.raises(ValueError):
        moving_block_bootstrap([1, 2], 100, 6, block=3)
    with pytest.raises(ValueError):
        moving_block_bootstrap([1, 2, 3], 100, 0)
    with pytest.raises(ValueError):
        moving_block_bootstrap([1, float("nan"), 3], 100, 2)
