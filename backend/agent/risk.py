"""Treasury coverage gate (PLAN task I2.1) — CONTRACTS §1 check_coverage.

The desk refuses to sell what it cannot pay: per-series cap, plus an
in-memory ledger of open exposure measured against the sidecar-reported
treasury balance. Fails CLOSED: if the sidecar is unreachable, coverage
is not ok and the agent must refuse the mint.
"""
from __future__ import annotations

import httpx

import config

SERIES_CAP_USD = 10_000.0

# token_id/series -> reserved max payout in USD
_exposure: dict[str, float] = {}


def reset_ledger() -> None:
    _exposure.clear()


def open_exposure_usd() -> float:
    return sum(_exposure.values())


def register_exposure(series_id: str, max_payout_usd: float) -> None:
    _exposure[series_id] = float(max_payout_usd)


def release_exposure(series_id: str) -> None:
    _exposure.pop(series_id, None)


def compute_max_payout(opt_type: str, K: float, qty: float) -> float:
    """Worst-case cash settlement per series. Put: K*qty (ETH -> 0).
    Call: theoretically unbounded — the desk caps payout per series
    (spec: 'max payout capped per series'), so reserve the cap."""
    if opt_type == "put":
        return min(K * qty, SERIES_CAP_USD)
    return SERIES_CAP_USD


def treasury_balance_usd() -> float:
    resp = httpx.get(f"{config.SIDECAR_URL}/treasury/balances", timeout=5.0)
    resp.raise_for_status()
    return float(resp.json()["stablecoin_usd"])


def check_coverage(max_payout_usd: float) -> dict:
    """CONTRACTS §1 Coverage. ok=false (never an exception) when the desk
    cannot or should not take the risk."""
    try:
        balance = treasury_balance_usd()
    except Exception:
        return {
            "ok": False,
            "treasury_balance_usd": 0.0,
            "open_exposure_usd": open_exposure_usd(),
            "series_cap_usd": SERIES_CAP_USD,
            "reason": "treasury unreachable — failing closed",
        }
    exposure = open_exposure_usd()
    ok = (
        max_payout_usd <= SERIES_CAP_USD
        and exposure + max_payout_usd <= balance
    )
    result = {
        "ok": ok,
        "treasury_balance_usd": balance,
        "open_exposure_usd": exposure,
        "series_cap_usd": SERIES_CAP_USD,
    }
    if not ok:
        result["reason"] = (
            "exceeds per-series cap" if max_payout_usd > SERIES_CAP_USD
            else "insufficient treasury coverage"
        )
    return result
