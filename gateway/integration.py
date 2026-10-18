"""P2 implementation of the interface P3 codes against (`payments/deps.py`).

After the merge, `payments/deps.py` becomes:

    from gateway.integration import (get_content, get_offer, get_publisher_wallet,
                                     get_session, get_tier_price, log_event, set_offer_status)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import jwt

from gateway import p1_bridge
from gateway.auth import JWT_ALG
from gateway.tiers import tiers_by_name
from shared import config, db
from shared.events import log_event  # noqa: F401  re-exported for payments/deps.py


def _epoch(iso_ts: str) -> float:
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).timestamp()


def get_session(token: str) -> Optional[dict[str, Any]]:
    """Session behind a Bearer token, or None if invalid, expired or the agent is not verified."""
    try:
        claims = jwt.decode(token, config.jwt_secret(), algorithms=[JWT_ALG], options={"require": ["exp", "sub", "sid"]})
    except jwt.InvalidTokenError:
        return None
    session = db.get_session(claims["sid"])
    agent = db.get_agent(claims["sub"])
    if (not session or session["agent_id"] != claims["sub"] or session["token_expires_at"] < db.now_iso()
            or not agent or agent["status"] != "verified" or agent["wallet_address"] != claims.get("wallet")):
        return None
    return {"session_id": session["session_id"], "agent_id": agent["agent_id"], "wallet_address": agent["wallet_address"]}


def get_offer(offer_id: str) -> Optional[dict[str, Any]]:
    """Offer row with `expires_at` as a Unix epoch float, as payments/router.py compares it to time.time()."""
    offer = db.get_offer(offer_id)
    if offer:
        offer["expires_at"] = _epoch(offer["expires_at"])
    return offer


def set_offer_status(offer_id: str, status: str) -> None:
    expected = "accepted" if status == "paid" else None
    if not db.update_offer_status(offer_id, status, expected_status=expected):
        raise ValueError(f"Offer {offer_id} could not move to {status}")


def get_tier_price(tier: str) -> Optional[float]:
    t = tiers_by_name().get(tier)
    return t["price_usdc"] if t else None


def get_publisher_wallet() -> str:
    wallet = db.get_publisher().get("wallet_address") or config.env("PUBLISHER_WALLET_ADDRESS")
    if not wallet:
        raise RuntimeError("No publisher wallet: connect it in onboarding or set PUBLISHER_WALLET_ADDRESS")
    return wallet


def get_content(content_ids: list[str]) -> dict[str, str]:
    return p1_bridge.get_content(content_ids)
