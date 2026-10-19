"""Owner-only publisher routes: a remote caller cannot change prices, payout wallet, catalog or start a scan."""
import pytest
from fastapi.testclient import TestClient

ATTACKER = "0x000000000000000000000000000000000000dEaD"


@pytest.fixture
def remote():
    from gateway.main import app
    with TestClient(app, client=("203.0.113.7", 50000)) as c:
        yield c


@pytest.mark.parametrize("method, path, body", [
    ("post", "/publisher/wallet", {"wallet_address": ATTACKER}),
    ("put", "/publisher/rules", {"raw_text": "$0.10: one figure"}),
    ("post", "/publisher/rules/confirm", {}),
    ("post", "/publisher/activate", {}),
    ("post", "/publisher/scan", {"url": "http://169.254.169.254/latest/meta-data/"}),
    ("patch", "/publisher/catalog/rpt_battery_2025%23s2", {"status": "free"}),
])
def test_remote_caller_cannot_change_the_publisher(remote, method, path, body):
    assert getattr(remote, method)(path, json=body).status_code == 403


def test_payout_wallet_unchanged_after_remote_attempt(remote, client):
    client.post("/publisher/wallet", json={"wallet_address": "0x797486c95c00d40F30E41996b0DA5417fF256844"})
    remote.post("/publisher/wallet", json={"wallet_address": ATTACKER})
    from shared import db
    assert db.get_publisher()["wallet_address"] == "0x797486c95c00d40F30E41996b0DA5417fF256844"


def test_forwarded_header_does_not_make_a_remote_caller_local(remote):
    r = remote.post("/publisher/wallet", json={"wallet_address": ATTACKER}, headers={"X-Forwarded-For": "127.0.0.1"})
    assert r.status_code == 403


def test_owner_token_allows_a_remote_owner(monkeypatch, remote):
    monkeypatch.setenv("PUBLISHER_OWNER_TOKEN", "owner-secret-for-tests")
    assert remote.post("/publisher/wallet", json={"wallet_address": ATTACKER}).status_code == 403
    r = remote.post("/publisher/wallet", json={"wallet_address": ATTACKER}, headers={"X-Owner-Token": "owner-secret-for-tests"})
    assert r.status_code == 200


def test_preview_is_owner_only(remote, client):
    path = "/publisher/catalog/rpt_battery_2025%23s2/preview"
    assert remote.get(path).status_code == 403
    r = client.get(path)
    assert r.status_code == 200 and r.json()["text"]
    assert client.get("/publisher/catalog/nope%23s9/preview").status_code == 404


def test_reads_stay_public(remote):
    assert remote.get("/publisher/catalog").status_code == 200


def test_owner_token_rotation_accepts_old_and_new(monkeypatch, remote, payments_tmp):
    monkeypatch.setenv("PUBLISHER_OWNER_TOKEN", "new-token-0123456789,old-token-0123456789")
    for token in ("new-token-0123456789", "old-token-0123456789"):
        res = remote.get("/compliance/report", headers={"X-Owner-Token": token})
        assert res.status_code == 200


def test_expired_owner_token_is_refused(monkeypatch, remote):
    monkeypatch.setenv("PUBLISHER_OWNER_TOKEN", "new-token-0123456789")
    monkeypatch.setenv("PUBLISHER_OWNER_TOKEN_EXPIRES_AT", "2020-01-01")
    res = remote.get("/compliance/report", headers={"X-Owner-Token": "new-token-0123456789"})
    assert res.status_code == 403 and "expired" in res.json()["detail"]


def test_ipv4_mapped_loopback_counts_as_local():
    from shared.owner import is_loopback
    assert is_loopback("::ffff:127.0.0.1") and is_loopback("::1") and not is_loopback("203.0.113.7")


@pytest.fixture
def payments_tmp(tmp_path, monkeypatch):
    from payments import store
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "pay.db"))
