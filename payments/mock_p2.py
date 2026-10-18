"""In-memory stand-ins for what P2 (sessions, offers, tiers, publisher, events)
and P1 (get_content) will provide. Used until /shared and /ingestion exist.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone

from eth_account import Account

from payments import config
from shared.keys import has_key, load_private_key

TIERS = {
    "single_fact": 0.10,
    "small_table": 0.50,
    "full_section": 2.00,
}

CONTENT = {
    "rpt_battery_2025#s2": "Market share 2025: Voltacell 31.4%, Nordbatt 18.7%, Ionix 12.2%",
    "rpt_battery_2025#s3": "Full section with methodology (mock text).",
    "rpt_battery_2025#s4": "Gigafactory capacity 2025: 412 GWh (mock text).",
}
EXCLUDED = set()

DEV_TOKEN = "dev-token"
SESSIONS = {
    DEV_TOKEN: {
        "session_id": "ses_dev",
        "agent_id": "agent_dev",
        "wallet_address": Account.from_key(load_private_key("BUYER_PRIVATE_KEY_1")).address
        if has_key("BUYER_PRIVATE_KEY_1") else "",
    }
}

OFFERS = {}
EVENTS = []


def log_event(session_id, actor, type, summary, payload=None):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "session_id": session_id,
        "actor": actor,
        "type": type,
        "summary": summary,
        "payload": payload or {},
    }
    EVENTS.append(event)
    print("EVENT", json.dumps(event, default=str))


def get_session(token):
    return SESSIONS.get(token)


def get_offer(offer_id):
    return OFFERS.get(offer_id)


def set_offer_status(offer_id, status):
    OFFERS[offer_id]["status"] = status


def get_tier_price(tier):
    return TIERS.get(tier)


def get_publisher_wallet():
    return os.environ["PUBLISHER_WALLET_ADDRESS"]


def get_content(content_ids):
    """Like P1's ingestion.store.get_content: raises if any id is unknown or excluded."""
    missing = [cid for cid in content_ids if cid not in CONTENT or cid in EXCLUDED]
    if missing:
        raise KeyError(f"content not available: {missing}")
    return {cid: CONTENT[cid] for cid in content_ids}


def create_offer(session_id, tier, content_ids, price_usdc=None, status="accepted", scope="mock offer"):
    offer_id = "off_" + uuid.uuid4().hex[:8]
    OFFERS[offer_id] = {
        "offer_id": offer_id,
        "session_id": session_id,
        "content_ids": content_ids,
        "scope": scope,
        "tier": tier,
        "price_usdc": TIERS[tier] if price_usdc is None else price_usdc,
        "license": "internal_use_only",
        "status": status,
        "expires_at": time.time() + 300,
    }
    return OFFERS[offer_id]
