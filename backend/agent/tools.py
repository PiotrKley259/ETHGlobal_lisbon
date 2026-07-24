"""Agent tool layer (PLAN task I1.1): Anthropic tool schemas bound 1:1 to the
vol_engine.api facade, plus the backend-owned settings tool and the panel
builder. The agent computes nothing — every number flows through dispatch().

Chain tools (mint/settle via the sidecar) are added in Stage 3 (I2.2).
"""
from __future__ import annotations

from typing import Any

from vol_engine import api

_LEG_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["call", "put"]},
        "side": {"type": "string", "enum": ["long", "short"]},
        "K": {"type": "number", "description": "strike in USD"},
        "T_days": {"type": "number", "description": "days to expiry"},
        "qty": {"type": "number", "default": 1.0},
    },
    "required": ["type", "side", "K", "T_days"],
}

TOOLS: list[dict] = [
    {
        "name": "get_spot",
        "description": "Latest ETH price in USD from the Uniswap v3 ETH/USDC pool. Call this before quoting anything.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "estimate_vol",
        "description": "Annualized realized volatility of ETH from Uniswap hourly candles. window: 24h, 7d or 30d; estimator close (default) or parkinson.",
        "input_schema": {
            "type": "object",
            "properties": {
                "window": {"type": "string", "enum": ["24h", "7d", "30d"]},
                "estimator": {"type": "string", "enum": ["close", "parkinson"], "default": "close"},
            },
            "required": ["window"],
        },
    },
    {
        "name": "get_regime",
        "description": "Current vol regime (calm/elevated/stressed): where today's 7d vol sits in its trailing 30d distribution, labeled with the user's configured bands.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_risk_free_rate",
        "description": "Continuously-compounded USDC financing rate used in pricing (live Aave v3 borrow rate, or a constant fallback).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "price_option",
        "description": "Black-Scholes price + Greeks for one European cash-settled ETH option. Uses live spot unless S is given. Call this for every single-leg quote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "K": {"type": "number", "description": "strike in USD"},
                "T_days": {"type": "number", "description": "days to expiry"},
                "type": {"type": "string", "enum": ["call", "put"]},
                "qty": {"type": "number", "default": 1.0},
                "S": {"type": "number", "description": "override spot (normally omit)"},
            },
            "required": ["K", "T_days", "type"],
        },
    },
    {
        "name": "price_strategy",
        "description": "Price a multi-leg strategy from explicit legs: net cost (negative = credit), net Greeks, payoff curve with breakevens and max profit/loss. Use resolve_strategy first to turn a named structure into legs.",
        "input_schema": {
            "type": "object",
            "properties": {"legs": {"type": "array", "items": _LEG_SCHEMA, "minItems": 1}},
            "required": ["legs"],
        },
    },
    {
        "name": "list_strategies",
        "description": "The desk's named strategy library with the market view each expresses.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_strategy",
        "description": "Turn a library strategy name (e.g. short_straddle) into explicit legs at current spot for a given expiry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "T_days": {"type": "number"},
            },
            "required": ["name", "T_days"],
        },
    },
    {
        "name": "set_regime_bands",
        "description": "Update the user's regime thresholds when they express a risk preference (e.g. 'only the top 20% counts as stressed' -> calm 0.33, elevated 0.80). Requires 0 < calm < elevated < 1.",
        "input_schema": {
            "type": "object",
            "properties": {
                "calm": {"type": "number"},
                "elevated": {"type": "number"},
            },
            "required": ["calm", "elevated"],
        },
    },
]


def default_state() -> dict:
    return {
        "settings": {"regime_bands": {"calm": 0.33, "elevated": 0.66}},
        "last_quote": None,
        "last_strategy": None,
    }


def dispatch(name: str, args: dict[str, Any], state: dict) -> dict:
    """Execute one tool call against the engine; records quote/strategy in
    state so the panel always shows what produced the latest number."""
    if name == "get_spot":
        return api.get_spot()
    if name == "estimate_vol":
        return api.estimate_vol(args["window"], args.get("estimator", "close"))
    if name == "get_regime":
        return api.get_regime(state["settings"]["regime_bands"])
    if name == "get_risk_free_rate":
        return api.get_risk_free_rate()
    if name == "price_option":
        quote = api.price_option(
            K=args["K"], T_days=args["T_days"], type=args["type"],
            qty=args.get("qty", 1.0), S=args.get("S"),
        )
        state["last_quote"], state["last_strategy"] = quote, None
        return quote
    if name == "price_strategy":
        strat = api.price_strategy(args["legs"])
        state["last_strategy"], state["last_quote"] = strat, None
        return strat
    if name == "list_strategies":
        return {"strategies": api.list_strategies()}
    if name == "resolve_strategy":
        legs = api.resolve_named(
            args["name"], S=api.get_spot()["price"], T_days=args["T_days"]
        )
        return {"legs": legs}
    if name == "set_regime_bands":
        calm, elevated = float(args["calm"]), float(args["elevated"])
        if not (0.0 < calm < elevated < 1.0):
            raise ValueError(f"need 0 < calm < elevated < 1, got {calm}, {elevated}")
        state["settings"]["regime_bands"] = {"calm": calm, "elevated": elevated}
        return {"regime_bands": state["settings"]["regime_bands"]}
    raise ValueError(f"unknown tool {name!r}")


def summarize(name: str, result: dict) -> str:
    """One-line chip text for the UI's tool_result events."""
    try:
        if name == "get_spot":
            return f"${result['price']:,.2f}"
        if name == "estimate_vol":
            return f"σ={result['sigma_annual']:.0%} ({result['window']}, {result['estimator']})"
        if name == "get_regime":
            return f"{result['regime']} ({result['percentile']:.0%} pct)"
        if name == "get_risk_free_rate":
            return f"{result['rate_cc']:.2%} cc ({result['source']})"
        if name == "price_option":
            i = result["inputs"]
            return f"${result['price']:,.2f} @ σ {i['sigma']:.0%} ({i['sigma_source']})"
        if name == "price_strategy":
            cost = result["net_cost"]
            label = "credit" if cost < 0 else "debit"
            return f"{label} ${abs(cost):,.2f}, breakevens {[round(b) for b in result['breakevens']]}"
        if name == "list_strategies":
            return f"{len(result['strategies'])} structures"
        if name == "resolve_strategy":
            return f"{len(result['legs'])} legs"
        if name == "set_regime_bands":
            b = result["regime_bands"]
            return f"calm<{b['calm']:.2f}, stressed≥{b['elevated']:.2f}"
    except Exception:
        pass
    return "done"


def build_panel(state: dict) -> dict:
    """Full pricing-panel object per CONTRACTS §3 (whole object every time)."""
    return {
        "spot": api.get_spot(),
        "vols": [api.estimate_vol(w) for w in ("24h", "7d", "30d")],
        "regime": api.get_regime(state["settings"]["regime_bands"]),
        "rate": api.get_risk_free_rate(),
        "quote": state["last_quote"],
        "strategy": state["last_strategy"],
        "curve": None,  # Stage 4: get_vol_curve
    }
