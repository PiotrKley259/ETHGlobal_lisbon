"""I1.2 tests: non-chat endpoints offline via TestClient. The /chat SSE path
needs a live Anthropic call and is exercised by the manual smoke script.
"""
import pytest
from fastapi.testclient import TestClient

import app as app_module
import config
from graph import subgraph


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    subgraph.clear_cache()
    app_module._last_panel = None
    app_module._state = app_module.default_state()


client = TestClient(app_module.app)


def test_health():
    body = client.get("/health").json()
    assert body["ok"] is True


def test_panel_hydration_offline():
    p = client.get("/panel").json()
    assert p["spot"]["price"] > 100
    assert len(p["vols"]) == 3
    assert p["regime"]["regime"] in ("calm", "elevated", "stressed")
    assert p["quote"] is None and p["strategy"] is None


def test_settings_roundtrip_updates_panel_bands():
    r = client.post("/settings", json={"regime_bands": {"calm": 0.2, "elevated": 0.9}})
    assert r.status_code == 200
    assert r.json()["regime_bands"] == {"calm": 0.2, "elevated": 0.9}
    assert client.get("/panel").json()["regime"]["bands"] == {
        "calm": 0.2, "elevated": 0.9}


def test_settings_validation():
    r = client.post("/settings", json={"regime_bands": {"calm": 0.9, "elevated": 0.2}})
    assert r.status_code == 422
