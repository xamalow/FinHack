"""Stuck payment recovery and paid-route rate limit.  Run: .venv/bin/python -m pytest payments/tests -q"""
import asyncio
import time

import pytest

from payments import recovery, router, store

PAYER = "0x" + "ab" * 20
NONCE = "0x" + "cd" * 32


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))


def chain(monkeypatch, used, tx_hash=None):
    async def authorization_used(payer, nonce):
        return used

    async def find_authorization_tx(payer, nonce):
        return tx_hash

    monkeypatch.setattr(recovery, "authorization_used", authorization_used)
    monkeypatch.setattr(recovery, "find_authorization_tx", find_authorization_tx)


def pending_row(age_s=0):
    tx_id = store.reserve("off_1", NONCE, PAYER, "0x" + "ef" * 20, 100_000)
    with store._conn() as conn:
        conn.execute("UPDATE transactions SET ts = ? WHERE tx_id = ?", (time.time() - age_s, tx_id))
    return store.get_by_offer("off_1")


def test_paid_on_chain_is_marked_settled(monkeypatch):
    chain(monkeypatch, used=True, tx_hash="0x" + "12" * 32)
    state, tx_hash = asyncio.run(recovery.reconcile(pending_row()))
    assert state == "settled" and tx_hash == "0x" + "12" * 32
    assert store.get_by_offer("off_1")["status"] == "settled"


def test_unused_and_expired_is_released(monkeypatch):
    chain(monkeypatch, used=False)
    state, _ = asyncio.run(recovery.reconcile(pending_row(age_s=recovery.EXPIRY_SECONDS + 1)))
    assert state == "released" and store.get_by_offer("off_1") is None


def test_unused_but_recent_stays_pending(monkeypatch):
    chain(monkeypatch, used=False)
    state, _ = asyncio.run(recovery.reconcile(pending_row(age_s=10)))
    assert state == "pending" and store.get_by_offer("off_1")["status"] == "pending"


def test_used_but_tx_not_found_stays_pending(monkeypatch):
    chain(monkeypatch, used=True, tx_hash=None)
    state, _ = asyncio.run(recovery.reconcile(pending_row()))
    assert state == "pending"


def test_rate_limit_per_key(monkeypatch):
    monkeypatch.setattr(router, "RATE_LIMIT_PER_MIN", 3)
    router._hits.clear()
    assert [router.rate_limited("ses_a") for _ in range(4)] == [False, False, False, True]
    assert router.rate_limited("ses_b") is False
