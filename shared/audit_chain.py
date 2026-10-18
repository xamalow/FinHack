"""Tamper-evident audit log: every event is chained to the previous one by SHA-256.

For each event, in the same SQLite transaction as the insert (BEGIN IMMEDIATE, so the gateway and the
MCP connector writing the same file cannot interleave):
    content_hash = sha256(canonical event: ts, session_id, actor, type, summary, payload_json)
    chain_hash   = sha256(prev_chain_hash + event_id + content_hash)

verify() recomputes everything: an edited, deleted or inserted event breaks the chain from that point.
head() is the latest chain hash; publishing it (or writing it on-chain, scripts/anchor_audit.py) freezes
the whole history up to that event.

Personal data can still be erased (shared/retention.py): a redacted event keeps its stored content_hash,
so the chain stays verifiable while the text is gone.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_chain (
    event_id      INTEGER PRIMARY KEY,
    content_hash  TEXT NOT NULL,
    chain_hash    TEXT NOT NULL,
    redacted      INTEGER NOT NULL DEFAULT 0
);
"""


def content_hash(ts, session_id, actor, type_, summary, payload_json) -> str:
    body = json.dumps([ts, session_id, actor, type_, summary, payload_json], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def link(prev: str, event_id: int, c_hash: str) -> str:
    return hashlib.sha256(f"{prev}{event_id}{c_hash}".encode()).hexdigest()


def append(conn: sqlite3.Connection, event_id: int, ts, session_id, actor, type_, summary, payload_json) -> str:
    row = conn.execute("SELECT chain_hash FROM audit_chain ORDER BY event_id DESC LIMIT 1").fetchone()
    prev = row[0] if row else GENESIS
    c_hash = content_hash(ts, session_id, actor, type_, summary, payload_json)
    chained = link(prev, event_id, c_hash)
    conn.execute("INSERT INTO audit_chain (event_id, content_hash, chain_hash) VALUES (?, ?, ?)",
                 (event_id, c_hash, chained))
    return chained


def verify(conn: sqlite3.Connection) -> dict:
    chain = conn.execute("SELECT event_id, content_hash, chain_hash, redacted FROM audit_chain ORDER BY event_id").fetchall()
    if not chain:
        return {"ok": True, "checked": 0, "head": GENESIS, "first_event_id": None, "redacted": 0, "problems": []}
    first = chain[0][0]
    events = {r[0]: r for r in conn.execute(
        "SELECT event_id, ts, session_id, actor, type, summary, payload_json FROM events WHERE event_id >= ?", (first,))}
    problems, prev = [], GENESIS
    chained_ids = set()
    for event_id, stored_content, stored_chain, redacted in chain:
        chained_ids.add(event_id)
        event = events.get(event_id)
        if event is None:
            problems.append({"event_id": event_id, "problem": "event deleted"})
        elif not redacted and content_hash(*event[1:]) != stored_content:
            problems.append({"event_id": event_id, "problem": "event content changed"})
        if link(prev, event_id, stored_content) != stored_chain:
            problems.append({"event_id": event_id, "problem": "chain link broken (audit row edited or removed)"})
        prev = stored_chain
    for event_id in sorted(set(events) - chained_ids):
        problems.append({"event_id": event_id, "problem": "event inserted outside the chain"})
    return {"ok": not problems, "checked": len(chain), "first_event_id": first, "head": prev,
            "redacted": sum(1 for r in chain if r[3]), "problems": problems[:50]}


def head(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT event_id, chain_hash FROM audit_chain ORDER BY event_id DESC LIMIT 1").fetchone()
    return {"event_id": row[0], "chain_hash": row[1]} if row else {"event_id": None, "chain_hash": GENESIS}
