"""Mock of the P2 endpoints the buyer agent talks to (manifest, discover, KYA,
Sales agent, offer accept). Only mounted by dev_app.py, replaced by P2's gateway.
The mock Sales agent is keyword based, it is not the real LLM Sales agent.
"""
import secrets
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Body, Header, Request
from fastapi.responses import JSONResponse

from payments import config, mock_p2

router = APIRouter()
CHALLENGES = {}
BLOCKLIST = {"0x000000000000000000000000000000000000dead"}


@router.get("/.well-known/ai-data.json")
async def manifest(request: Request):
    return {
        "publisher": "Demo Research Firm",
        "gateway": str(request.base_url).rstrip("/"),
        "discover": "/discover",
        "kya": "/kya/challenge",
        "topics": ["batteries", "lithium", "gigafactories"],
        "payment": {"protocol": "x402", "network": config.NETWORK, "asset": "USDC",
                    "pay_to": mock_p2.get_publisher_wallet()},
        "license_default": "internal_use_only",
    }


@router.get("/discover")
async def discover(q: str = ""):
    return {"query": q, "topics": ["batteries", "lithium", "gigafactories"],
            "periods": ["2024", "2025"], "summary": "European battery market reports, figures sold per piece."}


@router.post("/kya/challenge")
async def kya_challenge(x_agent_wallet: str | None = Header(None)):
    if not x_agent_wallet:
        return JSONResponse({"error": "human_redirected", "redirect": "/"}, status_code=403)
    nonce = secrets.token_hex(16)
    CHALLENGES[nonce] = x_agent_wallet.lower()
    return {"nonce": nonce}


@router.post("/kya/verify")
async def kya_verify(nonce: str = Body(...), signature: str = Body(...),
                     x_agent_id: str | None = Header(None), x_agent_wallet: str | None = Header(None)):
    expected = CHALLENGES.pop(nonce, None)
    signer = Account.recover_message(encode_defunct(text=nonce), signature=signature).lower()
    if expected is None or signer != expected or signer != (x_agent_wallet or "").lower() or signer in BLOCKLIST:
        return JSONResponse({"error": "kya_rejected"}, status_code=403)
    token = secrets.token_urlsafe(24)
    mock_p2.SESSIONS[token] = {"session_id": "ses_" + secrets.token_hex(3), "agent_id": x_agent_id,
                               "wallet_address": x_agent_wallet}
    return {"session_token": token, "session_id": mock_p2.SESSIONS[token]["session_id"], "expires_in_s": 900}


@router.post("/session/message")
async def session_message(message: str = Body(..., embed=True), authorization: str | None = Header(None)):
    session = mock_p2.get_session((authorization or "").removeprefix("Bearer ").strip())
    if session is None:
        return JSONResponse({"error": "invalid_session"}, status_code=401)
    text = message.lower()
    if "battery" not in text and "batteries" not in text:
        return {"action": "no_match", "message_to_buyer": "We do not cover this topic.", "offer": None}
    if "full" in text or "methodology" in text or "section" in text:
        tier, cid = "full_section", "rpt_battery_2025#s3"
    elif "table" in text or "top 5" in text:
        tier, cid = "small_table", "rpt_battery_2025#s2"
    else:
        tier, cid = "single_fact", "rpt_battery_2025#s2"
    offer = mock_p2.create_offer(session["session_id"], tier, [cid], status="proposed")
    return {
        "action": "propose_offer",
        "message_to_buyer": f"We can sell this as a {tier.replace('_', ' ')}.",
        "offer": {"offer_id": offer["offer_id"], "content_ids": offer["content_ids"], "scope": offer["scope"],
                  "tier": tier, "price_usdc": offer["price_usdc"], "license": offer["license"],
                  "expires_in_s": 300},
    }


@router.post("/offer/accept")
async def offer_accept(offer_id: str = Body(..., embed=True), authorization: str | None = Header(None)):
    session = mock_p2.get_session((authorization or "").removeprefix("Bearer ").strip())
    offer = mock_p2.get_offer(offer_id)
    if session is None or offer is None or offer["session_id"] != session["session_id"]:
        return JSONResponse({"error": "offer_not_found"}, status_code=404)
    offer["status"] = "accepted"
    offer["expires_at"] = time.time() + 300
    route = {v: k for k, v in config.ROUTE_TIERS.items()}[offer["tier"]]
    return {"offer_id": offer_id, "route": route, "price_usdc": offer["price_usdc"]}
