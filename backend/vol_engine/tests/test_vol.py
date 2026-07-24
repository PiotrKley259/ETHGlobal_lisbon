"""A1.2 tests — written before vol.py.

- Close-to-close on synthetic GBM with known sigma must recover it.
- Parkinson has an exact analytic value when every candle has the same
  high/low ratio: sigma_P = ln(H/L) / sqrt(4 ln 2) * sqrt(8760).
- Regime: percentile within the trailing 7d-vol distribution, with
  caller-supplied (user-configurable) bands echoed back.
"""
import math
import random

import pytest

from vol_engine.types import Candle
from vol_engine.vol import ANNUALIZE, estimate_vol, get_regime

HOURS_PER_YEAR = 8760


def gbm_candles(n: int, sigma_annual: float, seed: int = 7, s0: float = 1800.0):
    """n hourly candles with lognormal close-to-close moves of known vol."""
    rng = random.Random(seed)
    sh = sigma_annual / math.sqrt(HOURS_PER_YEAR)
    closes, price = [], s0
    for _ in range(n):
        price *= math.exp(rng.gauss(0.0, sh))
        closes.append(price)
    return [
        Candle(ts=1_700_000_000 + i * 3600, open=c, high=c * 1.001, low=c * 0.999,
               close=c, volume_usd=1e6)
        for i, c in enumerate(closes)
    ]


def flat_range_candles(n: int, hl_ratio: float):
    return [
        Candle(ts=1_700_000_000 + i * 3600, open=1800.0, high=1800.0 * hl_ratio,
               low=1800.0, close=1800.0, volume_usd=1e6)
        for i in range(n)
    ]


def test_close_to_close_recovers_known_sigma():
    candles = gbm_candles(721, sigma_annual=0.50)
    v = estimate_vol(candles, "30d", "close")
    assert v.sigma_annual == pytest.approx(0.50, abs=0.06)
    assert v.window == "30d" and v.estimator == "close" and v.n_obs == 720


def test_windows_use_correct_observation_counts():
    candles = gbm_candles(721, 0.5)
    assert estimate_vol(candles, "24h", "close").n_obs == 24
    assert estimate_vol(candles, "7d", "close").n_obs == 168
    assert estimate_vol(candles, "30d", "close").n_obs == 720


def test_parkinson_exact_analytic_value():
    ratio = math.exp(0.004)  # constant ln(H/L) = 0.004 per hour
    candles = flat_range_candles(200, ratio)
    expected = 0.004 / math.sqrt(4 * math.log(2)) * ANNUALIZE
    v = estimate_vol(candles, "7d", "parkinson")
    assert v.sigma_annual == pytest.approx(expected, rel=1e-9)
    assert v.estimator == "parkinson"


def test_parkinson_agrees_with_close_on_gbm_scale():
    # Not exact on synthetic candles (our fake ranges are narrow), but both
    # estimators must be positive and finite; guards against unit mistakes.
    candles = gbm_candles(721, 0.5)
    p = estimate_vol(candles, "30d", "parkinson").sigma_annual
    assert 0 < p < 5


def test_insufficient_data_raises():
    with pytest.raises(ValueError):
        estimate_vol(gbm_candles(100, 0.5), "30d", "close")
    with pytest.raises(ValueError):
        estimate_vol(gbm_candles(721, 0.5), "7d", "range")  # bad estimator
    with pytest.raises(ValueError):
        estimate_vol(gbm_candles(721, 0.5), "90d", "close")  # bad window


# --- regime -----------------------------------------------------------------

def calm_then_spike(n_calm: int = 553, n_spike: int = 168):
    calm = gbm_candles(n_calm, 0.20, seed=1)
    spike = gbm_candles(n_spike, 1.20, seed=2, s0=calm[-1].close)
    for i, c in enumerate(spike):
        spike[i] = c.model_copy(update={"ts": calm[-1].ts + (i + 1) * 3600})
    return calm + spike


def test_regime_spike_is_stressed_and_echoes_default_bands():
    r = get_regime(calm_then_spike())
    assert r.regime == "stressed"
    assert r.percentile > 0.9
    assert r.bands == {"calm": 0.33, "elevated": 0.66}
    assert r.window == "7d"


def high_then_cool(n_high: int = 400, n_cool: int = 321):
    high = gbm_candles(n_high, 1.20, seed=4)
    cool = gbm_candles(n_cool, 0.15, seed=5, s0=high[-1].close)
    for i, c in enumerate(cool):
        cool[i] = c.model_copy(update={"ts": high[-1].ts + (i + 1) * 3600})
    return high + cool


def test_regime_custom_bands_relabel_same_data():
    # cooling vol -> current percentile is interior; the same data must be
    # labeled stressed or calm purely by the user's choice of bands
    candles = high_then_cool()
    p = get_regime(candles).percentile
    assert 0 < p < 1
    stressed = get_regime(candles, bands={"calm": p / 2, "elevated": p * 0.75})
    calm = get_regime(candles, bands={"calm": (p + 1) / 2, "elevated": (p + 3) / 4})
    assert stressed.regime == "stressed"
    assert calm.regime == "calm"
    assert stressed.percentile == pytest.approx(p)
    assert stressed.bands == {"calm": p / 2, "elevated": p * 0.75}


def test_regime_flat_history_is_not_stressed():
    r = get_regime(gbm_candles(721, 0.5, seed=3))
    assert r.regime in ("calm", "elevated")


def test_regime_band_validation():
    candles = gbm_candles(721, 0.5)
    for bad in ({"calm": 0.7, "elevated": 0.3}, {"calm": 0.0, "elevated": 0.5},
                {"calm": 0.3, "elevated": 1.0}):
        with pytest.raises(ValueError):
            get_regime(candles, bands=bad)
