"""A2 tests — offline-first: everything here runs with zero network, exactly
as the engine does under OFFLINE_MODE=1. Ray/cc conversions are pinned to the
live Aave value verified 2026-07-24 (CONTRACTS §6).
"""
import math

import pytest

import config
from graph import subgraph


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    subgraph.clear_cache()


def test_price_history_shape_and_order():
    h = subgraph.get_price_history(hours=744)
    assert h["pool"] == config.ETH_USDC_POOL
    assert len(h["candles"]) == 744
    ts = [c["ts"] for c in h["candles"]]
    assert ts == sorted(ts)  # ascending per CONTRACTS §1
    last = h["candles"][-1]
    assert isinstance(last["close"], float) and 100 < last["close"] < 100_000
    assert last["volume_usd"] >= 0


def test_price_history_smaller_window_takes_most_recent():
    full = subgraph.get_price_history(hours=744)
    sub = subgraph.get_price_history(hours=24)
    assert len(sub["candles"]) == 24
    assert sub["candles"][-1] == full["candles"][-1]


def test_spot_matches_fixture():
    s = subgraph.get_spot()
    assert s["source"] == "uniswap-v3-subgraph"
    assert s["price"] == pytest.approx(1858.67, abs=0.5)
    assert isinstance(s["ts"], int) and s["ts"] > 1_700_000_000


def test_caching_prevents_refetch(monkeypatch):
    calls = {"n": 0}
    original = subgraph._load_fixture

    def counting(name):
        calls["n"] += 1
        return original(name)

    monkeypatch.setattr(subgraph, "_load_fixture", counting)
    subgraph.get_spot()
    subgraph.get_spot()
    subgraph.get_spot()
    assert calls["n"] == 1  # served from cache after first load


def test_risk_free_rate_offline_falls_back_to_constant():
    r = subgraph.get_risk_free_rate()
    assert r["source"] == "constant"
    assert r["fallback_level"] == 2
    assert r["rate_cc"] == pytest.approx(math.log(1 + config.RISK_FREE_RATE_CONSTANT))
    assert r["observed_at"] > 0


def test_ray_conversion_pinned_to_live_aave_value():
    # variableBorrowRate captured live 2026-07-24 (CONTRACTS §6)
    apr = subgraph.ray_to_apr("38943706239048578172608273")
    assert apr == pytest.approx(0.0389437, abs=1e-6)
    assert subgraph.apr_to_cc(apr) == pytest.approx(0.038204, abs=1e-4)


def test_apr_to_cc_known_value():
    assert subgraph.apr_to_cc(0.05) == pytest.approx(math.log(1.05), abs=1e-12)
    assert subgraph.apr_to_cc(0.0) == 0.0
