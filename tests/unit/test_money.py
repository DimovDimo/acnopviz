import pytest

from acnopviz.money import dollars, to_cents


def test_to_cents_half_up():
    assert to_cents("1.005") == 101
    assert to_cents(2.675) == 268
    assert to_cents("0") == 0


def test_dollars_roundtrip():
    assert dollars(123456) == 1234.56


def test_non_finite_rejected():
    with pytest.raises(ValueError):
        to_cents("nan")
    with pytest.raises(ValueError):
        to_cents("inf")
