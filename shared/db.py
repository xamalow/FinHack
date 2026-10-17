"""SQLite access shared by every role (agent.md 6.1). Owned by P2.

One file, one connection per call. Every role reads and writes its tables
through these helpers, so the schema stays in one place.

Timestamps are ISO 8601 UTC strings with milliseconds (`2026-10-18T14:02:11.482Z`).
They sort and compare correctly as plain strings. Exception: `transactions.ts`
is a Unix epoch float, as P3 (its owner) writes it.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional

from shared.config import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (
    content_id      TEXT PRIMARY KEY,
    report_id       TEXT NOT NULL,
    title           TEXT NOT NULL,
    section         TEXT NOT NULL,
    topic           TEXT NOT NULL,
    region          TEXT NOT NULL,
    period          TEXT NOT NULL,
    data_types      TEXT NOT NULL DEFAULT '[]',
    sensitivity     TEXT NOT NULL DEFAULT 'proprietary',
    status          TEXT NOT NULL DEFAULT 'sellable'
                    CHECK (status IN ('sellable', 'free', 'excluded')),
    suggested_tier  TEXT
);

CREATE TABLE IF NOT EXISTS content (
    content_id  TEXT PRIMARY KEY,
    raw_text    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules (
    rules_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text    TEXT NOT NULL,
    tiers_json  TEXT NOT NULL,
    confirmed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publisher (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    name            TEXT,
    site_url        TEXT,
    wallet_address  TEXT,
    activated_at    TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    wallet_address  TEXT NOT NULL,
    status          TEXT NOT NULL,
    first_seen      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kya_challenges (
    nonce           TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    wallet_address  TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    used            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    token_expires_at  TEXT NOT NULL,
    rounds            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('buyer', 'sales_agent')),
    content     TEXT NOT NULL,
    ts          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offers (
    offer_id     TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    content_ids  TEXT NOT NULL,
    scope        TEXT NOT NULL,
    tier         TEXT NOT NULL,
    price_usdc   REAL NOT NULL,
    license      TEXT NOT NULL,
    status       TEXT NOT NULL
                 CHECK (status IN ('proposed', 'accepted', 'paid', 'expired', 'rejected')),
    expires_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id          TEXT PRIMARY KEY,
    offer_id       TEXT NOT NULL UNIQUE,
    payer          TEXT NOT NULL,
    pay_to         TEXT NOT NULL,
    amount_atomic  INTEGER NOT NULL,
    nonce          TEXT NOT NULL UNIQUE,
    tx_hash        TEXT,
    status         TEXT NOT NULL,
    ts             REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    session_id    TEXT,
    actor         TEXT NOT NULL,
    type          TEXT NOT NULL,
    summary       TEXT NOT NULL,
    payload_json  TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_offers_session ON offers(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
"""

# Columns stored as JSON text, decoded on read.
_JSON_COLUMNS = {"data_types", "content_ids", "tiers_json", "payload_json"}


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def now_iso() -> str:
    return iso(utcnow())


def iso_in(seconds: int) -> str:
    return iso(utcnow() + timedelta(seconds=seconds))


def today_prefix() -> str:
    """`YYYY-MM-DD` of today in UTC, for `ts LIKE 'prefix%'` daily counts."""
    return utcnow().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for key in _JSON_COLUMNS & out.keys():
        if isinstance(out[key], str):
            out[key] = json.loads(out[key])
    return out


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def fetch_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return _decode(row) if row else None


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_decode(r) for r in rows]


def execute(sql: str, params: tuple = ()) -> int:
    """Run a write statement. Returns lastrowid (inserts) or rowcount (updates)."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else cur.rowcount


# ---------------------------------------------------------------------------
# Catalog and content (P1 writes, everyone reads)
# ---------------------------------------------------------------------------


def upsert_catalog_item(item: dict[str, Any]) -> None:
    execute(
        """INSERT INTO catalog (content_id, report_id, title, section, topic, region, period,
                                data_types, sensitivity, status, suggested_tier)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(content_id) DO UPDATE SET
             report_id=excluded.report_id, title=excluded.title, section=excluded.section,
             topic=excluded.topic, region=excluded.region, period=excluded.period,
             data_types=excluded.data_types, sensitivity=excluded.sensitivity,
             status=excluded.status, suggested_tier=excluded.suggested_tier""",
        (
            item["content_id"], item["report_id"], item["title"], item["section"],
            item["topic"], item["region"], item["period"],
            json.dumps(item.get("data_types", [])), item.get("sensitivity", "proprietary"),
            item.get("status", "sellable"), item.get("suggested_tier"),
        ),
    )


def list_catalog() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM catalog ORDER BY content_id")


def set_content(content_id: str, raw_text: str) -> None:
    execute(
        "INSERT INTO content (content_id, raw_text) VALUES (?, ?) "
        "ON CONFLICT(content_id) DO UPDATE SET raw_text=excluded.raw_text",
        (content_id, raw_text),
    )


def get_content_rows(content_ids: list[str]) -> list[dict[str, Any]]:
    if not content_ids:
        return []
    marks = ",".join("?" * len(content_ids))
    return fetch_all(f"SELECT * FROM content WHERE content_id IN ({marks})", tuple(content_ids))


# ---------------------------------------------------------------------------
# Rules and publisher (P2)
# ---------------------------------------------------------------------------


def insert_rules(raw_text: str, tiers: list[dict[str, Any]]) -> int:
    return execute(
        "INSERT INTO rules (raw_text, tiers_json, confirmed, created_at) VALUES (?, ?, 0, ?)",
        (raw_text, json.dumps(tiers), now_iso()),
    )


def latest_rules() -> Optional[dict[str, Any]]:
    return fetch_one("SELECT * FROM rules ORDER BY rules_id DESC LIMIT 1")


def confirmed_rules() -> Optional[dict[str, Any]]:
    return fetch_one("SELECT * FROM rules WHERE confirmed = 1 ORDER BY rules_id DESC LIMIT 1")


def confirm_rules(rules_id: int, tiers: list[dict[str, Any]]) -> None:
    execute(
        "UPDATE rules SET confirmed = 1, tiers_json = ? WHERE rules_id = ?",
        (json.dumps(tiers), rules_id),
    )


def get_publisher() -> dict[str, Any]:
    row = fetch_one("SELECT * FROM publisher WHERE id = 1")
    return row or {"id": 1, "name": None, "site_url": None, "wallet_address": None, "activated_at": None}


def update_publisher(**fields: Any) -> None:
    allowed = {"name", "site_url", "wallet_address", "activated_at"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    execute("INSERT OR IGNORE INTO publisher (id) VALUES (1)")
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        execute(f"UPDATE publisher SET {sets} WHERE id = 1", tuple(fields.values()))


# ---------------------------------------------------------------------------
# Agents, KYA challenges, sessions, messages (P2)
# ---------------------------------------------------------------------------


def get_agent(agent_id: str) -> Optional[dict[str, Any]]:
    return fetch_one("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))


def upsert_agent(agent_id: str, wallet_address: str, status: str) -> None:
    execute(
        "INSERT INTO agents (agent_id, wallet_address, status, first_seen) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(agent_id) DO UPDATE SET status = excluded.status",
        (agent_id, wallet_address, status, now_iso()),
    )


def insert_challenge(nonce: str, agent_id: str, wallet_address: str, expires_at: str) -> None:
    execute(
        "INSERT INTO kya_challenges (nonce, agent_id, wallet_address, expires_at) VALUES (?, ?, ?, ?)",
        (nonce, agent_id, wallet_address, expires_at),
    )


def consume_challenge(nonce: str) -> Optional[dict[str, Any]]:
    """Atomically mark a challenge as used. Returns it only on first use."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM kya_challenges WHERE nonce = ?", (nonce,)).fetchone()
        if not row or row["used"]:
            return None
        cur = conn.execute("UPDATE kya_challenges SET used = 1 WHERE nonce = ? AND used = 0", (nonce,))
        if cur.rowcount != 1:
            return None
    return _decode(row)


def insert_session(session_id: str, agent_id: str, token_expires_at: str) -> None:
    execute(
        "INSERT INTO sessions (session_id, agent_id, token_expires_at, rounds) VALUES (?, ?, ?, 0)",
        (session_id, agent_id, token_expires_at),
    )


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    return fetch_one("SELECT * FROM sessions WHERE session_id = ?", (session_id,))


def increment_rounds(session_id: str) -> int:
    execute("UPDATE sessions SET rounds = rounds + 1 WHERE session_id = ?", (session_id,))
    row = get_session(session_id)
    return row["rounds"] if row else 0


def add_message(session_id: str, role: str, content: str) -> None:
    execute(
        "INSERT INTO messages (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now_iso()),
    )


def list_messages(session_id: str) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT session_id, role, content, ts FROM messages WHERE session_id = ? ORDER BY message_id",
        (session_id,),
    )


# ---------------------------------------------------------------------------
# Offers (P2 writes proposed/accepted, P3 writes paid)
# ---------------------------------------------------------------------------


def insert_offer(offer: dict[str, Any]) -> None:
    execute(
        """INSERT INTO offers (offer_id, session_id, content_ids, scope, tier, price_usdc,
                               license, status, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            offer["offer_id"], offer["session_id"], json.dumps(offer["content_ids"]),
            offer["scope"], offer["tier"], offer["price_usdc"], offer["license"],
            offer["status"], offer["expires_at"], now_iso(),
        ),
    )


def get_offer(offer_id: str) -> Optional[dict[str, Any]]:
    return fetch_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))


def update_offer_status(
    offer_id: str, status: str, expires_at: Optional[str] = None, expected_status: Optional[str] = None
) -> bool:
    """Change an offer status. With `expected_status`, only succeeds from that state."""
    sql = "UPDATE offers SET status = ?"
    params: list[Any] = [status]
    if expires_at:
        sql += ", expires_at = ?"
        params.append(expires_at)
    sql += " WHERE offer_id = ?"
    params.append(offer_id)
    if expected_status:
        sql += " AND status = ?"
        params.append(expected_status)
    return execute(sql, tuple(params)) == 1


def offers_for_agent_today(agent_id: str, statuses: tuple[str, ...]) -> list[dict[str, Any]]:
    marks = ",".join("?" * len(statuses))
    return fetch_all(
        f"""SELECT o.* FROM offers o JOIN sessions s ON s.session_id = o.session_id
            WHERE s.agent_id = ? AND o.status IN ({marks}) AND o.created_at LIKE ?
            ORDER BY o.created_at""",
        (agent_id, *statuses, f"{today_prefix()}%"),
    )


def list_offers(session_id: str) -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM offers WHERE session_id = ? ORDER BY created_at", (session_id,))


# ---------------------------------------------------------------------------
# Transactions (P3 writes, P2 reads for audit)
# ---------------------------------------------------------------------------


def transactions_for_offer(offer_id: str) -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM transactions WHERE offer_id = ? ORDER BY ts", (offer_id,))


# ---------------------------------------------------------------------------
# Events (written through shared.events.log_event only)
# ---------------------------------------------------------------------------


def insert_event(ts: str, session_id: Optional[str], actor: str, type_: str, summary: str, payload: dict) -> int:
    return execute(
        "INSERT INTO events (ts, session_id, actor, type, summary, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, session_id, actor, type_, summary, json.dumps(payload, default=str)),
    )


def list_events(session_id: Optional[str] = None, after_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
    if session_id:
        rows = fetch_all(
            "SELECT * FROM events WHERE session_id = ? AND event_id > ? ORDER BY event_id LIMIT ?",
            (session_id, after_id, limit),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM events WHERE event_id > ? ORDER BY event_id LIMIT ?", (after_id, limit)
        )
    for r in rows:
        r["payload"] = r.pop("payload_json")
    return rows
