"""A1.3 tests — written before strategies.py.

Payoff-shape truths that don't depend on the vol input:
- butterfly = tent (peak at K_mid, wings lose exactly the debit)
- bull call spread = capped ramp
- straddle = V with breakevens at K -/+ total premium
- long + short of the identical leg cancels to nothing
- short straddle: unbounded loss (null), max profit = credit
"""
import pytest

from vol_engine.strategies import LIBRARY, list_strategies, price_strategy, resolve_named

S, R, SIGMA, T = 1858.67, 0.0382, 0.37, 7.0


def leg(opt_type, side, K, qty=1.0, T_days=T):
    return {"type": opt_type, "side": side, "K": K, "T_days": T_days, "qty": qty}


def pnl_at(result, price):
    """Interpolate the payoff curve at a terminal price."""
    xs, ys = result["payoff"]["prices"], result["payoff"]["pnl"]
    assert xs[0] <= price <= xs[-1], "price outside payoff grid"
    for i in range(len(xs) - 1):
        if xs[i] <= price <= xs[i + 1]:
            w = (price - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + w * (ys[i + 1] - ys[i])
    raise AssertionError


def test_library_has_eight_named_strategies():
    names = {s["name"] for s in list_strategies()}
    assert names == {
        "long_call", "long_put", "bull_call_spread", "bear_put_spread",
        "long_straddle", "long_strangle", "long_butterfly", "short_straddle",
    }
    assert all(s["view"] for s in list_strategies())


def test_butterfly_is_a_tent():
    lo, mid, hi = 1760.0, 1860.0, 1960.0
    r = price_strategy(
        [leg("call", "long", lo), leg("call", "short", mid, qty=2),
         leg("call", "long", hi)], S=S, r_cc=R, sigma=SIGMA)
    debit = r["net_cost"]
    assert debit > 0  # butterflies cost money
    # wings lose exactly the debit; peak gains (mid - lo) - debit
    assert pnl_at(r, lo - 50) == pytest.approx(-debit, abs=1e-6)
    assert pnl_at(r, hi + 50) == pytest.approx(-debit, abs=1e-6)
    # curve read at the peak is grid-interpolated (display artifact) — coarse;
    # max_profit is evaluated exactly at the kink — tight
    assert pnl_at(r, mid) == pytest.approx((mid - lo) - debit, rel=0.05)
    assert r["max_profit"] == pytest.approx((mid - lo) - debit, abs=1e-6)
    assert r["max_loss"] == pytest.approx(-debit, abs=1e-6)


def test_bull_call_spread_capped_ramp():
    k1, k2 = 1860.0, 1960.0
    r = price_strategy([leg("call", "long", k1), leg("call", "short", k2)],
                       S=S, r_cc=R, sigma=SIGMA)
    debit = r["net_cost"]
    assert 0 < debit < (k2 - k1)
    assert r["max_profit"] == pytest.approx((k2 - k1) - debit, abs=1e-6)
    assert r["max_loss"] == pytest.approx(-debit, abs=1e-6)
    assert pnl_at(r, k1 - 100) == pytest.approx(-debit, abs=1e-6)
    assert pnl_at(r, k2 + 100) == pytest.approx((k2 - k1) - debit, abs=1e-6)


def test_long_straddle_breakevens():
    K = 1860.0
    r = price_strategy([leg("call", "long", K), leg("put", "long", K)],
                       S=S, r_cc=R, sigma=SIGMA)
    prem = r["net_cost"]
    assert prem > 0
    assert len(r["breakevens"]) == 2
    lo, hi = sorted(r["breakevens"])
    assert lo == pytest.approx(K - prem, rel=0.01)
    assert hi == pytest.approx(K + prem, rel=0.01)
    assert r["max_loss"] == pytest.approx(-prem, abs=1e-6)
    assert r["max_profit"] is None  # unbounded upside


def test_short_straddle_is_mirror():
    K = 1860.0
    long = price_strategy([leg("call", "long", K), leg("put", "long", K)],
                          S=S, r_cc=R, sigma=SIGMA)
    short = price_strategy([leg("call", "short", K), leg("put", "short", K)],
                           S=S, r_cc=R, sigma=SIGMA)
    assert short["net_cost"] == pytest.approx(-long["net_cost"], abs=1e-9)
    assert short["max_profit"] == pytest.approx(long["net_cost"], abs=1e-6)
    assert short["max_loss"] is None  # unbounded loss
    assert short["net_greeks"]["vega"] == pytest.approx(
        -long["net_greeks"]["vega"], abs=1e-9)


def test_identical_long_short_cancels():
    r = price_strategy([leg("call", "long", 1860.0), leg("call", "short", 1860.0)],
                       S=S, r_cc=R, sigma=SIGMA)
    assert r["net_cost"] == pytest.approx(0, abs=1e-9)
    for v in r["net_greeks"].values():
        assert v == pytest.approx(0, abs=1e-9)
    assert all(abs(p) < 1e-9 for p in r["payoff"]["pnl"])


def test_per_leg_quotes_and_grid_shape():
    r = price_strategy([leg("put", "long", 1770.0)], S=S, r_cc=R, sigma=SIGMA)
    assert len(r["legs"]) == 1
    assert r["legs"][0]["price"] > 0
    assert r["legs"][0]["inputs"]["K"] == 1770.0
    assert len(r["payoff"]["prices"]) == 121
    assert r["payoff"]["prices"] == sorted(r["payoff"]["prices"])


def test_resolve_named_matches_library():
    legs = resolve_named("long_strangle", S=1858.67, T_days=7.0)
    assert len(legs) == len(LIBRARY["long_strangle"]["template"])
    types = {(l["type"], l["side"]) for l in legs}
    assert types == {("call", "long"), ("put", "long")}
    ks = sorted(l["K"] for l in legs)
    assert ks[0] < 1858.67 < ks[1]  # strangle straddles spot
    with pytest.raises(ValueError):
        resolve_named("iron_condor", S=S, T_days=7.0)


def test_invalid_legs_raise():
    with pytest.raises(ValueError):
        price_strategy([], S=S, r_cc=R, sigma=SIGMA)
    with pytest.raises(ValueError):
        price_strategy([leg("call", "hold", 1860.0)], S=S, r_cc=R, sigma=SIGMA)
