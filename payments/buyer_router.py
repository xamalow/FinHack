"""POST /buyer/run, POST /buyer/approve, GET /buyer/runs/{run_id} (agent.md 6.5, P3).

The buyer agent lives in /buyer-agent and only talks HTTP to the gateway.
This router starts it in the background and relays human approvals.

These routes spend the buyer's wallets, so only its owner may call them:
- BUYER_OWNER_TOKEN set: header X-Owner-Token must match it, from anywhere;
- not set: only connections from this machine (loopback socket address) are accepted.
"""
import asyncio
import hmac
import importlib.util
import os
import secrets

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from payments import config, deps

_spec = importlib.util.spec_from_file_location("buyer_agent", config.ROOT / "buyer-agent" / "agent.py")
buyer_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(buyer_agent)

LOOPBACK = {"127.0.0.1", "::1"}


def require_owner(request: Request, x_owner_token: str | None = Header(None)):
    expected = os.getenv("BUYER_OWNER_TOKEN", "")
    if expected:
        if x_owner_token and hmac.compare_digest(x_owner_token.encode(), expected.encode()):
            return
        raise HTTPException(403, "buyer controls need a valid X-Owner-Token")
    # request.client is the TCP peer, not a forwarded header, so it cannot be spoofed by the caller
    if request.client and request.client.host in LOOPBACK:
        return
    raise HTTPException(403, "buyer controls are local only; set BUYER_OWNER_TOKEN to allow a remote owner")


router = APIRouter(dependencies=[Depends(require_owner)])
approvals = buyer_agent.Approvals()
RUNS = {}
TASKS = set()


@router.post("/buyer/run")
async def buyer_run(
    mission: str = Body(...),
    budget_usdc: float = Body(float(os.getenv("BUYER_BUDGET_USDC", "5.00"))),
    wallet: int = Body(1, ge=1, le=4),
):
    agent = buyer_agent.BuyerAgent(
        mission=mission,
        limits=buyer_agent.Limits(budget_usdc=budget_usdc),
        private_key=os.environ[f"BUYER_PRIVATE_KEY_{wallet}"],
        manifest_url=os.getenv("BUYER_MANIFEST_URL", "http://127.0.0.1:4022/.well-known/ai-data.json"),
        log_event=deps.log_event,
        approvals=approvals,
    )
    run_id = "run_" + secrets.token_hex(4)
    RUNS[run_id] = agent

    async def run():
        try:
            await agent.run()
        except Exception as e:
            agent.finish("failed", f"Buyer crashed: {type(e).__name__}: {e}")

    task = asyncio.create_task(run())
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)
    return {"run_id": run_id, "agent": agent.account.address}


@router.get("/buyer/runs/{run_id}")
async def buyer_status(run_id: str):
    agent = RUNS.get(run_id)
    if agent is None:
        return JSONResponse({"error": "unknown_run"}, status_code=404)
    return {"run_id": run_id, **agent.result()}


@router.post("/buyer/replay-last")
async def buyer_replay_last(run_id: str | None = Body(None, embed=True)):
    """Security demo button: replays the last paid request of a run (default: the latest run that paid).
    The gateway answers 409 and logs replay_rejected in the live view."""
    candidates = [RUNS[run_id]] if run_id in RUNS else [a for a in reversed(RUNS.values()) if a.last_paid_request]
    if not candidates or candidates[0].last_paid_request is None:
        return JSONResponse({"error": "no_paid_request_to_replay"}, status_code=404)
    result = await candidates[0].replay_last_payment()
    return {"replayed_offer_id": candidates[0].last_paid_request["json"]["offer_id"], **result}


@router.post("/buyer/approve")
async def buyer_approve(offer_id: str = Body(...), approved: bool = Body(True)):
    if not approvals.resolve(offer_id, approved):
        return JSONResponse({"error": "no_pending_approval", "offer_id": offer_id}, status_code=404)
    return {"offer_id": offer_id, "approved": approved}
