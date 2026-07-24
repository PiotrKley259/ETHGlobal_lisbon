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
    assert q["inputs"]["sigma_source"] == "7d"  # tenor-matched window
    assert 0.1 < q["inputs"]["sigma"] < 2.0
    assert -1 < q["greeks"]["delta"] < 0  # put
    assert set(q["greeks"]) == {"delta", "gamma", "vega", "theta", "rho"}


def test_price_option_qty_scales_price_not_greeks():
    q1 = api.price_option(K=1860.0, T_days=7.0, type="call", qty=1.0)
    q3 = api.price_option(K=1860.0, T_days=7.0, type="call", qty=3.0)
    assert q3["price"] == pytest.approx(3 * q1["price"])
    assert q3["greeks"] == q1["greeks"]  # per 1 unit by contract


def test_tenor_matching_selects_windows():
    assert api.price_option(1860, 1.0, "call")["inputs"]["sigma_source"] == "24h"
    assert api.price_option(1860, 7.0, "call")["inputs"]["sigma_source"] == "7d"
    assert api.price_option(1860, 30.0, "call")["inputs"]["sigma_source"] == "30d"


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
