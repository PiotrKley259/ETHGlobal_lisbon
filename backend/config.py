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
SIDECAR_URL = os.getenv("SIDECAR_URL", "http://localhost:7070")
RISK_FREE_RATE_CONSTANT = float(os.getenv("RISK_FREE_RATE_CONSTANT", "0.04"))
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "0") == "1"

GRAPH_GATEWAY = "https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph}"
