"""Settlement worker (PLAN task I2.3).

The on-chain Scheduled Transaction is the settlement *commitment*; the
payoff amount cannot be computed at expiry on-chain (CONTRACTS §2), so this
worker computes max(0, S-K) (reversed for puts) at expiry from live spot and
triggers /settlement/execute. Retries are safe — the sidecar is idempotent
per token_id.

execute_due() is synchronous and pure-ish for testability; worker_loop()
is the asyncio wrapper app.py runs.
"""
from __future__ import annotations

import asyncio
import time

from vol_engine import api

from . import risk, sidecar

# token_id -> series terms
_registry: dict[str, dict] = {}


def reset_registry() -> None:
    _registry.clear()


def register_series(token_id: str, opt_type: str, K: float, qty: float,
                    expiry_ts: int, symbol: str, asset: str = "ETH") -> None:
    _registry[token_id] = {
        "token_id": token_id, "type": opt_type, "K": float(K), "qty": float(qty),
        "expiry_ts": int(expiry_ts), "symbol": symbol, "asset": asset,
        "armed": False, "settled": False,
    }


def mark_armed(token_id: str) -> None:
    if token_id in _registry:
        _registry[token_id]["armed"] = True


def open_series() -> list[dict]:
    return [dict(s) for s in _registry.values() if not s["settled"]]


def _payoff(opt_type: str, K: float, qty: float, spot: float) -> float:
    intrinsic = max(spot - K, 0.0) if opt_type == "call" else max(K - spot, 0.0)
    return intrinsic * qty


def execute_due(now: float | None = None) -> list[dict]:
    """Settle every armed, expired, unsettled series. Returns CONTRACTS §3
    chain events (status=paid) for each settlement performed."""
    now = time.time() if now is None else now
    events = []
    for series in _registry.values():
        if series["settled"] or not series["armed"] or series["expiry_ts"] > now:
            continue
        spot = api.get_spot(series.get("asset", "ETH"))["price"]
        payout = round(_payoff(series["type"], series["K"], series["qty"], spot), 2)
        result = sidecar.execute_settlement(series["token_id"], payout, spot)
        series["settled"] = True
        risk.release_exposure(series["token_id"])
        events.append({
            "kind": "settle",
            "label": f"{series['symbol']} paid ${payout:,.2f}",
            "id": series["token_id"],
            "tx_id": result.get("tx_id", ""),
            "hashscan_url": result.get("hashscan_url", ""),
            "status": "paid",
        })
    return events


async def worker_loop(pending_chain: list[dict], poll_s: float = 5.0) -> None:
    """Append settle events to the app's pending queue; they are flushed to
    the UI at the start of the next /chat stream."""
    while True:
        try:
            pending_chain.extend(execute_due())
        except Exception:
            pass  # transient sidecar/graph failure: retry next tick (idempotent)
        await asyncio.sleep(poll_s)
