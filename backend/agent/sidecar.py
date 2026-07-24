"""Thin HTTP client for the Hedera sidecar (CONTRACTS §2). Lane A never
touches Hedera directly — every chain action goes through these wrappers.
The sidecar guarantees idempotency (per token_id / symbol), so callers may
retry freely.
"""
from __future__ import annotations

import httpx

import config

_TIMEOUT = 20.0  # Hedera consensus can take a few seconds


def _post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{config.SIDECAR_URL}{path}", json=body, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def mint_series(symbol: str, name: str, option: dict) -> dict:
    return _post("/tokens/mint-series", {"symbol": symbol, "name": name, "option": option})


def hcs_log(kind: str, payload: dict) -> dict:
    return _post("/hcs/log", {"kind": kind, "payload": payload})


def schedule_settlement(token_id: str, expiry_ts: int, max_payout_usd: float) -> dict:
    return _post("/settlement/schedule", {
        "token_id": token_id, "expiry_ts": expiry_ts, "max_payout_usd": max_payout_usd,
    })


def execute_settlement(token_id: str, payout_usd: float, spot_at_expiry: float) -> dict:
    return _post("/settlement/execute", {
        "token_id": token_id, "payout_usd": payout_usd, "spot_at_expiry": spot_at_expiry,
    })
