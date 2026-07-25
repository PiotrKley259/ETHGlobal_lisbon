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


MIN_COVERAGE = 0.55  # window must be at least this fraction covered by data


def _returns_with_dt(candles: list[Candle]) -> list[tuple[float, float]]:
    out = []
    for a, b in zip(candles, candles[1:]):
        dt_h = (b.ts - a.ts) / 3600.0
        if dt_h > 0:
            out.append((math.log(b.close / a.close), dt_h))
    return out


def estimate_vol(candles: list[Candle], window: str, estimator: str = "close") -> Vol:
    """Annualized realized vol over the trailing time `window`.

    Candles are selected by TIMESTAMP (not count), and close-to-close vol is
    the irregular-sampling estimator sum(r_i^2)/sum(dt_i) — so sparse pools
    (missing no-trade hours, e.g. LINK) are handled correctly: a return that
    spans a 3h gap contributes 3h of time to the denominator. Contiguous
    hourly data reduces to the classic estimator.
    """
    if window not in WINDOW_HOURS:
        raise ValueError(f"window must be one of {sorted(WINDOW_HOURS)}, got {window!r}")
    if estimator not in ("close", "parkinson"):
        raise ValueError(f"estimator must be 'close' or 'parkinson', got {estimator!r}")
    hours = WINDOW_HOURS[window]
    if not candles:
        raise ValueError("no candles")
    end_ts = candles[-1].ts
    sel = [c for c in candles if c.ts >= end_ts - hours * 3600]
    span_h = (sel[-1].ts - sel[0].ts) / 3600.0 if len(sel) > 1 else 0.0
    if len(sel) < 13 or span_h < MIN_COVERAGE * hours:
        raise ValueError(
            f"insufficient data for {window} vol: {len(sel)} candles covering "
            f"{span_h:.0f}h of a {hours}h window")

    if estimator == "close":
        rets = _returns_with_dt(sel)
        var_hourly = sum(r * r for r, _ in rets) / sum(dt for _, dt in rets)
        sigma = math.sqrt(var_hourly) * ANNUALIZE
        n_obs = len(rets)
    else:
        sigma = _parkinson(sel)
        n_obs = len(sel)

    return Vol(
        sigma_annual=sigma,
        # the intuitive number: 1-sigma move over the window's own length
        # (e.g. 33% annualized -> ±1.7% over a day)
        sigma_period=sigma * math.sqrt(hours / 8760.0),
        window=window,
        estimator=estimator,
        n_obs=n_obs,
    )


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
