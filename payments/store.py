"""transactions table (owned by P3, agent.md 6.1).

Replay protection lives here: nonce and offer_id are UNIQUE, so a second
attempt with the same EIP-3009 nonce or for the same offer fails at insert time,
before anything is sent to the facilitator.
"""
import sqlite3
import time
import uuid

from payments.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    tx_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL UNIQUE,
    payer TEXT NOT NULL,
    pay_to TEXT NOT NULL,
    amount_atomic INTEGER NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    tx_hash TEXT,
    status TEXT NOT NULL,
    ts REAL NOT NULL
)
"""


class ReplayError(Exception):
    pass


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def reserve(offer_id, nonce, payer, pay_to, amount_atomic):
    tx_id = "tx_" + uuid.uuid4().hex[:12]
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, NULL, 'pending', ?)",
                (tx_id, offer_id, payer.lower(), pay_to.lower(), amount_atomic, nonce.lower(), time.time()),
            )
    except sqlite3.IntegrityError as e:
        raise ReplayError(str(e))
    return tx_id


def release(tx_id):
    """Drop a reservation whose verify or settle failed, so the buyer can retry with a new signature."""
    with _conn() as conn:
        conn.execute("DELETE FROM transactions WHERE tx_id = ? AND status = 'pending'", (tx_id,))


def mark_settled(tx_id, tx_hash):
    with _conn() as conn:
        conn.execute(
            "UPDATE transactions SET status = 'settled', tx_hash = ?, ts = ? WHERE tx_id = ?",
            (tx_hash.lower(), time.time(), tx_id),
        )


def offer_consumed(offer_id):
    with _conn() as conn:
        row = conn.execute("SELECT 1 FROM transactions WHERE offer_id = ?", (offer_id,)).fetchone()
    return row is not None


def get_by_hash(tx_hash):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE tx_hash = ?", (tx_hash.lower(),)).fetchone()
    return dict(row) if row else None


def list_all():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM transactions ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]
