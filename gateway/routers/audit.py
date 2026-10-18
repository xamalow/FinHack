"""Audit trail per sale (6.5): offer, agent identity, conversation, payment, events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from shared import config, db
from shared.owner import publisher_only

router = APIRouter(tags=["audit"], dependencies=[Depends(publisher_only)])  # holds the conversation


@router.get("/audit/{offer_id}")
def audit(offer_id: str) -> dict:
    offer = db.get_offer(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Unknown offer")
    session = db.get_session(offer["session_id"]) or {}
    agent = db.get_agent(session.get("agent_id", "")) if session else None
    transactions = db.transactions_for_offer(offer_id)
    for tx in transactions:
        if tx.get("tx_hash"):
            tx["explorer_url"] = f"{config.EXPLORER_URL}/tx/{tx['tx_hash']}"
    return {
        "offer": offer,
        "agent": agent,
        "session": session,
        "messages": db.list_messages(offer["session_id"]),
        "transaction": next((t for t in transactions if t.get("status") == "settled"),
                            transactions[0] if transactions else None),
        "transactions": transactions,
        "events": db.list_events(session_id=offer["session_id"]),
    }
