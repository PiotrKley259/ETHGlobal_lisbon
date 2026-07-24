"""GraphQL adapter for The Graph gateway (PLAN track A2).

- OFFLINE_MODE=1 serves fixtures/ through the same code path (the fixture IS
  a recorded gateway response), so tests and demo-day fallback are identical.
- In-memory TTL cache: history 10 min, spot 30 s, rate 1 h. Pricing never
  triggers network — it reads these cached fetchers (CONTRACTS §1).
- Verified queries, field names, and gotchas: docs/CONTRACTS.md §6.
"""
from __future__ import annotations

import json
import math
import time

import httpx

import config

HISTORY_TTL_S = 600
SPOT_TTL_S = 30
RATE_TTL_S = 3600

_cache: dict[str, tuple[float, object]] = {}


def clear_cache() -> None:
    _cache.clear()


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    return None


def _cache_put(key: str, ttl_s: float, value):
    _cache[key] = (time.monotonic() + ttl_s, value)
    return value


def _load_fixture(name: str) -> dict:
    return json.loads((config.FIXTURES_DIR / name).read_text())["data"]


def _gateway(subgraph_id: str, query: str) -> dict:
    url = config.GRAPH_GATEWAY.format(key=config.GRAPH_API_KEY, subgraph=subgraph_id)
    resp = httpx.post(url, json={"query": query}, timeout=15.0)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"subgraph error: {body['errors']}")
    return body["data"]


# --- pool data ---------------------------------------------------------------

def _history_query(hours: int) -> str:
    return (
        f'{{ poolHourDatas(first: {hours}, orderBy: periodStartUnix, '
        f'orderDirection: desc, where: {{ pool: "{config.ETH_USDC_POOL}" }}) '
        f'{{ periodStartUnix open high low close volumeUSD }} }}'
    )


def get_price_history(hours: int = 720) -> dict:
    """Trailing hourly OHLC candles, ascending by ts (CONTRACTS §1)."""
    key = f"history:{hours}"
    if (hit := _cache_get(key)) is not None:
        return hit
    if config.OFFLINE_MODE:
        raw = _load_fixture("pool_hour_datas.json")["poolHourDatas"][:hours]
    else:
        raw = _gateway(config.UNISWAP_SUBGRAPH_ID, _history_query(hours))["poolHourDatas"]
    candles = [
        {
            "ts": int(c["periodStartUnix"]),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume_usd": float(c["volumeUSD"]),
        }
        for c in reversed(raw)  # gateway returns desc; contract wants asc
    ]
    return _cache_put(key, HISTORY_TTL_S, {
        "pool": config.ETH_USDC_POOL, "hours": hours, "candles": candles,
    })


_SPOT_QUERY = (
    f'{{ pool(id: "{config.ETH_USDC_POOL}") {{ token0Price }} '
    f'_meta {{ block {{ timestamp }} }} }}'
)


def get_spot() -> dict:
    """Latest pool price. token0Price is already ETH in USD for this pool
    (verified — no inversion; CONTRACTS §6)."""
    if (hit := _cache_get("spot")) is not None:
        return hit
    data = _load_fixture("spot.json") if config.OFFLINE_MODE \
        else _gateway(config.UNISWAP_SUBGRAPH_ID, _SPOT_QUERY)
    return _cache_put("spot", SPOT_TTL_S, {
        "price": float(data["pool"]["token0Price"]),
        "ts": int(data["_meta"]["block"]["timestamp"]),
        "source": "uniswap-v3-subgraph",
    })


# --- risk-free rate ----------------------------------------------------------

USDC_MAINNET = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
_AAVE_QUERY = (
    f'{{ reserves(where: {{ underlyingAsset: "{USDC_MAINNET}" }}) '
    f'{{ symbol variableBorrowRate lastUpdateTimestamp }} }}'
)


def ray_to_apr(ray: str | int) -> float:
    """Aave rates are APR scaled by 1e27 (ray)."""
    return int(ray) / 1e27


def apr_to_cc(apr: float) -> float:
    """Annual rate -> continuously compounded (r_cc = ln(1+r))."""
    return math.log(1.0 + apr)


def get_risk_free_rate() -> dict:
    """USDC borrow rate from Aave v3 (the desk's true financing rate — the
    payoff is stablecoin-settled). Fallback: constant from config.
    fallback_level: 0 = live Aave, 2 = constant. (FRED tier is Stage 4.)"""
    if (hit := _cache_get("rate")) is not None:
        return hit
    if not config.OFFLINE_MODE:
        try:
            reserves = _gateway(config.AAVE_SUBGRAPH_ID, _AAVE_QUERY)["reserves"]
            reserve = next(r for r in reserves if r["symbol"] == "USDC")
            return _cache_put("rate", RATE_TTL_S, {
                "rate_cc": apr_to_cc(ray_to_apr(reserve["variableBorrowRate"])),
                "source": "aave-v3-subgraph",
                "observed_at": int(reserve["lastUpdateTimestamp"]),
                "fallback_level": 0,
            })
        except Exception:
            pass  # fall through to constant
    return _cache_put("rate", RATE_TTL_S, {
        "rate_cc": apr_to_cc(config.RISK_FREE_RATE_CONSTANT),
        "source": "constant",
        "observed_at": int(time.time()),
        "fallback_level": 2,
    })
