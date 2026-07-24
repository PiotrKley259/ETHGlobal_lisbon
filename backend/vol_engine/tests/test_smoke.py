"""Scaffold smoke test: config loads, fixtures are present and parseable."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import config  # noqa: E402


def test_config_loads():
    assert config.ETH_USDC_POOL.startswith("0x")
    assert 0 < config.RISK_FREE_RATE_CONSTANT < 0.2


def test_fixtures_present_and_valid():
    candles = json.loads(
        (config.FIXTURES_DIR / "pool_hour_datas.json").read_text()
    )["data"]["poolHourDatas"]
    spot = json.loads((config.FIXTURES_DIR / "spot.json").read_text())
    assert len(candles) == 720
    assert 100 < float(spot["data"]["pool"]["token0Price"]) < 100_000
