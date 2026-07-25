"""Black-Scholes price + closed-form Greeks (PLAN task A1.1).

Pure math: no I/O, no network, no imports from graph/ or agent/.

Conventions (frozen in docs/CONTRACTS.md §1):
- T is passed in DAYS and converted with 365 days/year.
- r is continuously compounded (decimal).
- Greeks per 1 unit of the option: vega = dP/d(sigma) per 1.00 of vol,
  rho = dP/dr per 1.00 of rate, theta per calendar day (annual theta / 365).
- At T<=0 or sigma<=0 the value degenerates to (discounted) intrinsic.
"""
from __future__ import annotations

import math
from typing import Literal

from .types import Greeks

DAYS_PER_YEAR = 365.0

OptionType = Literal["call", "put"]


def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _validate(S: float, K: float, T_days: float, opt_type: str) -> None:
    if S <= 0:
        raise ValueError(f"spot must be > 0, got {S}")
    if K <= 0:
        raise ValueError(f"strike must be > 0, got {K}")
    if T_days < 0:
        raise ValueError(f"T_days must be >= 0, got {T_days}")
    if opt_type not in ("call", "put"):
        raise ValueError(f"type must be 'call' or 'put', got {opt_type!r}")


def _d1_d2(S: float, K: float, T: float, sigma: float, r: float) -> tuple[float, float]:
    srt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / srt
    return d1, d1 - srt


def bs_price(
    S: float, K: float, T_days: float, sigma: float, r_cc: float, opt_type: OptionType
) -> float:
    """European option price. Degenerate cases collapse to intrinsic value."""
    _validate(S, K, T_days, opt_type)
    T = T_days / DAYS_PER_YEAR
    sign = 1.0 if opt_type == "call" else -1.0
    if T_days == 0:
        return max(sign * (S - K), 0.0)
    if sigma <= 0:
        return max(sign * (S - K * math.exp(-r_cc * T)), 0.0)
    d1, d2 = _d1_d2(S, K, T, sigma, r_cc)
    disc = math.exp(-r_cc * T)
    if opt_type == "call":
        return S * _norm_cdf(d1) - K * disc * _norm_cdf(d2)
    return K * disc * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_greeks(
    S: float, K: float, T_days: float, sigma: float, r_cc: float, opt_type: OptionType
) -> Greeks:
    """Closed-form Greeks from the same d1/d2 pass as the price."""
    _validate(S, K, T_days, opt_type)
    T = T_days / DAYS_PER_YEAR
    if T_days == 0 or sigma <= 0:
        sign = 1.0 if opt_type == "call" else -1.0
        disc = math.exp(-r_cc * T)
        itm = sign * (S - K * disc) > 0
        if not itm:
            return Greeks(delta=0.0, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)
        return Greeks(
            delta=sign,
            gamma=0.0,
            vega=0.0,
            theta=-sign * r_cc * K * disc / DAYS_PER_YEAR,
            rho=sign * K * T * disc,
        )

    d1, d2 = _d1_d2(S, K, T, sigma, r_cc)
    disc = math.exp(-r_cc * T)
    pdf1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(T)

    gamma = pdf1 / (S * sigma * sqrt_t)
    vega = S * pdf1 * sqrt_t
    common_theta = -S * pdf1 * sigma / (2.0 * sqrt_t)

    if opt_type == "call":
        delta = _norm_cdf(d1)
        theta_annual = common_theta - r_cc * K * disc * _norm_cdf(d2)
        rho = K * T * disc * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1.0
        theta_annual = common_theta + r_cc * K * disc * _norm_cdf(-d2)
        rho = -K * T * disc * _norm_cdf(-d2)

    return Greeks(
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta=theta_annual / DAYS_PER_YEAR,
        rho=rho,
    )
