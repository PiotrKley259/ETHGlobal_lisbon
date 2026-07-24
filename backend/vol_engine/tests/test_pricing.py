"""A1.1 tests — written before pricing.py per PLAN. Known-value references:

- Hull, "Options, Futures and Other Derivatives": S=42, K=40, r=10%, sigma=20%,
  T=0.5y -> call 4.759, put 0.808.
- Standard reference set S=K=100, r=5%, sigma=20%, T=1y:
  call 10.4506, put 5.5735, delta_c 0.6368, gamma 0.018762, vega 37.524,
  theta_c -6.4140/yr, rho_c 53.2325.

Conventions (CONTRACTS §1): T in days / 365; r continuously compounded;
vega = dP/d(sigma) per 1.00 of vol; rho = dP/dr per 1.00 of rate;
theta = per calendar day (annual/365).
"""
import math

import pytest

from vol_engine.pricing import bs_greeks, bs_price

Y = 365.0  # days per year


# --- known values -----------------------------------------------------------

def test_hull_example():
    assert bs_price(42, 40, 0.5 * Y, 0.2, 0.10, "call") == pytest.approx(4.759, abs=1e-3)
    assert bs_price(42, 40, 0.5 * Y, 0.2, 0.10, "put") == pytest.approx(0.808, abs=1e-3)


def test_reference_atm_1y_prices():
    assert bs_price(100, 100, Y, 0.2, 0.05, "call") == pytest.approx(10.4506, abs=1e-3)
    assert bs_price(100, 100, Y, 0.2, 0.05, "put") == pytest.approx(5.5735, abs=1e-3)


def test_reference_atm_1y_greeks():
    g = bs_greeks(100, 100, Y, 0.2, 0.05, "call")
    assert g.delta == pytest.approx(0.6368, abs=1e-3)
    assert g.gamma == pytest.approx(0.018762, abs=1e-5)
    assert g.vega == pytest.approx(37.524, abs=1e-2)
    assert g.theta == pytest.approx(-6.4140 / Y, abs=1e-4)  # per day
    assert g.rho == pytest.approx(53.2325, abs=1e-2)


def test_put_greeks_relations():
    c, p = (bs_greeks(100, 100, Y, 0.2, 0.05, t) for t in ("call", "put"))
    assert p.delta == pytest.approx(c.delta - 1, abs=1e-9)  # delta parity
    assert p.gamma == pytest.approx(c.gamma, abs=1e-12)
    assert p.vega == pytest.approx(c.vega, abs=1e-9)


# --- structural properties --------------------------------------------------

def test_put_call_parity_grid():
    r, sigma = 0.04, 0.5
    for S in (1500.0, 1858.67, 2200.0):
        for K in (1600.0, 1860.0, 2100.0):
            for T in (1.0, 7.0, 30.0):
                c = bs_price(S, K, T, sigma, r, "call")
                p = bs_price(S, K, T, sigma, r, "put")
                assert c - p == pytest.approx(
                    S - K * math.exp(-r * T / Y), abs=1e-8
                )


def test_limits():
    # deep ITM call ~ discounted forward intrinsic; deep OTM ~ 0
    assert bs_price(1860, 100, 7, 0.5, 0.04, "call") == pytest.approx(
        1860 - 100 * math.exp(-0.04 * 7 / Y), abs=1e-6
    )
    assert bs_price(1860, 10000, 7, 0.5, 0.04, "call") == pytest.approx(0, abs=1e-6)
    assert bs_price(1860, 100, 7, 0.5, 0.04, "put") == pytest.approx(0, abs=1e-6)


def test_monotone_in_sigma():
    prices = [bs_price(1860, 1860, 7, s, 0.04, "call") for s in (0.2, 0.4, 0.6, 0.8)]
    assert prices == sorted(prices)
    assert prices[0] > 0


def test_delta_bounds_and_signs():
    for K in (1500, 1860, 2300):
        g_c = bs_greeks(1860, K, 7, 0.5, 0.04, "call")
        g_p = bs_greeks(1860, K, 7, 0.5, 0.04, "put")
        assert 0 < g_c.delta < 1
        assert -1 < g_p.delta < 0
        assert g_c.gamma > 0 and g_c.vega > 0
        assert g_c.theta < 0  # long options bleed


def test_expiry_is_intrinsic():
    assert bs_price(1900, 1860, 0, 0.5, 0.04, "call") == pytest.approx(40)
    assert bs_price(1800, 1860, 0, 0.5, 0.04, "call") == 0
    assert bs_price(1800, 1860, 0, 0.5, 0.04, "put") == pytest.approx(60)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        bs_price(-1, 100, 7, 0.2, 0.04, "call")
    with pytest.raises(ValueError):
        bs_price(100, 0, 7, 0.2, 0.04, "call")
    with pytest.raises(ValueError):
        bs_price(100, 100, 7, 0.2, 0.04, "swaption")  # type: ignore[arg-type]
