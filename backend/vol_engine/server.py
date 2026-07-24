"""FastMCP server exposing the CONTRACTS §1 tools (PLAN task A1.4).

Thin by design: zero logic, every tool delegates to vol_engine.api.
The agent computes nothing — these tools are where all numbers come from.

Run (stdio): cd backend && uv run python -m vol_engine.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from vol_engine import api

mcp = FastMCP("optoputs-vol-engine")


@mcp.tool()
def get_price_history(hours: int = 720) -> dict:
    """Trailing hourly ETH/USDC OHLC candles from Uniswap v3 (ascending)."""
    return api.get_price_history(hours)


@mcp.tool()
def get_spot() -> dict:
    """Latest ETH price in USD (Uniswap v3 pool token0Price)."""
    return api.get_spot()


@mcp.tool()
def estimate_vol(window: str, estimator: str = "close") -> dict:
    """Annualized realized vol. window: 24h|7d|30d; estimator: close|parkinson."""
    return api.estimate_vol(window, estimator)


@mcp.tool()
def get_regime(bands: dict[str, float] | None = None) -> dict:
    """Vol regime (calm/elevated/stressed): current 7d vol percentile in its
    trailing 30d distribution. bands are the user's thresholds, echoed back."""
    return api.get_regime(bands)


@mcp.tool()
def get_risk_free_rate() -> dict:
    """Continuously-compounded USDC financing rate (Aave v3; falls back to a
    constant — fallback_level says which source produced it)."""
    return api.get_risk_free_rate()


@mcp.tool()
def price_option(
    K: float, T_days: float, type: str, qty: float = 1.0, S: float | None = None
) -> dict:
    """Black-Scholes quote for a European cash-settled ETH option.
    Omit S to use live spot. Returns price, inputs used, and Greeks."""
    return api.price_option(K=K, T_days=T_days, type=type, qty=qty, S=S)


@mcp.tool()
def price_strategy(legs: list[dict]) -> dict:
    """Price a multi-leg strategy. Each leg: {type: call|put, side: long|short,
    K, T_days, qty}. Returns net cost/Greeks, payoff curve, breakevens, max P/L."""
    return api.price_strategy(legs)


@mcp.tool()
def list_strategies() -> list[dict]:
    """The named strategy library (view + leg template per structure)."""
    return api.list_strategies()


@mcp.tool()
def resolve_strategy(name: str, T_days: float) -> list[dict]:
    """Turn a library strategy name into explicit legs at current spot."""
    return api.resolve_named(name, S=api.get_spot()["price"], T_days=T_days)


if __name__ == "__main__":
    mcp.run()
