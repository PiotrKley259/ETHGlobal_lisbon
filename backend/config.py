"""Central config: every secret and setting comes from env, loaded once here.

Never read os.environ elsewhere; import from this module instead.
Var names are frozen in docs/CONTRACTS.md §5.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"

load_dotenv(REPO_ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GRAPH_API_KEY = os.getenv("GRAPH_API_KEY", "")
UNISWAP_SUBGRAPH_ID = os.getenv(
    "UNISWAP_SUBGRAPH_ID", "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
)
AAVE_SUBGRAPH_ID = os.getenv(
    "AAVE_SUBGRAPH_ID", "Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g"
)
ETH_USDC_POOL = os.getenv(
    "ETH_USDC_POOL", "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
).lower()

# Asset registry: every Uniswap v3 <TOKEN>/USDC pool the desk quotes.
# `invert` says whether poolHourData OHLC (which tracks token0Price) must be
# flipped to get USD: False when USDC is token0 (candles already USD, e.g.
# ETH), True when the token is token0 (candles are TOKEN-per-USDC, e.g. WBTC
# pool 0x99ac... where close ~0.0000156 -> 1/close ~= $63,917). Verified
# live 2026-07-25; see CONTRACTS §6.
ASSETS: dict[str, dict] = {
    "ETH": {"pool": ETH_USDC_POOL, "invert": False, "fixture_suffix": ""},
    "WBTC": {
        "pool": "0x99ac8ca7087fa4a2a1fb6357269965a2014abc35",
        "invert": True,
        "fixture_suffix": "_wbtc",
    },
    # WETH-quoted pools (deepest venues for these assets): candles are priced
    # in WETH and crossed with the ETH/USDC series -> USD. All three have the
    # asset as token0 (invert) — verified live 2026-07-25. WDOGE was evaluated
    # and REJECTED: 86% of hours have no trades (744 candles span 7.5 months).
    "LINK": {
        "pool": "0xa6cc3c2531fdaa6ae1a3ca84c2855806728693e8",
        "invert": True, "quote": "WETH", "fixture_suffix": "_link",
    },
    "UNI": {
        "pool": "0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801",
        "invert": True, "quote": "WETH", "fixture_suffix": "_uni",
    },
    "AAVE": {
        "pool": "0x5ab53ee1d50eef2c1dd3d5402789cd27bb52c1bb",
        "invert": True, "quote": "WETH", "fixture_suffix": "_aave",
    },
}
DEFAULT_ASSET = "ETH"
SIDECAR_URL = os.getenv("SIDECAR_URL", "http://localhost:7070")
RISK_FREE_RATE_CONSTANT = float(os.getenv("RISK_FREE_RATE_CONSTANT", "0.04"))
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "0") == "1"

GRAPH_GATEWAY = "https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph}"
