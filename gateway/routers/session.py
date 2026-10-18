"""Sales agent conversation and offer acceptance (7.2 steps 5 to 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from gateway import sales_agent
from gateway.auth import AgentIdentity, AgentSession, log_request, require_session
from gateway.tiers import tiers_by_name
from shared import config, db
from shared.events import log_event
from shared.schemas import OfferAcceptIn, OfferAcceptOut, SessionMessageIn, SessionMessageOut

router = APIRouter(tags=["session"])


@router.post("/session/message", response_model=SessionMessageOut)
def session_message(body: SessionMessageIn, request: Request,
                    session: AgentSession = Depends(require_session)) -> SessionMessageOut:
    log_request(request, AgentIdentity(session.agent_id, session.wallet), session.session_id)
    turn = sales_agent.handle_message(session.session_id, session.agent_id, body.message)
    return SessionMessageOut(session_id=session.session_id, action=turn.action,
                             message_to_buyer=turn.message_to_buyer, offer=turn.offer, rounds=turn.rounds)


@router.post("/offer/accept", response_model=OfferAcceptOut)
def offer_accept(body: OfferAcceptIn, request: Request,
                 session: AgentSession = Depends(require_session)) -> OfferAcceptOut:
    log_request(request, AgentIdentity(session.agent_id, session.wallet), session.session_id)
    offer = db.get_offer(body.offer_id)
    if not offer or offer["session_id"] != session.session_id:
        raise HTTPException(status_code=404, detail="Offer not found in this session")
    if offer["status"] != "proposed":
        raise HTTPException(status_code=409, detail=f"Offer is {offer['status']}, it cannot be accepted")
    if offer["expires_at"] < db.now_iso():
        db.update_offer_status(offer["offer_id"], "expired", expected_status="proposed")
        raise HTTPException(status_code=409, detail="Offer expired, ask the Sales agent again")

    limit = sales_agent.daily_limit_errors(session.agent_id, offer["content_ids"], sales_agent._sellable_catalog(),
                                           exclude_offer=offer["offer_id"])
    if limit:
        db.update_offer_status(offer["offer_id"], "rejected", expected_status="proposed")
        log_event(session.session_id, "gateway", "offer_rejected", f"Offer {offer['offer_id']} refused at accept: {limit[0]}",
                  {"offer_id": offer["offer_id"], "errors": limit})
        raise HTTPException(status_code=409, detail=limit[0])

    tier = tiers_by_name().get(offer["tier"])
    if not tier or abs(tier["price_usdc"] - offer["price_usdc"]) > 1e-9:
        db.update_offer_status(offer["offer_id"], "rejected", expected_status="proposed")
        raise HTTPException(status_code=409, detail="Tiers changed since the offer was made")

    if not db.update_offer_status(offer["offer_id"], "accepted", expires_at=db.iso_in(config.OFFER_TTL_SECONDS),
                                  expected_status="proposed"):
        raise HTTPException(status_code=409, detail="Offer was already accepted")

    route = tier["route"]
    log_event(session.session_id, "gateway", "offer_accepted",
              f"Offer {offer['offer_id']} accepted, pay {offer['price_usdc']:.2f} USDC on /query/{route}",
              {"offer_id": offer["offer_id"], "route": route, "price_usdc": offer["price_usdc"],
               "expires_in_s": config.OFFER_TTL_SECONDS})
    return OfferAcceptOut(offer_id=offer["offer_id"], status="accepted", tier=offer["tier"],
                          price_usdc=offer["price_usdc"], route=route, pay_url=f"/query/{route}",
                          expires_in_s=config.OFFER_TTL_SECONDS)
