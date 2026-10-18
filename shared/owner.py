"""Owner-only routes: who may change the publisher setup, or spend the buyer's wallets.

A route protected with `owner_only("PUBLISHER_OWNER_TOKEN")` accepts a request when:
- the env var is set and the request carries one of its values in `X-Owner-Token` (constant-time compare), or
- the env var is empty and the request comes from this machine (loopback TCP peer; X-Forwarded-For is ignored).

Rotation: the env var may hold several comma-separated tokens (new,old) while clients move to the new one.
Expiry: <ENV_VAR>_EXPIRES_AT (ISO date, UTC) refuses the tokens after that date, so they must be rotated.

Everything else gets 403. Agents never call these routes: they only use discovery, KYA, the Sales agent and
the paid routes, which stay public.
"""
import hmac
import ipaddress
import os
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request

LOOPBACK = {"127.0.0.1", "::1"}


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:  # ::ffff:127.0.0.1 on dual-stack
        address = address.ipv4_mapped
    return address.is_loopback


def _expired(env_var: str) -> bool:
    raw = os.getenv(f"{env_var}_EXPIRES_AT", "").strip()
    if not raw:
        return False
    expires = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires


def owner_only(env_var: str, what: str = "this action"):
    def require(request: Request, x_owner_token: str | None = Header(None)) -> None:
        tokens = [t.strip() for t in os.getenv(env_var, "").split(",") if t.strip()]
        if tokens:
            if _expired(env_var):
                raise HTTPException(403, f"{what}: the owner token expired, rotate {env_var}")
            given = (x_owner_token or "").encode()
            # compare against every token, no early exit, so timing does not tell which one matched
            if x_owner_token and sum(hmac.compare_digest(given, t.encode()) for t in tokens):
                return
            raise HTTPException(403, f"{what} needs a valid X-Owner-Token")
        # request.client is the TCP peer, not a forwarded header, so it cannot be spoofed by the caller
        if request.client and is_loopback(request.client.host):
            return
        raise HTTPException(403, f"{what} is local only; set {env_var} to allow a remote owner")

    return require


publisher_only = owner_only("PUBLISHER_OWNER_TOKEN", "publisher setup")
