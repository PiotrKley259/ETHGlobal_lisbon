"""I1.1 tests: tool dispatch against the offline engine — no Anthropic calls.
The loop itself is exercised by the live smoke in I1.2.
"""
import pytest

import config
from agent import tools
from graph import subgraph


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    subgraph.clear_cache()


@pytest.fixture()
def state():
    return tools.default_state()


def test_every_declared_tool_dispatches(state):
    args = {
        "get_spot": {},
        "estimate_vol": {"window": "7d"},
        "get_regime": {},
        "get_risk_free_rate": {},
        "get_vol_curve": {},
        "price_option": {"K": 1770.0, "T_days": 7.0, "type": "put"},
        "price_strategy": {"legs": [
            {"type": "call", "side": "long", "K": 1860.0, "T_days": 7.0, "qty": 1}]},
        "list_strategies": {},
        "resolve_strategy": {"name": "short_straddle", "T_days": 7.0},
        "set_regime_bands": {"calm": 0.2, "elevated": 0.8},
    }
    chain_tools = {"mint_option", "log_trade", "arm_settlement"}  # test_chain.py
    declared = {t["name"] for t in tools.TOOLS}
    assert declared == set(args) | chain_tools
    for name in set(args):
        result = tools.dispatch(name, args[name], state)
        assert isinstance(result, dict)
        assert tools.summarize(name, result)  # chip text never empty


def test_quote_lands_in_state_and_panel(state):
    tools.dispatch("price_option", {"K": 1770.0, "T_days": 7.0, "type": "put"}, state)
    panel = tools.build_panel(state)
    assert panel["quote"]["inputs"]["K"] == 1770.0
    assert panel["strategy"] is None
    # pricing a strategy replaces the quote (panel shows the latest thing)
    tools.dispatch("price_strategy", {"legs": [
        {"type": "put", "side": "long", "K": 1770.0, "T_days": 7.0, "qty": 1}]}, state)
    panel = tools.build_panel(state)
    assert panel["quote"] is None and panel["strategy"] is not None
    assert len(panel["vols"]) == 3
    assert panel["regime"]["bands"] == state["settings"]["regime_bands"]


def test_asset_flows_into_state_and_panel(state):
    tools.dispatch("get_spot", {"asset": "WBTC"}, state)
    assert state["asset"] == "WBTC"
    panel = tools.build_panel(state)
    assert panel["asset"] == "WBTC"
    assert panel["spot"]["price"] > 10_000  # BTC scale
    # sticky: next call without asset stays on WBTC; explicit ETH switches back
    q = tools.dispatch("price_option", {"K": 60_000, "T_days": 7.0, "type": "put"}, state)
    assert q["inputs"]["S"] > 10_000
    tools.dispatch("get_spot", {"asset": "ETH"}, state)
    assert tools.build_panel(state)["spot"]["price"] < 10_000


def test_set_regime_bands_flows_into_regime(state):
    before = tools.dispatch("get_regime", {}, state)
    tools.dispatch("set_regime_bands", {"calm": 0.01, "elevated": 0.02}, state)
    after = tools.dispatch("get_regime", {}, state)
    assert after["bands"] == {"calm": 0.01, "elevated": 0.02}
    assert after["percentile"] == pytest.approx(before["percentile"])


def test_set_regime_bands_validates(state):
    with pytest.raises(ValueError):
        tools.dispatch("set_regime_bands", {"calm": 0.8, "elevated": 0.2}, state)
    with pytest.raises(ValueError):
        tools.dispatch("set_regime_bands", {"calm": 0.0, "elevated": 0.5}, state)


def test_unknown_tool_raises(state):
    with pytest.raises(ValueError):
        tools.dispatch("teleport_funds", {}, state)
