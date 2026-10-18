"""Event log feeding the live view (agent.md 6.4). Owned by P2.

Every step of every workflow calls `log_event()`. Events are stored in SQLite,
so the gateway, the buyer agent and scripts can all write them, and
`GET /events/stream` replays them in order.

Add new event types to EVENT_TYPES below; unknown types raise.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from shared import db

log = logging.getLogger("events")

EVENT_TYPES: dict[str, set[str]] = {
    "publisher": {
        "scan_started", "scan_extracting", "scan_indexing", "scan_ready", "scan_failed", "catalog_updated",
        "rules_parsed", "rules_confirmed", "wallet_connected", "activated",
    },
    "gateway": {
        "request_received", "human_redirected", "kya_challenge_issued", "kya_verified",
        "kya_rejected", "offer_validated", "offer_rejected", "offer_accepted",
        "payment_required_sent", "payment_verified", "payment_settled", "payment_rejected",
        "replay_rejected", "content_delivered", "receipt_redownload",
        "sanctions_screened", "sanctions_blocked", "license_receipt_issued", "personal_data_purged",
    },
    "sales_agent": {"sales_message", "offer_proposed", "no_match", "injection_ignored"},
    "buyer": {
        "mission_started", "manifest_read", "discover_called", "kya_signed", "buyer_message",
        "offer_evaluated", "offer_refused_budget", "approval_requested", "approval_granted",
        "payment_signed", "data_received", "mission_done",
        "sanctions_screened", "sanctions_blocked", "velocity_limit_hit", "structuring_suspected",
        "manifest_signature_checked", "manifest_signature_failed", "receipt_verified",
    },
    "facilitator": {"verify_response", "settle_response"},
    "chain": {"tx_submitted", "tx_confirmed", "balance_changed", "balance_watch_failed"},
}

# Payload keys whose values are never shown in the live view.
SECRET_KEYS = ("private_key", "secret", "api_key", "apikey", "password", "authorization", "token", "jwt")
MASK = "***masked***"


def mask_secrets(value: Any) -> Any:
    """Recursively mask values whose key looks like a secret."""
    if isinstance(value, dict):
        return {
            k: (MASK if any(s in str(k).lower() for s in SECRET_KEYS) else mask_secrets(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_secrets(v) for v in value]
    return value


def log_event(
    session_id: Optional[str],
    actor: str,
    type: str,
    summary: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Store one event and return it as a dict matching shared.schemas.Event."""
    if type not in EVENT_TYPES.get(actor, set()):
        raise ValueError(f"Unknown event type {actor}/{type}. Add it to shared/events.py first.")
    ts = db.now_iso()
    safe_payload = mask_secrets(payload or {})
    event_id = db.insert_event(ts, session_id, actor, type, summary, safe_payload)
    log.info("[%s] %s/%s %s", session_id or "-", actor, type, summary)
    return {
        "event_id": event_id,
        "ts": ts,
        "session_id": session_id,
        "actor": actor,
        "type": type,
        "summary": summary,
        "payload": safe_payload,
    }
