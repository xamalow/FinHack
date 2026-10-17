"""Agent-or-human detection (7.2 step 2) and session tokens (7.2 step 3)."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Optional

import jwt
from eth_utils import is_address, to_checksum_address
from fastapi import Depends, Header, HTTPException, Request

from shared import config, db
from shared.events import log_event

JWT_ALG = "HS256"


@dataclass
class AgentIdentity:
    agent_id: str
    wallet: str  # checksummed


@dataclass
class AgentSession:
    agent_id: str
    wallet: str
    session_id: str


def _redirect_human(request: Request) -> HTTPException:
    target = config.DEMO_SITE_URL or "/"
    log_event(
        None, "gateway", "human_redirected",
        f"No agent identity on {request.url.path}, redirected to the website",
        {"path": request.url.path, "redirect_to": target},
    )
    return HTTPException(status_code=307, detail="Humans are redirected to the website", headers={"Location": target})


def agent_identity(
    request: Request,
    x_agent_id: Optional[str] = Header(default=None),
    x_agent_wallet: Optional[str] = Header(default=None),
) -> AgentIdentity:
    """No identity headers means a human visitor (7.2 step 2)."""
    if not x_agent_id or not x_agent_wallet:
        raise _redirect_human(request)
    if len(x_agent_id) > 128 or not is_address(x_agent_wallet):
        raise HTTPException(status_code=400, detail="Invalid X-Agent-Id or X-Agent-Wallet")
    return AgentIdentity(agent_id=x_agent_id, wallet=to_checksum_address(x_agent_wallet))


def log_request(request: Request, identity: AgentIdentity, session_id: Optional[str] = None) -> None:
    log_event(
        session_id, "gateway", "request_received",
        f"{request.method} {request.url.path} from agent {identity.agent_id}",
        {"method": request.method, "path": request.url.path, "agent_id": identity.agent_id, "wallet": identity.wallet},
    )


def issue_token(agent_id: str, wallet: str, session_id: str) -> str:
    now = int(time.time())
    claims = {
        "sub": agent_id,
        "wallet": wallet,
        "sid": session_id,
        "iat": now,
        "exp": now + config.SESSION_TTL_SECONDS,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, config.jwt_secret(), algorithm=JWT_ALG)


def require_session(
    identity: AgentIdentity = Depends(agent_identity),
    authorization: Optional[str] = Header(default=None),
) -> AgentSession:
    """Bearer session token, bound to the same agent id and wallet as the headers."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing session token, run KYA first")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, config.jwt_secret(), algorithms=[JWT_ALG], options={"require": ["exp", "sub", "sid"]})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session token expired, run KYA again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    if claims["sub"] != identity.agent_id or claims.get("wallet") != identity.wallet:
        raise HTTPException(status_code=403, detail="Session token does not match agent identity headers")

    session = db.get_session(claims["sid"])
    if not session or session["agent_id"] != identity.agent_id or session["token_expires_at"] < db.now_iso():
        raise HTTPException(status_code=401, detail="Session not found or expired")

    agent = db.get_agent(identity.agent_id)
    if not agent or agent["status"] != "verified":
        raise HTTPException(status_code=403, detail="Agent is not verified")

    return AgentSession(agent_id=identity.agent_id, wallet=identity.wallet, session_id=claims["sid"])
