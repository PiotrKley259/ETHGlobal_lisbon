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


# --- multi-asset (WBTC pool is inverted: OHLC is WBTC-per-USDC) --------------

def test_wbtc_history_inverted_to_usd():
    h = subgraph.get_price_history(hours=744, asset="WBTC")
    assert h["asset"] == "WBTC" and len(h["candles"]) == 744
    last = h["candles"][-1]
    assert 10_000 < last["close"] < 1_000_000  # USD scale, not 0.0000156
    for c in h["candles"]:
        assert c["high"] >= c["low"]  # inversion must swap high/low


def test_wbtc_spot_reads_token1_price():
    s = subgraph.get_spot(asset="WBTC")
    assert s["asset"] == "WBTC"
    assert s["price"] == pytest.approx(63_917, rel=0.01)


def test_eth_still_default_and_uninverted():
    assert subgraph.get_spot()["asset"] == "ETH"
    assert subgraph.get_spot()["price"] == pytest.approx(1858.67, abs=0.5)


def test_unknown_asset_raises():
    with pytest.raises(ValueError, match="unknown asset"):
        subgraph.get_spot(asset="DOGE")


def test_weth_cross_assets_priced_in_usd():
    # LINK/UNI/AAVE candles are WETH-quoted and crossed with ETH/USD
    eth_spot = subgraph.get_spot()["price"]
    for asset, lo, hi in (("LINK", 2, 100), ("UNI", 0.5, 50), ("AAVE", 20, 1000)):
        s = subgraph.get_spot(asset=asset)
        assert lo < s["price"] < hi, f"{asset} spot {s['price']} not USD-scale"
        h = subgraph.get_price_history(hours=744, asset=asset)
        closes = [c["close"] for c in h["candles"]]
        assert len(closes) > 550  # sparse hours dropped; dt-normalized vol handles gaps
        assert all(lo / 4 < c < hi * 4 for c in closes)
        ts = [c["ts"] for c in h["candles"]]
        assert ts == sorted(ts)
        # spot must equal (token in WETH) x (ETH in USD) from the fixtures
        raw = subgraph._load_fixture(
            f"spot{subgraph._asset_cfg(asset)['fixture_suffix']}.json")
        assert s["price"] == pytest.approx(
            float(raw["pool"]["token1Price"]) * eth_spot, rel=1e-9)


def test_cross_candle_math_synthetic(monkeypatch):
    # token/WETH raw candle (token0Price = token-per-WETH = 140) with ETH at
    # $2,000 must produce a $14.29 close: 1/140 * 2000
    raw = {"periodStartUnix": 1_700_000_000, "open": "140", "high": "150",
           "low": "130", "close": "140", "volumeUSD": "9"}
    in_weth = subgraph._to_usd_candle(raw, invert=True)
    usd_close = in_weth["close"] * 2000.0
    assert usd_close == pytest.approx(2000.0 / 140.0)
    assert in_weth["high"] == pytest.approx(1 / 130)  # 1/low
    assert in_weth["low"] == pytest.approx(1 / 150)   # 1/high


def test_inversion_math_exact():
    raw = {"periodStartUnix": 1, "open": "0.00002", "high": "0.00004",
           "low": "0.00001", "close": "0.000025", "volumeUSD": "5"}
    c = subgraph._to_usd_candle(raw, invert=True)
    assert c["open"] == pytest.approx(50_000)
    assert c["high"] == pytest.approx(100_000)   # 1/low
    assert c["low"] == pytest.approx(25_000)     # 1/high
    assert c["close"] == pytest.approx(40_000)
    assert subgraph._to_usd_candle(raw, invert=False)["open"] == pytest.approx(0.00002)


# --- fallback chain (online mode, each network layer faked) -----------------

FRED_CSV = "DATE,DGS1MO\n2026-07-22,4.35\n2026-07-23,4.40\n2026-07-24,.\n"


def test_fred_csv_parser_skips_missing_observations():
    assert subgraph.parse_fred_csv(FRED_CSV) == pytest.approx(0.0440)
    with pytest.raises(ValueError):
        subgraph.parse_fred_csv("DATE,DGS1MO\n2026-07-24,.\n")


def test_fallback_level_1_when_aave_down_fred_up(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(subgraph, "_gateway",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("gw down")))

    class FakeResp:
        text = FRED_CSV
        def raise_for_status(self): pass

    monkeypatch.setattr(subgraph.httpx, "get", lambda *a, **k: FakeResp())
    r = subgraph.get_risk_free_rate()
    assert r["fallback_level"] == 1
    assert r["source"] == "fred-dgs1mo-cached"
    assert r["rate_cc"] == pytest.approx(math.log(1.044), abs=1e-9)


def test_fallback_level_2_when_everything_down(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(subgraph, "_gateway",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("gw down")))
    monkeypatch.setattr(subgraph.httpx, "get",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fred down")))
    r = subgraph.get_risk_free_rate()
    assert r["fallback_level"] == 2 and r["source"] == "constant"


def test_fallback_level_0_when_aave_up(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(subgraph, "_gateway", lambda *a: {"reserves": [{
        "symbol": "USDC", "variableBorrowRate": "38943706239048578172608273",
        "lastUpdateTimestamp": 1784924327}]})
    r = subgraph.get_risk_free_rate()
    assert r["fallback_level"] == 0
    assert r["rate_cc"] == pytest.approx(0.038204, abs=1e-4)
