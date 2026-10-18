"""KYA, Know Your Agent, by wallet signature (7.2 step 3)."""

from __future__ import annotations

import secrets

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Depends, HTTPException, Request

from gateway.auth import AgentIdentity, agent_identity, issue_token, log_request
from shared import config, db
from shared.events import log_event
from shared.schemas import KyaChallengeOut, KyaVerifyIn, KyaVerifyOut

router = APIRouter(prefix="/kya", tags=["kya"])


def challenge_message(nonce: str, agent_id: str) -> str:
    """The exact text the agent signs with EIP-191 personal_sign."""
    return f"FinHack KYA challenge for agent {agent_id}. Nonce: {nonce}"


def _reject(identity: AgentIdentity, reason: str, status: int = 403) -> HTTPException:
    log_event(
        None, "gateway", "kya_rejected",
        f"KYA rejected for {identity.agent_id}: {reason}",
        {"agent_id": identity.agent_id, "wallet": identity.wallet, "reason": reason},
    )
    return HTTPException(status_code=status, detail=f"KYA failed: {reason}")


@router.post("/challenge", response_model=KyaChallengeOut)
def challenge(request: Request, identity: AgentIdentity = Depends(agent_identity)) -> KyaChallengeOut:
    log_request(request, identity)
    nonce = secrets.token_hex(32)
    db.insert_challenge(nonce, identity.agent_id, identity.wallet, db.iso_in(config.KYA_CHALLENGE_TTL_SECONDS))
    message = challenge_message(nonce, identity.agent_id)
    log_event(
        None, "gateway", "kya_challenge_issued",
        f"KYA challenge issued to {identity.agent_id}",
        {"agent_id": identity.agent_id, "wallet": identity.wallet, "nonce": nonce, "message": message},
    )
    return KyaChallengeOut(nonce=nonce, message=message, expires_in_s=config.KYA_CHALLENGE_TTL_SECONDS)


@router.post("/verify", response_model=KyaVerifyOut)
def verify(body: KyaVerifyIn, request: Request, identity: AgentIdentity = Depends(agent_identity)) -> KyaVerifyOut:
    log_request(request, identity)

    challenge_row = db.consume_challenge(body.nonce)
    if not challenge_row:
        raise _reject(identity, "unknown or already used nonce")
    if challenge_row["expires_at"] < db.now_iso():
        raise _reject(identity, "challenge expired")
    if challenge_row["agent_id"] != identity.agent_id or challenge_row["wallet_address"] != identity.wallet:
        raise _reject(identity, "challenge was issued to another agent")

    # Agents may sign the bare nonce (agent.md 7.2 step 3) or the full challenge message.
    signer = None
    for text in (body.nonce, challenge_message(body.nonce, identity.agent_id)):
        try:
            signer = Account.recover_message(encode_defunct(text=text), signature=body.signature)
        except Exception:
            raise _reject(identity, "unreadable signature")
        if signer == identity.wallet:
            break
    if signer != identity.wallet:
        raise _reject(identity, "signature does not match X-Agent-Wallet")

    # Binding first: a blocklisted wallet must not be able to rebind (and block) another agent's id.
    existing = db.get_agent(identity.agent_id)
    if existing and existing["wallet_address"] != identity.wallet:
        raise _reject(identity, "agent id is already bound to another wallet")
    if identity.wallet.lower() in config.kya_blocklist():
        db.upsert_agent(identity.agent_id, identity.wallet, "blocked")
        raise _reject(identity, "wallet is on the blocklist (sanctions screening)")
    if existing and existing["status"] == "blocked":
        raise _reject(identity, "agent is blocked")
    db.upsert_agent(identity.agent_id, identity.wallet, "verified")

    session_id = "ses_" + secrets.token_hex(6)
    db.insert_session(session_id, identity.agent_id, db.iso_in(config.SESSION_TTL_SECONDS))
    token = issue_token(identity.agent_id, identity.wallet, session_id)

    log_event(
        session_id, "gateway", "kya_verified",
        f"Agent {identity.wallet[:6]}...{identity.wallet[-4:]} verified, session token issued",
        {"agent_id": identity.agent_id, "wallet": identity.wallet, "signer": signer,
         "signature": body.signature, "session_id": session_id, "token": token,
         "expires_in_s": config.SESSION_TTL_SECONDS},
    )
    return KyaVerifyOut(session_id=session_id, agent_id=identity.agent_id, token=token, session_token=token,
                        expires_in_s=config.SESSION_TTL_SECONDS)
