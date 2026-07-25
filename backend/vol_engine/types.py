"""Shared dataclasses/pydantic models mirroring docs/CONTRACTS.md §1 shapes.

Owned by track A1 — the single place both vol.py and pricing.py import from,
so the parallel subagents building them don't collide.
"""
from pydantic import BaseModel


class Candle(BaseModel):
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume_usd: float


class Vol(BaseModel):
    sigma_annual: float
    sigma_period: float  # 1-sigma expected move over the window itself (display)
    window: str  # "24h" | "7d" | "30d"
    estimator: str  # "close" | "parkinson"
    n_obs: int


class Regime(BaseModel):
    regime: str  # "calm" | "elevated" | "stressed"
    percentile: float
    window: str = "7d"
    bands: dict[str, float]  # {"calm": 0.33, "elevated": 0.66}


class Greeks(BaseModel):
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
