"""A1.4 tests: the facade produces CONTRACTS §1 shapes offline, end to end
from fixtures — this is the whole engine wired together without network.
"""
import pytest

import config
from graph import subgraph
from vol_engine import api


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    subgraph.clear_cache()


def test_price_option_full_quote_shape():
    q = api.price_option(K=1770.0, T_days=7.0, type="put")
    assert q["price"] > 0
    assert q["qty"] == 1.0
    assert q["inputs"]["S"] == pytest.approx(1858.67, abs=0.5)
    assert q["inputs"]["sigma_source"] == "curve"  # term-structure sourced
    assert 0.1 < q["inputs"]["sigma"] < 2.0
    assert -1 < q["greeks"]["delta"] < 0  # put
    assert set(q["greeks"]) == {"delta", "gamma", "vega", "theta", "rho"}


def test_price_option_qty_scales_price_not_greeks():
    q1 = api.price_option(K=1860.0, T_days=7.0, type="call", qty=1.0)
    q3 = api.price_option(K=1860.0, T_days=7.0, type="call", qty=3.0)
    assert q3["price"] == pytest.approx(3 * q1["price"])
    assert q3["greeks"] == q1["greeks"]  # per 1 unit by contract


def test_pricing_sigma_comes_from_the_curve():
    # at the tenor points the curve reproduces the window estimates exactly
    for tenor, window in ((1.0, "24h"), (7.0, "7d"), (30.0, "30d")):
        q = api.price_option(1860, tenor, "call")
        assert q["inputs"]["sigma"] == pytest.approx(
            api.estimate_vol(window)["sigma_annual"], abs=1e-12)
    # between tenors: interpolated, strictly inside the bracket (contango data)
    s1 = api.estimate_vol("24h")["sigma_annual"]
    s7 = api.estimate_vol("7d")["sigma_annual"]
    mid = api.price_option(1860, 3.0, "call")["inputs"]["sigma"]
    assert min(s1, s7) < mid < max(s1, s7)
    # clamped flat beyond the observed range
    assert api.price_option(1860, 60.0, "call")["inputs"]["sigma"] == \
        pytest.approx(api.estimate_vol("30d")["sigma_annual"], abs=1e-12)


def test_vol_curve_shape_from_fixtures():
    curve = api.get_vol_curve()
    assert [p["tenor_days"] for p in curve["points"]] == [1.0, 7.0, 30.0]
    assert curve["shape"] == "contango"  # 33% -> 53% in the captured data


def test_wbtc_quote_uses_wbtc_market_data():
    q = api.price_option(K=60_000, T_days=7.0, type="put", asset="WBTC")
    assert q["inputs"]["S"] == pytest.approx(63_917, rel=0.01)
    assert q["price"] > 0
    assert 0.05 < q["inputs"]["sigma"] < 2.0
    # WBTC's curve is its own, not ETH's
    eth7 = api.estimate_vol("7d")["sigma_annual"]
    wbtc7 = api.estimate_vol("7d", asset="WBTC")["sigma_annual"]
    assert eth7 != pytest.approx(wbtc7, abs=1e-6)
    assert api.get_vol_curve(asset="WBTC")["shape"] in (
        "contango", "backwardation", "flat")


def test_price_strategy_from_named_template():
    legs = api.resolve_named("short_straddle", S=api.get_spot()["price"], T_days=7.0)
    r = api.price_strategy(legs)
    assert r["net_cost"] < 0  # credit
    assert r["max_loss"] is None  # unbounded
    assert r["max_profit"] == pytest.approx(-r["net_cost"], abs=1e-6)
    assert len(r["payoff"]["prices"]) == 121


def test_vol_and_regime_from_fixtures():
    vols = {w: api.estimate_vol(w)["sigma_annual"] for w in ("24h", "7d", "30d")}
    assert vols["24h"] == pytest.approx(0.333, abs=0.02)
    assert vols["30d"] == pytest.approx(0.526, abs=0.02)
    regime = api.get_regime()
    assert regime["regime"] in ("calm", "elevated", "stressed")
    assert regime["bands"] == {"calm": 0.33, "elevated": 0.66}


def test_mcp_server_registers_all_contract_tools():
    from vol_engine import server
    import asyncio

    tools = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"get_price_history", "get_spot", "estimate_vol", "get_regime",
            "get_risk_free_rate", "price_option", "price_strategy",
            "list_strategies", "resolve_strategy"} <= tools
