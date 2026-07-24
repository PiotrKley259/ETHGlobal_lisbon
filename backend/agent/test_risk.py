"""I2.1 tests: coverage gate against a mocked sidecar (no network)."""
import httpx
import pytest

from agent import risk


@pytest.fixture(autouse=True)
def clean_ledger():
    risk.reset_ledger()
    yield
    risk.reset_ledger()


def mock_balance(monkeypatch, usd: float):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hbar": 100.0, "stablecoin_usd": usd}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())


def test_ok_when_covered(monkeypatch):
    mock_balance(monkeypatch, 50_000.0)
    c = risk.check_coverage(800.0)
    assert c["ok"] is True
    assert c["treasury_balance_usd"] == 50_000.0
    assert c["open_exposure_usd"] == 0.0


def test_series_cap_enforced(monkeypatch):
    mock_balance(monkeypatch, 1_000_000.0)
    c = risk.check_coverage(risk.SERIES_CAP_USD + 1)
    assert c["ok"] is False and "cap" in c["reason"]


def test_open_exposure_accumulates_until_released(monkeypatch):
    mock_balance(monkeypatch, 10_000.0)
    risk.register_exposure("0.0.111", 6_000.0)
    assert risk.check_coverage(5_000.0)["ok"] is False  # 6k + 5k > 10k
    risk.release_exposure("0.0.111")
    assert risk.check_coverage(5_000.0)["ok"] is True


def test_fails_closed_when_sidecar_down(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", boom)
    c = risk.check_coverage(100.0)
    assert c["ok"] is False and "unreachable" in c["reason"]


def test_max_payout_rule():
    assert risk.compute_max_payout("put", 1770.0, 2.0) == 3540.0
    assert risk.compute_max_payout("put", 90_000.0, 1.0) == risk.SERIES_CAP_USD
    assert risk.compute_max_payout("call", 1860.0, 1.0) == risk.SERIES_CAP_USD
