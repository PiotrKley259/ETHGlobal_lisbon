"""Realized-vol estimators + regime classification (PLAN task A1.2).

Pure math over Candle lists — no I/O, no network. Hourly data, annualized
via sqrt(8760). Windows per CONTRACTS §1: 24h / 7d / 30d.
"""
from __future__ import annotations

import math
import statistics

from .types import Candle, Regime, Vol

ANNUALIZE = math.sqrt(8760.0)
WINDOW_HOURS = {"24h": 24, "7d": 168, "30d": 720}
DEFAULT_BANDS = {"calm": 0.33, "elevated": 0.66}
_PARKINSON_K = 1.0 / (4.0 * math.log(2.0))


def _close_to_close(closes: list[float]) -> float:
    rets = [math.log(closes[i + 1] / closes[i]) for i in range(len(closes) - 1)]
    return statistics.stdev(rets) * ANNUALIZE


def _parkinson(candles: list[Candle]) -> float:
    sq = [math.log(c.high / c.low) ** 2 for c in candles]
    return math.sqrt(_PARKINSON_K * (sum(sq) / len(sq))) * ANNUALIZE


def estimate_vol(candles: list[Candle], window: str, estimator: str = "close") -> Vol:
    """Annualized realized vol over the trailing `window` of hourly candles.

    close-to-close needs hours+1 candles (hours returns); Parkinson needs
    hours candles (one range per candle).
    """
    if window not in WINDOW_HOURS:
        raise ValueError(f"window must be one of {sorted(WINDOW_HOURS)}, got {window!r}")
    if estimator not in ("close", "parkinson"):
        raise ValueError(f"estimator must be 'close' or 'parkinson', got {estimator!r}")
    hours = WINDOW_HOURS[window]

    if estimator == "close":
        if len(candles) < hours + 1:
            raise ValueError(f"need {hours + 1} candles for {window} close vol, got {len(candles)}")
        sigma = _close_to_close([c.close for c in candles[-(hours + 1):]])
        n_obs = hours
    else:
        if len(candles) < hours:
            raise ValueError(f"need {hours} candles for {window} parkinson vol, got {len(candles)}")
        sigma = _parkinson(candles[-hours:])
        n_obs = hours

    return Vol(sigma_annual=sigma, window=window, estimator=estimator, n_obs=n_obs)


def _validate_bands(bands: dict[str, float]) -> dict[str, float]:
    calm, elevated = bands.get("calm"), bands.get("elevated")
    if calm is None or elevated is None or not (0.0 < calm < elevated < 1.0):
        raise ValueError(f"bands need 0 < calm < elevated < 1, got {bands}")
    return {"calm": float(calm), "elevated": float(elevated)}


def get_regime(candles: list[Candle], bands: dict[str, float] | None = None) -> Regime:
    """Percentile of the current 7d vol within its trailing distribution.

    A rolling 7d close-to-close vol is computed at every hour endpoint the
    data allows (up to 30d back); the regime is where *now* sits in that
    distribution, labeled with caller-supplied bands (user preference —
    the engine never stores them, per CONTRACTS §1).
    """
    checked = _validate_bands(bands if bands is not None else DEFAULT_BANDS)
    w = WINDOW_HOURS["7d"]
    closes = [c.close for c in candles][-(WINDOW_HOURS["30d"] + 1):]
    if len(closes) < w + 2:
        raise ValueError(f"need at least {w + 2} candles for regime, got {len(closes)}")

    rolling = [_close_to_close(closes[i - w:i + 1]) for i in range(w, len(closes))]
    current = rolling[-1]
    percentile = sum(1 for v in rolling if v <= current) / len(rolling)

    if percentile < checked["calm"]:
        label = "calm"
    elif percentile < checked["elevated"]:
        label = "elevated"
    else:
        label = "stressed"

    return Regime(regime=label, percentile=percentile, window="7d", bands=checked)


def select_sigma_window(T_days: float) -> str:
    """Baseline tenor-matching rule: which realized-vol window prices a given
    horizon. (Stage 4 replaces this with sigma_for_horizon interpolation.)"""
    if T_days <= 2.0:
        return "24h"
    if T_days <= 14.0:
        return "7d"
    return "30d"
