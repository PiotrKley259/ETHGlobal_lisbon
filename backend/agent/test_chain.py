"""I2.2/I2.3 tests: the full chain lifecycle against a faked sidecar —
mint (coverage-gated) -> arm -> worker settles at expiry, exposure released.
Also fixes the declared-vs-dispatched tool parity check to include chain tools.
"""
import time

import pytest

import config
from agent import risk, settlement, sidecar, tools
from graph import subgraph


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    subgraph.clear_cache()
    risk.reset_ledger()
    settlement.reset_registry()
    yield
    risk.reset_ledger()
    settlement.reset_registry()


@pytest.fixture()
def fake_sidecar(monkeypatch):
    calls = {"minted": [], "logged": [], "scheduled": [], "executed": []}
    monkeypatch.setattr(risk, "treasury_balance_usd", lambda: 50_000.0)
    monkeypatch.setattr(sidecar, "mint_series", lambda symbol, name, option: (
        calls["minted"].append((symbol, option)) or {
            "token_id": f"0.0.{5000 + len(calls['minted'])}", "tx_id": "0.0.1-1-1",
            "hashscan_url": "https://hashscan.io/testnet/token/x"}))
    monkeypatch.setattr(sidecar, "hcs_log", lambda kind, payload: (
        calls["logged"].append((kind, payload)) or {
            "topic_id": "0.0.42", "sequence_number": len(calls["logged"]),
            "tx_id": "t", "hashscan_url": "h"}))
    monkeypatch.setattr(sidecar, "schedule_settlement", lambda token_id, expiry_ts, cap: (
        calls["scheduled"].append(token_id) or {
            "schedule_id": "0.0.777", "status": "armed", "hashscan_url": "h"}))
    monkeypatch.setattr(sidecar, "execute_settlement", lambda token_id, payout, spot: (
        calls["executed"].append((token_id, payout)) or {
            "tx_id": "settle-tx", "hashscan_url": "h", "paid_usd": payout}))
    return calls


def test_mint_registers_exposure_and_series(fake_sidecar):
    state = tools.default_state()
    result = tools.dispatch("mint_option", {
        "type": "put", "K": 1770.0, "qty": 1.0, "expiry_minutes": 3}, state)
    assert result["token_id"].startswith("0.0.")
    assert risk.open_exposure_usd() == 1770.0  # put reserves K*qty
    assert len(settlement.open_series()) == 1
    assert tools.chain_event("mint_option", result)["kind"] == "mint"
    assert tools.chain_event("mint_option", result)["status"] == "ok"


def test_mint_refused_when_uncovered(monkeypatch, fake_sidecar):
    monkeypatch.setattr(risk, "treasury_balance_usd", lambda: 100.0)
    state = tools.default_state()
    with pytest.raises(ValueError, match="mint refused"):
        tools.dispatch("mint_option", {
            "type": "put", "K": 1770.0, "expiry_minutes": 3}, state)
    assert fake_sidecar["minted"] == []  # refusal happens before any chain call
    assert risk.open_exposure_usd() == 0.0


def test_arm_then_worker_settles_put_at_expiry(fake_sidecar):
    state = tools.default_state()
    minted = tools.dispatch("mint_option", {
        "type": "put", "K": 1900.0, "qty": 1.0, "expiry_minutes": 0.001}, state)
    token = minted["token_id"]
    tools.dispatch("arm_settlement", {"token_id": token}, state)
    assert fake_sidecar["scheduled"] == [token]

    events = settlement.execute_due(now=time.time() + 60)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "settle" and ev["status"] == "paid"
    # fixture spot ~1858 -> put K=1900 pays ~K - S
    token_paid, payout = fake_sidecar["executed"][0]
    assert token_paid == token
    assert payout == pytest.approx(1900.0 - 1858.02, abs=1.0)
    assert risk.open_exposure_usd() == 0.0  # exposure released
    # idempotent client-side: second sweep does nothing
    assert settlement.execute_due(now=time.time() + 120) == []


def test_unarmed_or_unexpired_series_not_settled(fake_sidecar):
    state = tools.default_state()
    tools.dispatch("mint_option", {
        "type": "call", "K": 1800.0, "expiry_minutes": 0.001}, state)  # never armed
    tools.dispatch("mint_option", {
        "type": "call", "K": 1810.0, "expiry_minutes": 999}, state)
    tools.dispatch("arm_settlement",
                   {"token_id": settlement.open_series()[1]["token_id"]}, state)
    assert settlement.execute_due(now=time.time() + 60) == []
    assert fake_sidecar["executed"] == []


def test_arm_unknown_series_raises(fake_sidecar):
    with pytest.raises(ValueError, match="mint it first"):
        tools.dispatch("arm_settlement", {"token_id": "0.0.99999"},
                       tools.default_state())


def test_log_trade_chain_event(fake_sidecar):
    result = tools.dispatch("log_trade", {
        "kind": "trade", "payload": {"symbol": "OPT-P-1770"}}, tools.default_state())
    ev = tools.chain_event("log_trade", result)
    assert ev["kind"] == "hcs" and "#1" in ev["label"]
