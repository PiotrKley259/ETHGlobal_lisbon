"""Strategy library + multi-leg pricing composition (PLAN task A1.3).

A strategy is a basket of the calls/puts already priced by pricing.py:
price each leg, sum with signs and quantities; the payoff curve is the sum
of leg payoffs across terminal prices. Depends only on pricing.py/types.py.

Named structures are resolved to explicit legs (the agent normally does
this via resolve_named); the engine itself only ever prices explicit legs,
per CONTRACTS §1.
"""
from __future__ import annotations

from collections.abc import Callable

from .pricing import bs_greeks, bs_price

_SLOPE_EPS = 1e-6
GRID_POINTS = 121

# Declarative templates: strikes as moneyness (K = m * S), rounded to $10.
LIBRARY: dict[str, dict] = {
    "long_call": {
        "view": "bullish; unlimited upside for a known premium",
        "legs_template": "long call ATM",
        "template": [("call", "long", 1.00, 1)],
    },
    "long_put": {
        "view": "bearish or hedging; insurance below the strike",
        "legs_template": "long put ATM (or below spot for cheaper cover)",
        "template": [("put", "long", 1.00, 1)],
    },
    "bull_call_spread": {
        "view": "moderately bullish; capped upside for lower cost",
        "legs_template": "long call K1, short call K2 > K1",
        "template": [("call", "long", 1.00, 1), ("call", "short", 1.05, 1)],
    },
    "bear_put_spread": {
        "view": "moderately bearish; capped payout for lower cost",
        "legs_template": "long put K1, short put K2 < K1",
        "template": [("put", "long", 1.00, 1), ("put", "short", 0.95, 1)],
    },
    "long_straddle": {
        "view": "big move either way; pay premium, profit if it breaks",
        "legs_template": "long call ATM + long put ATM",
        "template": [("call", "long", 1.00, 1), ("put", "long", 1.00, 1)],
    },
    "long_strangle": {
        "view": "big move either way, cheaper than straddle, needs a bigger move",
        "legs_template": "long call OTM + long put OTM",
        "template": [("call", "long", 1.05, 1), ("put", "long", 0.95, 1)],
    },
    "long_butterfly": {
        "view": "pin at the middle strike; small debit, tent-shaped payoff",
        "legs_template": "long call K1, short 2 calls K2, long call K3",
        "template": [
            ("call", "long", 0.95, 1),
            ("call", "short", 1.00, 2),
            ("call", "long", 1.05, 1),
        ],
    },
    "short_straddle": {
        "view": "profit from calm; collect premium, lose if it breaks either way",
        "legs_template": "short call ATM + short put ATM",
        "template": [("call", "short", 1.00, 1), ("put", "short", 1.00, 1)],
    },
}


def list_strategies() -> list[dict]:
    return [
        {"name": name, "view": s["view"], "legs_template": s["legs_template"],
         "n_legs": len(s["template"])}
        for name, s in LIBRARY.items()
    ]


def resolve_named(name: str, S: float, T_days: float) -> list[dict]:
    """Turn a library template into explicit legs at the current spot."""
    if name not in LIBRARY:
        raise ValueError(f"unknown strategy {name!r}; see list_strategies()")
    return [
        {"type": t, "side": side, "K": round(m * S / 10) * 10.0,
         "T_days": T_days, "qty": float(qty)}
        for t, side, m, qty in LIBRARY[name]["template"]
    ]


def _validate_leg(leg: dict) -> None:
    if leg.get("type") not in ("call", "put"):
        raise ValueError(f"leg type must be call/put, got {leg.get('type')!r}")
    if leg.get("side") not in ("long", "short"):
        raise ValueError(f"leg side must be long/short, got {leg.get('side')!r}")
    if not leg.get("K") or leg["K"] <= 0 or leg.get("T_days", -1) < 0:
        raise ValueError(f"leg needs K > 0 and T_days >= 0: {leg}")


def _intrinsic(opt_type: str, K: float, s_t: float) -> float:
    return max(s_t - K, 0.0) if opt_type == "call" else max(K - s_t, 0.0)


def price_strategy(
    legs: list[dict],
    S: float,
    r_cc: float,
    sigma: float | Callable[[float], float],
) -> dict:
    """Price an explicit basket of legs. `sigma` is a flat vol or a callable
    sigma(T_days) (the Stage-4 term-structure hook plugs in there)."""
    if not legs:
        raise ValueError("strategy needs at least one leg")
    for leg in legs:
        _validate_leg(leg)
    sigma_of = sigma if callable(sigma) else (lambda _t: sigma)

    priced, net_cost = [], 0.0
    net_greeks = dict.fromkeys(("delta", "gamma", "vega", "theta", "rho"), 0.0)
    for leg in legs:
        qty = float(leg.get("qty", 1.0))
        sign = 1.0 if leg["side"] == "long" else -1.0
        sig = sigma_of(leg["T_days"])
        price = bs_price(S, leg["K"], leg["T_days"], sig, r_cc, leg["type"])
        greeks = bs_greeks(S, leg["K"], leg["T_days"], sig, r_cc, leg["type"])
        net_cost += sign * price * qty
        for k in net_greeks:
            net_greeks[k] += sign * getattr(greeks, k) * qty
        priced.append({
            "price": price, "qty": qty, "side": leg["side"],
            "inputs": {"S": S, "K": leg["K"], "T_days": leg["T_days"],
                       "r_cc": r_cc, "sigma": sig, "type": leg["type"]},
            "greeks": greeks.model_dump(),
        })

    t_ref = max(leg["T_days"] for leg in legs)
    sig_ref = sigma_of(t_ref)
    span = max(3.0 * sig_ref * (t_ref / 365.0) ** 0.5 * S, 0.15 * S,
               1.3 * max(abs(leg["K"] - S) for leg in legs))
    lo, hi = max(S - span, 0.0), S + span
    step = (hi - lo) / (GRID_POINTS - 1)
    prices = [lo + i * step for i in range(GRID_POINTS)]

    def pnl(s_t: float) -> float:
        total = 0.0
        for leg, quote in zip(legs, priced):
            sign = 1.0 if leg["side"] == "long" else -1.0
            total += sign * (_intrinsic(leg["type"], leg["K"], s_t)
                             - quote["price"]) * quote["qty"]
        return total

    pnls = [pnl(p) for p in prices]

    breakevens = []
    for i in range(len(prices) - 1):
        y0, y1 = pnls[i], pnls[i + 1]
        if y0 == 0.0:
            breakevens.append(prices[i])
        elif y0 * y1 < 0:
            breakevens.append(prices[i] - y0 * (prices[i + 1] - prices[i]) / (y1 - y0))
    if pnls[-1] == 0.0:
        breakevens.append(prices[-1])

    kinks = sorted({leg["K"] for leg in legs})
    candidates = [pnl(k) for k in kinks] + [pnls[0], pnls[-1]]
    slope_hi = (pnls[-1] - pnls[-2]) / step
    slope_lo = (pnls[1] - pnls[0]) / step
    at_zero = pnls[0] + slope_lo * (0.0 - prices[0])

    max_profit: float | None = max(candidates)
    if slope_hi > _SLOPE_EPS:
        max_profit = None
    elif slope_lo < -_SLOPE_EPS:
        max_profit = max(max_profit, at_zero)

    max_loss: float | None = min(candidates)
    if slope_hi < -_SLOPE_EPS:
        max_loss = None
    elif slope_lo > _SLOPE_EPS:
        max_loss = min(max_loss, at_zero)

    return {
        "net_cost": net_cost,
        "net_greeks": net_greeks,
        "legs": priced,
        "payoff": {"prices": prices, "pnl": pnls},
        "breakevens": breakevens,
        "max_profit": max_profit,
        "max_loss": max_loss,
    }
