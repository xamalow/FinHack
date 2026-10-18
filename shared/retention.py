"""Personal data retention and erasure (GDPR art. 5(1)(e) storage limitation, art. 17 erasure).

What is personal here: the free text agents send (missions, buyer messages, the Sales agent's replies
and the LLM outputs quoting them). It is kept PERSONAL_DATA_RETENTION_DAYS (default 30) for disputes and
abuse review, then erased: message rows deleted, event text replaced by a redaction marker. The audit
chain stays verifiable (shared/audit_chain.py keeps the hash of what was there).

What is kept: offers, transactions, license receipts, wallet addresses and payment events. They are the
record of a financial transaction and its license, kept for accounting and AML record keeping
(5 years under EU AMLD art. 40), which is a legal obligation (GDPR art. 6(1)(c), art. 17(3)(b)).
"""
from __future__ import annotations

import os
from datetime import timedelta

from shared import db

PERSONAL_EVENT_TYPES = (
    "buyer_message", "sales_message", "injection_ignored", "offer_rejected", "offer_evaluated",
    "mission_started", "discover_called", "no_match",
)
REDACTED_SUMMARY = "[personal data erased]"
REDACTED_PAYLOAD = '{"redacted": true}'


def retention_days() -> int:
    return int(os.getenv("PERSONAL_DATA_RETENTION_DAYS", "30"))


def _redact(conn, where: str, params: tuple) -> int:
    types = ",".join("?" * len(PERSONAL_EVENT_TYPES))
    ids = [r[0] for r in conn.execute(
        f"SELECT event_id FROM events WHERE type IN ({types}) AND payload_json != ? AND {where}",
        (*PERSONAL_EVENT_TYPES, REDACTED_PAYLOAD, *params))]
    for event_id in ids:
        conn.execute("UPDATE events SET summary = ?, payload_json = ? WHERE event_id = ?",
                     (REDACTED_SUMMARY, REDACTED_PAYLOAD, event_id))
        conn.execute("UPDATE audit_chain SET redacted = 1 WHERE event_id = ?", (event_id,))
    return len(ids)


def purge(days: int | None = None) -> dict:
    """Erase personal data older than the retention period. Safe to run at every start."""
    days = retention_days() if days is None else days
    cutoff = db.iso(db.utcnow() - timedelta(days=days))
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        messages = conn.execute("DELETE FROM messages WHERE ts < ?", (cutoff,)).rowcount
        events = _redact(conn, "ts < ?", (cutoff,))
        challenges = conn.execute("DELETE FROM kya_challenges WHERE expires_at < ?", (db.now_iso(),)).rowcount
    result = {"retention_days": days, "cutoff": cutoff, "messages_deleted": messages,
              "events_redacted": events, "expired_challenges_deleted": challenges}
    if messages or events:
        from shared.events import log_event
        log_event(None, "gateway", "personal_data_purged",
                  f"Retention: {messages} message(s) deleted, {events} event(s) redacted (older than {days} days)", result)
    return result


def erase_subject(wallet: str) -> dict:
    """Right to erasure for one agent wallet: its conversations go, its financial records stay."""
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        sessions = [r[0] for r in conn.execute(
            "SELECT s.session_id FROM sessions s JOIN agents a ON a.agent_id = s.agent_id "
            "WHERE lower(a.wallet_address) = lower(?)", (wallet,))]
        marks = ",".join("?" * len(sessions)) or "NULL"
        messages = conn.execute(f"DELETE FROM messages WHERE session_id IN ({marks})", tuple(sessions)).rowcount
        events = _redact(conn, f"session_id IN ({marks})", tuple(sessions))
    result = {"wallet": wallet, "sessions": len(sessions), "messages_deleted": messages, "events_redacted": events,
              "kept": "offers, transactions and license receipts (legal record keeping)"}
    from shared.events import log_event
    log_event(None, "gateway", "personal_data_purged",
              f"Erasure request for {wallet[:6]}...{wallet[-4:]}: {messages} message(s) deleted, {events} event(s) redacted",
              result)
    return result
