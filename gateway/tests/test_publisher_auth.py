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


def test_reads_stay_public(remote):
    assert remote.get("/publisher/catalog").status_code == 200
