"""Engine facade (PLAN task A1.4): the one place cached market data meets the
pure math. Every function returns exactly the CONTRACTS §1 JSON shape; both
the MCP server (server.py) and the agent tools (agent/tools.py) call these.

Network policy: data arrives only via graph.subgraph's cached fetchers —
pricing itself never fetches (OFFLINE_MODE=1 therefore always works).
"""
from __future__ import annotations

import config
from graph import subgraph

from .curve import classify_shape, sigma_for_horizon
from .pricing import bs_greeks, bs_price
from .strategies import list_strategies as _list_strategies
from .strategies import price_strategy as _price_strategy
from .strategies import resolve_named
from .types import Candle
from .vol import estimate_vol as _estimate_vol
from .vol import get_regime as _get_regime

__all__ = [
    "get_price_history", "get_spot", "estimate_vol", "get_regime",
    "get_risk_free_rate", "get_vol_curve", "price_option", "price_strategy",
    "list_strategies", "resolve_named",
]

CURVE_TENORS = (("24h", 1.0), ("7d", 7.0), ("30d", 30.0))

get_price_history = subgraph.get_price_history
get_spot = subgraph.get_spot
get_risk_free_rate = subgraph.get_risk_free_rate
list_strategies = _list_strategies


# 31 days of hourly candles: the 30d close-to-close window needs 721 closes
# (720 returns), and the regime's rolling series wants headroom beyond that.
HISTORY_HOURS = 744


def _candles(asset: str = config.DEFAULT_ASSET) -> list[Candle]:
    return [
        Candle(**c)
        for c in subgraph.get_price_history(hours=HISTORY_HOURS, asset=asset)["candles"]
    ]


def estimate_vol(window: str, estimator: str = "close",
                 asset: str = config.DEFAULT_ASSET) -> dict:
    return _estimate_vol(_candles(asset), window, estimator).model_dump()


def get_regime(bands: dict[str, float] | None = None,
               asset: str = config.DEFAULT_ASSET) -> dict:
    return _get_regime(_candles(asset), bands).model_dump()


def _curve_points(candles: list[Candle]) -> list[tuple[float, float]]:
    return [
        (tenor, _estimate_vol(candles, window, "close").sigma_annual)
        for window, tenor in CURVE_TENORS
    ]


def get_vol_curve(asset: str = config.DEFAULT_ASSET) -> dict:
    """VolCurve per CONTRACTS §1: the three tenor points + the curve's shape.
    This curve is THE source of sigma for all pricing (sigma_for_horizon)."""
    points = _curve_points(_candles(asset))
    return {
        "points": [{"tenor_days": t, "sigma": s} for t, s in points],
        "shape": classify_shape(points),
    }


def _sigma_for(T_days: float, candles: list[Candle]) -> tuple[float, str]:
    """Single source of sigma for pricing: the fitted term-structure curve
    (variance-time interpolation, flat clamp outside [1d, 30d])."""
    return sigma_for_horizon(T_days, _curve_points(candles)), "curve"


def price_option(
    K: float, T_days: float, type: str, qty: float = 1.0,
    S: float | None = None, asset: str = config.DEFAULT_ASSET
) -> dict:
    """Quote per CONTRACTS §1. price is total for qty; Greeks are per 1 unit.
    S=None (the normal case) uses the latest cached spot for the asset."""
    spot = float(S) if S is not None else get_spot(asset)["price"]
    r_cc = get_risk_free_rate()["rate_cc"]
    sigma, window = _sigma_for(T_days, _candles(asset))
    unit = bs_price(spot, K, T_days, sigma, r_cc, type)
    greeks = bs_greeks(spot, K, T_days, sigma, r_cc, type)
    return {
        "price": unit * qty,
        "qty": qty,
        "inputs": {"S": spot, "K": K, "T_days": T_days, "r_cc": r_cc,
                   "sigma": sigma, "sigma_source": window},
        "greeks": greeks.model_dump(),
    }


def price_strategy(legs: list[dict], asset: str = config.DEFAULT_ASSET) -> dict:
    """StrategyQuote per CONTRACTS §1; per-leg sigma from the asset's curve."""
    spot = get_spot(asset)["price"]
    r_cc = get_risk_free_rate()["rate_cc"]
    candles = _candles(asset)
    return _price_strategy(
        legs, S=spot, r_cc=r_cc,
        sigma=lambda t_days: _sigma_for(t_days, candles)[0],
    )
