"""Owner-only routes: who may change the publisher setup, or spend the buyer's wallets.

A route protected with `owner_only("PUBLISHER_OWNER_TOKEN")` accepts a request when:
- the env var is set and the request carries the same value in `X-Owner-Token` (constant-time compare), or
- the env var is empty and the request comes from this machine (loopback TCP peer; X-Forwarded-For is ignored).

Everything else gets 403. Agents never call these routes: they only use discovery, KYA, the Sales agent and
the paid routes, which stay public.
"""
import hmac
import os

from fastapi import Header, HTTPException, Request

LOOPBACK = {"127.0.0.1", "::1"}


def owner_only(env_var: str, what: str = "this action"):
    def require(request: Request, x_owner_token: str | None = Header(None)) -> None:
        expected = os.getenv(env_var, "")
        if expected:
            if x_owner_token and hmac.compare_digest(x_owner_token.encode(), expected.encode()):
                return
            raise HTTPException(403, f"{what} needs a valid X-Owner-Token")
        # request.client is the TCP peer, not a forwarded header, so it cannot be spoofed by the caller
        if request.client and request.client.host in LOOPBACK:
            return
        raise HTTPException(403, f"{what} is local only; set {env_var} to allow a remote owner")

    return require


publisher_only = owner_only("PUBLISHER_OWNER_TOKEN", "publisher setup")
