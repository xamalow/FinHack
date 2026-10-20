"""transactions table (owned by P3).

Replay protection lives here: nonce and offer_id are UNIQUE, so a second
attempt with the same EIP-3009 nonce or for the same offer fails at insert time,
before anything is sent to the facilitator.
"""
import json
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
);
CREATE TABLE IF NOT EXISTS license_receipts (
    tx_hash TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    receipt_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paid_route_requests (
    ts REAL NOT NULL,
    route TEXT NOT NULL,
    offer_id TEXT,
    session_id TEXT,
    status_code INTEGER NOT NULL
);
"""


class ReplayError(Exception):
    pass


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
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


def get_by_offer(offer_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE offer_id = ?", (offer_id,)).fetchone()
    return dict(row) if row else None


def get_by_hash(tx_hash):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE tx_hash = ?", (tx_hash.lower(),)).fetchone()
    return dict(row) if row else None


def list_all():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM transactions ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]


def record_request(route, offer_id, session_id, status_code):
    with _conn() as conn:
        conn.execute("INSERT INTO paid_route_requests VALUES (?, ?, ?, ?, ?)",
                     (time.time(), route, offer_id, session_id, status_code))


def stats():
    """Publisher dashboard numbers. Revenue counts settled transactions only."""
    with _conn() as conn:
        requests = conn.execute("SELECT COUNT(*) FROM paid_route_requests").fetchone()[0]
        by_status = dict(conn.execute(
            "SELECT status_code, COUNT(*) FROM paid_route_requests GROUP BY status_code").fetchall())
        paid, revenue, payers, last_ts = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_atomic), 0), COUNT(DISTINCT payer), MAX(ts) "
            "FROM transactions WHERE status = 'settled'").fetchone()
        by_amount = conn.execute(
            "SELECT amount_atomic, COUNT(*), SUM(amount_atomic) FROM transactions "
            "WHERE status = 'settled' GROUP BY amount_atomic ORDER BY amount_atomic").fetchall()
    return {
        "requests": requests,
        "paid_requests": paid,
        "refused_requests": sum(n for code, n in by_status.items() if code >= 400 and code != 402),
        "payment_required_sent": by_status.get(402, 0),
        "revenue_usdc": revenue / 1_000_000,
        "average_usdc": round(revenue / paid / 1_000_000, 6) if paid else 0.0,
        "unique_payers": payers,
        "last_sale_ts": last_ts,
        "by_price": [{"price_usdc": a / 1_000_000, "sales": n, "revenue_usdc": s / 1_000_000}
                     for a, n, s in by_amount],
    }


def save_receipt(tx_hash, offer_id, receipt):
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO license_receipts VALUES (?, ?, ?)", (tx_hash, offer_id, json.dumps(receipt)))


def get_receipt(tx_hash):
    with _conn() as conn:
        row = conn.execute("SELECT receipt_json FROM license_receipts WHERE tx_hash = ?", (tx_hash,)).fetchone()
    return json.loads(row["receipt_json"]) if row else None


def settled_sales():
    with _conn() as conn:
        rows = conn.execute("SELECT offer_id, payer, tx_hash, amount_atomic, ts FROM transactions "
                            "WHERE status = 'settled' ORDER BY ts").fetchall()
    return [dict(r) for r in rows]
