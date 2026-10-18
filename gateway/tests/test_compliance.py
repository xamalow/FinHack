"""Compliance controls: sanctions screening, audit chain, retention and erasure, signed manifest, owner-only reads."""
import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from gateway.main import app
from payments import store
from shared import audit_chain, db, retention, sanctions, signing
from shared.events import log_event

from .test_gateway import authed, headers, kya

LAZARUS = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"  # OFAC SDN (Ronin bridge hack), for the oracle test


@pytest.fixture(autouse=True)
def payments_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def oracle(monkeypatch):
    """Turns the oracle on with a fake chain: returns the set of sanctioned addresses to fill."""
    listed = set()
    monkeypatch.setenv("SANCTIONS_ORACLE", sanctions.DEFAULT_ORACLE)
    monkeypatch.setattr(sanctions, "_call_oracle", lambda address: address.lower() in listed)
    sanctions.clear_cache()
    yield listed
    sanctions.clear_cache()


def remote():
    return TestClient(app, client=("203.0.113.7", 40000))


# --- Sanctions -----------------------------------------------------------------


def test_kya_refuses_a_wallet_on_the_ofac_list(client, oracle):
    acct = Account.create()
    oracle.add(acct.address.lower())
    res = kya(client, acct, "sdn-bot")
    assert res.status_code == 403 and "OFAC" in res.json()["detail"]
    assert db.get_agent("sdn-bot")["status"] == "blocked"
    assert any(e["type"] == "sanctions_blocked" for e in db.list_events())


def test_kya_logs_a_passed_screening_in_the_session(client, oracle):
    acct = Account.create()
    _, sid = authed(client, acct)
    passed = [e for e in db.list_events(session_id=sid) if e["type"] == "sanctions_screened"]
    assert passed and passed[0]["payload"]["source"] == "chainalysis_oracle"


def test_oracle_down_fails_closed_on_mainnet_and_open_on_testnet(monkeypatch):
    monkeypatch.setenv("SANCTIONS_ORACLE", sanctions.DEFAULT_ORACLE)

    def down(_address):
        raise TimeoutError

    monkeypatch.setattr(sanctions, "_call_oracle", down)
    sanctions.clear_cache()
    monkeypatch.setenv("NETWORK", "eip155:8453")
    assert sanctions.screen(LAZARUS).blocked
    monkeypatch.setenv("NETWORK", "eip155:84532")
    result = sanctions.screen(LAZARUS)
    assert not result.blocked and result.source == "oracle_unavailable"


def test_sanctioned_payout_wallet_is_refused(client, oracle):
    wallet = Account.create().address
    oracle.add(wallet.lower())
    res = client.post("/publisher/wallet", json={"wallet_address": wallet})
    assert res.status_code == 403 and db.get_publisher().get("wallet_address") != wallet


# --- Audit chain ---------------------------------------------------------------


def _verify():
    with db.connect() as conn:
        return audit_chain.verify(conn)


def test_chain_is_valid_then_detects_edit_delete_and_insert():
    for i in range(3):
        log_event(None, "gateway", "request_received", f"event {i}", {"i": i})
    assert _verify()["ok"] and _verify()["checked"] == 3

    first = db.list_events()[0]["event_id"]
    db.execute("UPDATE events SET summary = 'edited' WHERE event_id = ?", (first,))
    assert "event content changed" in str(_verify()["problems"])

    db.execute("DELETE FROM events WHERE event_id = ?", (first + 1,))
    assert "event deleted" in str(_verify()["problems"])

    db.execute("INSERT INTO events (ts, actor, type, summary, payload_json) VALUES ('x', 'gateway', 'kya_verified', 'forged', '{}')")
    assert "event inserted outside the chain" in str(_verify()["problems"])


def test_audit_head_is_public_and_full_check_is_owner_only(client):
    log_event(None, "gateway", "request_received", "one", {})
    assert remote().get("/compliance/audit-head").json()["chain_hash"] != audit_chain.GENESIS
    assert remote().get("/compliance/audit-chain").status_code == 403
    assert client.get("/compliance/audit-chain").json()["ok"]


# --- Retention and erasure ------------------------------------------------------


def test_purge_erases_old_conversations_and_keeps_the_chain_valid(client):
    acct = Account.create()
    h, sid = authed(client, acct)
    db.add_message(sid, "buyer", "my name is Alice, I need lithium prices")
    log_event(sid, "buyer", "buyer_message", "my name is Alice", {"message": "my name is Alice"})
    old = "2020-01-01T00:00:00.000Z"
    db.execute("UPDATE messages SET ts = ?", (old,))
    db.execute("UPDATE events SET ts = ? WHERE type = 'buyer_message'", (old,))
    with db.connect() as conn:  # rebuild the chain as if those events had been written in 2020
        conn.execute("DELETE FROM audit_chain")
        for e in conn.execute("SELECT event_id, ts, session_id, actor, type, summary, payload_json FROM events ORDER BY event_id").fetchall():
            audit_chain.append(conn, *e)

    result = retention.purge(30)
    assert result["messages_deleted"] == 1 and result["events_redacted"] == 1
    assert db.list_messages(sid) == []
    assert "Alice" not in str(db.list_events())
    assert _verify()["ok"] and _verify()["redacted"] == 1


def test_erasure_request_removes_messages_but_keeps_financial_records(client):
    acct = Account.create()
    _, sid = authed(client, acct)
    db.add_message(sid, "buyer", "private question")
    res = client.post("/compliance/erase", json={"wallet": acct.address})
    assert res.status_code == 200 and res.json()["messages_deleted"] == 1
    assert db.list_messages(sid) == [] and _verify()["ok"]
    assert remote().post("/compliance/erase", json={"wallet": acct.address}).status_code == 403


# --- Signed manifest and owner-only reads ----------------------------------------


def test_manifest_is_signed_by_the_publisher_key(client):
    db.update_publisher(wallet_address=Account.create().address, activated_at=db.now_iso())
    manifest = client.get("/.well-known/ai-data.json").json()
    ok, signer, _ = signing.verify_manifest(manifest)
    assert ok and signer == signing.publisher_account().address
    manifest["payment"]["pay_to"] = Account.create().address  # what an attacker in the middle would change
    assert not signing.verify_manifest(manifest)[0]


@pytest.mark.parametrize("path", ["/events", "/transactions", "/publisher/stats", "/compliance/report", "/audit/off_x"])
def test_dashboards_holding_buyer_data_are_owner_only(client, path):
    assert remote().get(path).status_code == 403
    assert client.get(path).status_code in (200, 404)


def test_security_headers_on_gateway_responses(client):
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff" and res.headers["X-Frame-Options"] == "DENY"
    assert remote().get("/compliance/signer").headers.get("Cache-Control") == "no-store"
