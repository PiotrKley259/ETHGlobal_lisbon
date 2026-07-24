"""Engine facade (PLAN task A1.4): the one place cached market data meets the
pure math. Every function returns exactly the CONTRACTS §1 JSON shape; both
the MCP server (server.py) and the agent tools (agent/tools.py) call these.

Network policy: data arrives only via graph.subgraph's cached fetchers —
pricing itself never fetches (OFFLINE_MODE=1 therefore always works).
"""
from __future__ import annotations

from graph import subgraph

from .pricing import bs_greeks, bs_price
from .strategies import list_strategies as _list_strategies
from .strategies import price_strategy as _price_strategy
from .strategies import resolve_named
from .types import Candle
from .vol import estimate_vol as _estimate_vol
from .vol import get_regime as _get_regime
from .vol import select_sigma_window

__all__ = [
    "get_price_history", "get_spot", "estimate_vol", "get_regime",
    "get_risk_free_rate", "price_option", "price_strategy",
    "list_strategies", "resolve_named",
]

get_price_history = subgraph.get_price_history
get_spot = subgraph.get_spot
get_risk_free_rate = subgraph.get_risk_free_rate
list_strategies = _list_strategies


# 31 days of hourly candles: the 30d close-to-close window needs 721 closes
# (720 returns), and the regime's rolling series wants headroom beyond that.
HISTORY_HOURS = 744


def _candles() -> list[Candle]:
    return [
        Candle(**c)
        for c in subgraph.get_price_history(hours=HISTORY_HOURS)["candles"]
    ]


def estimate_vol(window: str, estimator: str = "close") -> dict:
    return _estimate_vol(_candles(), window, estimator).model_dump()


def get_regime(bands: dict[str, float] | None = None) -> dict:
    return _get_regime(_candles(), bands).model_dump()


def _sigma_for(T_days: float, candles: list[Candle]) -> tuple[float, str]:
    window = select_sigma_window(T_days)
    return _estimate_vol(candles, window, "close").sigma_annual, window


def price_option(
    K: float, T_days: float, type: str, qty: float = 1.0, S: float | None = None
) -> dict:
    """Quote per CONTRACTS §1. price is total for qty; Greeks are per 1 unit.
    S=None (the normal case) uses the latest cached spot."""
    spot = float(S) if S is not None else get_spot()["price"]
    r_cc = get_risk_free_rate()["rate_cc"]
    sigma, window = _sigma_for(T_days, _candles())
    unit = bs_price(spot, K, T_days, sigma, r_cc, type)
    greeks = bs_greeks(spot, K, T_days, sigma, r_cc, type)
    return {
        "price": unit * qty,
        "qty": qty,
        "inputs": {"S": spot, "K": K, "T_days": T_days, "r_cc": r_cc,
                   "sigma": sigma, "sigma_source": window},
        "greeks": greeks.model_dump(),
    }


def price_strategy(legs: list[dict]) -> dict:
    """StrategyQuote per CONTRACTS §1; per-leg sigma tenor-matched via
    select_sigma_window (Stage 4 swaps in sigma_for_horizon here)."""
    spot = get_spot()["price"]
    r_cc = get_risk_free_rate()["rate_cc"]
    candles = _candles()
    return _price_strategy(
        legs, S=spot, r_cc=r_cc,
        sigma=lambda t_days: _sigma_for(t_days, candles)[0],
    )
