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

def _asset_cfg(asset: str) -> dict:
    if asset not in config.ASSETS:
        raise ValueError(f"unknown asset {asset!r}; desk quotes {sorted(config.ASSETS)}")
    return config.ASSETS[asset]


def _history_query(pool: str, hours: int) -> str:
    return (
        f'{{ poolHourDatas(first: {hours}, orderBy: periodStartUnix, '
        f'orderDirection: desc, where: {{ pool: "{pool}" }}) '
        f'{{ periodStartUnix open high low close volumeUSD }} }}'
    )


def _to_usd_candle(c: dict, invert: bool) -> dict:
    """Raw poolHourData -> USD candle. When the pool's token0 is the asset
    (invert=True), OHLC is TOKEN-per-USDC: flip with 1/x AND swap high/low
    (the max of the reciprocal is the reciprocal of the min)."""
    o, h, lo, cl = (float(c[k]) for k in ("open", "high", "low", "close"))
    if invert:
        o, h, lo, cl = 1.0 / o, 1.0 / lo, 1.0 / h, 1.0 / cl
    return {
        "ts": int(c["periodStartUnix"]),
        "open": o, "high": h, "low": lo, "close": cl,
        "volume_usd": float(c["volumeUSD"]),
    }


def get_price_history(hours: int = 720, asset: str = config.DEFAULT_ASSET) -> dict:
    """Trailing hourly USD OHLC candles, ascending by ts (CONTRACTS §1)."""
    cfg = _asset_cfg(asset)
    key = f"history:{asset}:{hours}"
    if (hit := _cache_get(key)) is not None:
        return hit
    if config.OFFLINE_MODE:
        raw = _load_fixture(
            f"pool_hour_datas{cfg['fixture_suffix']}.json")["poolHourDatas"][:hours]
    else:
        raw = _gateway(config.UNISWAP_SUBGRAPH_ID,
                       _history_query(cfg["pool"], hours))["poolHourDatas"]
    candles = [_to_usd_candle(c, cfg["invert"]) for c in reversed(raw)]
    if cfg.get("quote", "USDC") == "WETH":
        # cross to USD with the same-hour ETH close. Close-to-close returns
        # compose exactly (r_usd = r_weth + r_eth); intra-hour high/low are
        # scaled by the hourly ETH close, an approximation that keeps
        # high >= low (fine for close vol; Parkinson is approximate here).
        eth_close = {c["ts"]: c["close"]
                     for c in get_price_history(hours, "ETH")["candles"]}
        candles = [
            {**c, "open": c["open"] * e, "high": c["high"] * e,
             "low": c["low"] * e, "close": c["close"] * e}
            for c in candles if (e := eth_close.get(c["ts"])) is not None
        ]
    return _cache_put(key, HISTORY_TTL_S, {
        "pool": cfg["pool"], "asset": asset, "hours": hours, "candles": candles,
    })


def _spot_query(pool: str) -> str:
    return (
        f'{{ pool(id: "{pool}") {{ token0Price token1Price }} '
        f'_meta {{ block {{ timestamp }} }} }}'
    )


def get_spot(asset: str = config.DEFAULT_ASSET) -> dict:
    """Latest pool price in USD. Non-inverted pools (USDC = token0) read
    token0Price directly; inverted pools read token1Price (CONTRACTS §6)."""
    cfg = _asset_cfg(asset)
    key = f"spot:{asset}"
    if (hit := _cache_get(key)) is not None:
        return hit
    data = _load_fixture(f"spot{cfg['fixture_suffix']}.json") if config.OFFLINE_MODE \
        else _gateway(config.UNISWAP_SUBGRAPH_ID, _spot_query(cfg["pool"]))
    price_field = "token1Price" if cfg["invert"] else "token0Price"
    price = float(data["pool"][price_field])
    if cfg.get("quote", "USDC") == "WETH":
        price *= get_spot("ETH")["price"]
    return _cache_put(key, SPOT_TTL_S, {
        "price": price,
        "asset": asset,
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


_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS1MO"


def parse_fred_csv(text: str) -> float:
    """Latest DGS1MO observation from fredgraph.csv (percent -> decimal APR).
    Missing observations are '.' — walk back to the last real value."""
    for line in reversed(text.strip().splitlines()):
        parts = line.split(",")
        if len(parts) == 2 and parts[1] not in (".", "", "DGS1MO", "VALUE"):
            try:
                return float(parts[1]) / 100.0
            except ValueError:
                continue
    raise ValueError("no numeric observation in FRED csv")


def _fred_rate() -> dict:
    resp = httpx.get(_FRED_CSV_URL, timeout=10.0, follow_redirects=True)
    resp.raise_for_status()
    return {
        "rate_cc": apr_to_cc(parse_fred_csv(resp.text)),
        "source": "fred-dgs1mo-cached",
        "observed_at": int(time.time()),
        "fallback_level": 1,
    }


def get_risk_free_rate() -> dict:
    """USDC borrow rate from Aave v3 (the desk's true financing rate — the
    payoff is stablecoin-settled). Fallback chain per spec:
    Aave subgraph (0) → cached FRED DGS1MO (1) → constant (2).
    OFFLINE_MODE goes straight to the constant (no network at all)."""
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
            try:
                return _cache_put("rate", RATE_TTL_S, _fred_rate())
            except Exception:
                pass  # fall through to constant
    return _cache_put("rate", RATE_TTL_S, {
        "rate_cc": apr_to_cc(config.RISK_FREE_RATE_CONSTANT),
        "source": "constant",
        "observed_at": int(time.time()),
        "fallback_level": 2,
    })
