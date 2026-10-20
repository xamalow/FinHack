"""Paid routes (agent.md 7.2 step 8): POST /query/{route}, GET /receipt/{tx_hash}, GET /transactions.

Order on a paid request:
1. session, offer and tier checks
2. no payment header -> 402 built from the server-side offer price
3. payment header -> must match the offer requirements exactly, payer must be the KYA wallet
4. reserve nonce + offer_id (UNIQUE, replay -> 409)
5. facilitator verify, then settle
6. only after settlement: mark offer paid, load content, 200 with PAYMENT-RESPONSE
"""
import asyncio
import hashlib
import os
import time
from datetime import datetime, timezone
from collections import defaultdict, deque

from fastapi import APIRouter, Body, Depends, Header, Request
from fastapi.responses import JSONResponse
from x402.http import (
    decode_payment_signature_header,
    encode_payment_required_header,
    encode_payment_response_header,
)
from x402.schemas import ResourceInfo, SettleResponse

from payments import balances, config, deps, recovery, store, watermark
from payments.x402_server import build_requirements, get_server
from shared import sanctions, signing
from shared.owner import publisher_only

router = APIRouter()
SETTLE_ATTEMPTS = 3
RATE_LIMIT_PER_MIN = int(os.getenv("QUERY_RATE_LIMIT_PER_MIN", "30"))
_hits = defaultdict(deque)
# Last successfully paid request, whoever the buyer is (test agent or a user's own assistant via buyer-mcp),
# kept in memory only for the replay demo button (POST /buyer/replay-last).
LAST_PAID = None


def rate_limited(key):
    """Sliding one-minute window per session (or client IP before KYA). No event on purpose: a flood must not
    flood the live view and the events table too."""
    now = time.time()
    hits = _hits[key]
    while hits and hits[0] < now - 60:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_PER_MIN:
        return True
    hits.append(now)
    return False


def error(status, session_id, event_type, summary, payload=None, headers=None):
    deps.log_event(session_id, "gateway", event_type, summary, payload or {})
    return JSONResponse({"error": event_type, "detail": summary}, status_code=status, headers=headers)


def load_content(offer):
    """The content must be deliverable before we ask for or take the money. None if it is not
    (P1 raises for unknown or excluded ids). Kept in memory, never sent before settlement."""
    try:
        content = deps.get_content(offer["content_ids"])
    except Exception:
        return None
    if not content or any(not content.get(cid) for cid in offer["content_ids"]):
        return None
    return content


def content_unavailable(sid, offer):
    return error(409, sid, "payment_rejected", f"Content of {offer['offer_id']} is not available, nothing to pay",
                 {"offer_id": offer["offer_id"], "content_ids": offer["content_ids"]})


def auth(authorization):
    token = (authorization or "").removeprefix("Bearer ").strip()
    return deps.get_session(token) if token else None


async def payment_required(request, offer, requirements, session_id, reason="Payment required"):
    resource = ResourceInfo(url=str(request.url), description=offer["offer_id"])
    body = await get_server().create_payment_required_response(requirements, resource, reason)
    deps.log_event(session_id, "gateway", "payment_required_sent",
                   f"402 sent for {offer['offer_id']}, {offer['price_usdc']} USDC",
                   body.model_dump(by_alias=True, exclude_none=True))
    return JSONResponse(
        {"error": reason, "offer_id": offer["offer_id"]},
        status_code=402,
        headers={"PAYMENT-REQUIRED": encode_payment_required_header(body)},
    )


@router.post("/query/{route}")
async def query(
    route: str,
    request: Request,
    offer_id: str = Body(..., embed=True),
    authorization: str | None = Header(None),
    payment_signature: str | None = Header(None),
):
    session = auth(authorization)
    key = session["session_id"] if session else f"ip:{request.client.host if request.client else '?'}"
    if rate_limited(key):
        return JSONResponse({"error": "rate_limited", "detail": f"max {RATE_LIMIT_PER_MIN} paid requests per minute"},
                            status_code=429, headers={"Retry-After": "60"})
    response = await paid_query(route, request, offer_id, authorization, payment_signature)
    store.record_request(route, offer_id, session["session_id"] if session else None, response.status_code)
    return response


async def paid_query(route, request, offer_id, authorization, payment_signature):
    session = auth(authorization)
    if session is None:
        return JSONResponse({"error": "invalid_session"}, status_code=401)
    sid = session["session_id"]

    offer = deps.get_offer(offer_id)
    tier = config.ROUTE_TIERS.get(route)
    if offer is None or offer["session_id"] != sid:
        return error(404, sid, "payment_rejected", f"Offer {offer_id} not found for this session")
    row = store.get_by_offer(offer_id)
    if row and row["status"] == "pending":
        # A previous attempt crashed or lost the facilitator answer: ask the chain what happened.
        try:
            state, tx_hash = await recovery.reconcile(row)
        except Exception:
            state, tx_hash = "pending", None
        if state == "settled":
            return deliver_recovered(sid, session, offer, row, tx_hash)
        if state == "pending":
            return error(409, sid, "payment_rejected", f"A payment for {offer_id} is still being settled, retry shortly",
                         {"offer_id": offer_id})
    elif row or offer["status"] == "paid":
        return error(409, sid, "replay_rejected", f"Offer {offer_id} already paid", {"offer_id": offer_id})
    if offer["status"] != "accepted":
        return error(409, sid, "payment_rejected", f"Offer {offer_id} is {offer['status']}")
    if offer["expires_at"] < time.time():
        return error(410, sid, "payment_rejected", f"Offer {offer_id} expired")
    if tier is None or offer["tier"] != tier:
        return error(400, sid, "payment_rejected", f"Route {route} does not match tier {offer['tier']}")

    tier_price = deps.get_tier_price(tier)
    if tier_price is None or abs(tier_price - float(offer["price_usdc"])) > 1e-9:
        return error(400, sid, "payment_rejected", "Offer price does not match the confirmed tier")

    if load_content(offer) is None:
        return content_unavailable(sid, offer)

    amount = config.usdc_to_atomic(tier_price)
    pay_to = deps.get_publisher_wallet()
    requirements = build_requirements(amount, pay_to)

    if not payment_signature:
        try:
            await balances.watch(sid, {"buyer": session["wallet_address"], "publisher": pay_to})
        except Exception as e:
            deps.log_event(sid, "chain", "balance_watch_failed", f"Balance watch not started: {type(e).__name__}")
        return await payment_required(request, offer, requirements, sid)

    try:
        payload = decode_payment_signature_header(payment_signature)
        authorization_data = payload.payload["authorization"]
        nonce, payer = authorization_data["nonce"], authorization_data["from"]
    except Exception:
        return await payment_required(request, offer, requirements, sid, "Unreadable payment header")

    matched = get_server().find_matching_requirements(requirements, payload)
    if matched is None:
        deps.log_event(sid, "gateway", "payment_rejected", "Payment does not match the offer",
                       {"expected": [r.model_dump(by_alias=True) for r in requirements],
                        "received": payload.accepted.model_dump(by_alias=True)})
        return await payment_required(request, offer, requirements, sid, "Payment does not match the offer")

    if payer.lower() != session["wallet_address"].lower():
        deps.log_event(sid, "gateway", "payment_rejected", "Payer is not the KYA-verified wallet",
                       {"payer": payer, "kya_wallet": session["wallet_address"]})
        return await payment_required(request, offer, requirements, sid, "Payer is not the verified agent wallet")

    # Checked again right before taking the money: the publisher may have excluded it since the 402.
    content = load_content(offer)
    if content is None:
        return content_unavailable(sid, offer)

    # Screened again right before the money moves: the list changes, and a KYA session lasts 15 minutes.
    screening = await asyncio.to_thread(sanctions.screen, payer)
    if screening.blocked:
        return error(403, sid, "sanctions_blocked", f"Payer refused by sanctions screening: {screening.detail}",
                     {"check": "payment", **screening.as_payload()})

    try:
        tx_id = store.reserve(offer_id, nonce, payer, pay_to, amount)
    except store.ReplayError as e:
        return error(409, sid, "replay_rejected", "Nonce or offer already used, nothing delivered",
                     {"offer_id": offer_id, "nonce": nonce, "db": str(e)})

    try:
        verified = await get_server().verify_payment(payload, matched)
        verify = verified.verify
        deps.log_event(sid, "facilitator", "verify_response",
                       "Signature valid" if verify.is_valid else f"Verify failed: {verify.invalid_reason}",
                       verify.model_dump(by_alias=True))
        if not verify.is_valid:
            store.release(tx_id)
            return await payment_required(request, offer, requirements, sid, verify.invalid_reason or "Verify failed")
        deps.log_event(sid, "gateway", "payment_verified", f"Payment of {tier_price} USDC verified", {"payer": payer})
    except Exception as e:
        store.release(tx_id)
        return error(502, sid, "payment_rejected", f"Facilitator error: {type(e).__name__}", {"error": str(e)})

    try:
        # The public facilitator sometimes fails to broadcast (its own nonce clash). Retrying is safe:
        # the EIP-3009 nonce lets the USDC contract execute this authorization at most once.
        for attempt in range(1, SETTLE_ATTEMPTS + 1):
            settle = await get_server().settle_payment(payload, matched)
            deps.log_event(sid, "facilitator", "settle_response",
                           f"Settled, tx {settle.transaction}" if settle.success
                           else f"Settle failed (attempt {attempt}): {settle.error_reason}",
                           settle.model_dump(by_alias=True))
            if settle.success or "transaction_failed" not in (settle.error_reason or ""):
                break
            await asyncio.sleep(2)
    except Exception as e:
        # Outcome unknown: the transfer may still land. The reservation stays pending and the next request on
        # this offer settles it from the chain or releases it once the authorization expired (recovery.py).
        return error(502, sid, "payment_rejected", f"Settlement outcome unknown ({type(e).__name__}), retry shortly",
                     {"offer_id": offer_id, "error": str(e)})
    if not settle.success:
        store.release(tx_id)
        return await payment_required(request, offer, requirements, sid, settle.error_reason or "Settle failed")

    store.mark_settled(tx_id, settle.transaction)
    global LAST_PAID
    LAST_PAID = {"url": str(request.url), "json": {"offer_id": offer_id},
                 "headers": {k: v for k, v in request.headers.items()
                             if k.lower() in ("authorization", "payment-signature", "x-agent-id", "x-agent-wallet")}}
    return deliver(sid, offer, content, settle, payer, tier_price)


def deliver(sid, offer, content, settle, payer, price_usdc, recovered=False):
    """Money has moved: from here on we always deliver. The transactions row already blocks a second sale."""
    offer_id = offer["offer_id"]
    try:
        deps.set_offer_status(offer_id, "paid")
    except Exception as e:
        deps.log_event(sid, "gateway", "payment_settled", f"Offer status not updated: {type(e).__name__}",
                       {"offer_id": offer_id, "error": str(e)})
    tx_url = f"{config.EXPLORER_URL}/tx/{settle.transaction}"
    deps.log_event(sid, "gateway", "payment_settled",
                   f"{price_usdc} USDC settled" + (" (recovered from the chain)" if recovered else ""),
                   {"tx_hash": settle.transaction, "recovered": recovered})
    deps.log_event(sid, "chain", "tx_confirmed", f"Tx {settle.transaction[:10]}... confirmed",
                   {"tx_hash": settle.transaction, "explorer": tx_url})
    content, receipt = license_content(offer, content, settle.transaction, payer)
    deps.log_event(sid, "gateway", "content_delivered", f"Delivered {len(content)} item(s) for {offer_id}",
                   {"offer_id": offer_id, "content_ids": offer["content_ids"], "watermark_id": receipt["watermark_id"]})
    return JSONResponse(
        {
            "offer_id": offer_id,
            "license": offer["license"],
            "content": content,
            "receipt": {"tx_hash": settle.transaction, "explorer": tx_url, "payer": payer,
                        "amount_usdc": price_usdc, "network": config.NETWORK},
            "license_receipt": receipt,
        },
        headers={"PAYMENT-RESPONSE": encode_payment_response_header(settle), "Cache-Control": "no-store"},
    )


def license_content(offer, content, tx_hash, payer):
    """Watermarks the content for this buyer and returns it with the publisher-signed license receipt.
    Deterministic, so a re-delivery (recovery, /receipt) carries the same marks and the same receipt."""
    content, wid = watermark.apply(content, offer["offer_id"], payer, offer["license"])
    receipt = store.get_receipt(tx_hash)
    if receipt is None:
        tx = store.get_by_hash(tx_hash) or {}
        receipt = signing.sign_receipt({
            "offer_id": offer["offer_id"], "tx_hash": tx_hash, "network": config.NETWORK, "asset": config.USDC_ADDRESS,
            "payer": payer.lower(), "pay_to": (tx.get("pay_to") or deps.get_publisher_wallet()).lower(),
            "amount_atomic": tx.get("amount_atomic") or config.usdc_to_atomic(offer["price_usdc"]),
            "tier": offer["tier"], "scope": offer.get("scope"), "license": offer["license"],
            "content_ids": offer["content_ids"],
            "content_sha256": hashlib.sha256(signing.canonical(content).encode()).hexdigest(),
            "watermark_id": wid, "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        store.save_receipt(tx_hash, offer["offer_id"], receipt)
        deps.log_event(offer.get("session_id"), "gateway", "license_receipt_issued",
                       f"License receipt signed for {offer['offer_id']} by {receipt['signer'][:10]}...", receipt)
    return content, receipt


def deliver_recovered(sid, session, offer, row, tx_hash):
    """The chain shows this offer was paid but the delivery never happened: deliver it to that same payer."""
    if row["payer"] != session["wallet_address"].lower():
        return error(409, sid, "replay_rejected", f"Offer {offer['offer_id']} already paid", {"offer_id": offer["offer_id"]})
    content = load_content(offer)
    if content is None:
        return error(410, sid, "payment_rejected", "Paid content is no longer available", {"tx_hash": tx_hash})
    settle = SettleResponse(success=True, transaction=tx_hash, network=config.NETWORK, payer=row["payer"])
    return deliver(sid, offer, content, settle, row["payer"], row["amount_atomic"] / 1_000_000, recovered=True)


@router.get("/receipt/{tx_hash}")
async def receipt(tx_hash: str, authorization: str | None = Header(None)):
    session = auth(authorization)
    if session is None:
        return JSONResponse({"error": "invalid_session"}, status_code=401)
    sid = session["session_id"]

    tx = store.get_by_hash(tx_hash)
    if tx is None or tx["status"] != "settled":
        return error(404, sid, "payment_rejected", "Unknown receipt")
    if tx["payer"] != session["wallet_address"].lower():
        return error(403, sid, "payment_rejected", "Receipt belongs to another wallet")
    if time.time() - tx["ts"] > config.RECEIPT_TTL_HOURS * 3600:
        return error(410, sid, "payment_rejected", "Receipt expired")

    offer = deps.get_offer(tx["offer_id"])
    content = load_content(offer) if offer else None
    if content is None:
        return error(410, sid, "payment_rejected", "Paid content is no longer available", {"tx_hash": tx_hash})
    content, license_receipt = license_content(offer, content, tx["tx_hash"], tx["payer"])
    deps.log_event(sid, "gateway", "receipt_redownload", f"Re-delivered {tx['offer_id']} from receipt",
                   {"tx_hash": tx_hash})
    return JSONResponse({"offer_id": tx["offer_id"], "license": offer["license"], "content": content,
                         "receipt": {"tx_hash": tx["tx_hash"], "payer": tx["payer"]}, "license_receipt": license_receipt},
                        headers={"Cache-Control": "no-store"})


@router.get("/transactions", dependencies=[Depends(publisher_only)])
async def transactions():
    return store.list_all()


@router.get("/balance/{address}")
async def balance(address: str):
    if not balances.is_address(address):
        return JSONResponse({"error": "invalid_address"}, status_code=400)
    try:
        atomic = await balances.read_balance(address)
    except Exception as e:
        return JSONResponse({"error": "rpc_error", "detail": type(e).__name__}, status_code=502)
    return {"address": address, "asset": "USDC", "network": config.NETWORK,
            "balance_atomic": atomic, "balance_usdc": atomic / 1_000_000}


@router.get("/publisher/stats", dependencies=[Depends(publisher_only)])
async def publisher_stats():
    # Before Go live there is no payout wallet yet: the dashboard still shows its (empty) stats.
    try:
        wallet = deps.get_publisher_wallet()
    except RuntimeError:
        wallet = None
    return {"publisher_wallet": wallet, **store.stats()}
