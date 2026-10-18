"""POST /buyer/run, POST /buyer/approve, GET /buyer/runs/{run_id} (agent.md 6.5, P3).

The buyer agent lives in /buyer-agent and only talks HTTP to the gateway.
This router starts it in the background and relays human approvals.

These routes spend the buyer's wallets, so only its owner may call them:
- BUYER_OWNER_TOKEN set: header X-Owner-Token must match it, from anywhere;
- not set: only connections from this machine (loopback socket address) are accepted.
"""
import asyncio
import importlib.util
import os
import secrets

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

import httpx

from payments import balances, config, deps
from shared.owner import owner_only
from payments import router as payments_router

_spec = importlib.util.spec_from_file_location("buyer_agent", config.ROOT / "buyer-agent" / "agent.py")
buyer_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(buyer_agent)

require_owner = owner_only("BUYER_OWNER_TOKEN", "buyer controls")


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


@router.get("/buyer/treasury")
async def buyer_treasury():
    """Owner view of the buyer wallets: on-chain USDC, spending by this gateway's runs, and the spend limits."""
    limits = buyer_agent.Limits(budget_usdc=float(os.getenv("BUYER_BUDGET_USDC", "5.00")))
    wallets = []
    for i in range(1, 5):
        key = os.getenv(f"BUYER_PRIVATE_KEY_{i}")
        if not key:
            continue
        address = buyer_agent.Account.from_key(key).address
        try:
            onchain = await balances.read_balance(address) / 1_000_000
        except Exception:
            onchain = None
        runs = [a for a in RUNS.values() if a.account.address == address]
        wallets.append({
            "wallet": i, "address": address, "balance_usdc_onchain": onchain,
            "runs": len(runs), "spent_usdc": round(sum(a.spent_usdc for a in runs), 6),
            "receipts": [r for a in runs for r in a.receipts],
        })
    known = [w["balance_usdc_onchain"] for w in wallets if w["balance_usdc_onchain"] is not None]
    return {
        "network": config.NETWORK,
        "limits": {"budget_usdc": limits.budget_usdc, "max_per_tx_usdc": limits.max_per_tx_usdc,
                   "approval_threshold_usdc": limits.approval_threshold_usdc},
        "total_balance_usdc_onchain": round(sum(known), 6),
        "total_spent_usdc": round(sum(w["spent_usdc"] for w in wallets), 6),
        "wallets": wallets,
    }


@router.post("/buyer/replay-last")
async def buyer_replay_last(run_id: str | None = Body(None, embed=True)):
    """Security demo button: replays the last paid request (of a given run, or the latest on this gateway).
    The gateway answers 409 and logs replay_rejected in the live view."""
    if run_id in RUNS and RUNS[run_id].last_paid_request:
        result = await RUNS[run_id].replay_last_payment()
        return {"replayed_offer_id": RUNS[run_id].last_paid_request["json"]["offer_id"], **result}
    # Default: the latest paid request on this gateway, from any buyer (test agent or buyer-mcp connector).
    last = payments_router.LAST_PAID
    if last is None:
        return JSONResponse({"error": "no_paid_request_to_replay"}, status_code=404)
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.post(last["url"], headers=last["headers"], json=last["json"])
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
    return {"replayed_offer_id": last["json"]["offer_id"], "status_code": r.status_code, "body": body,
            "delivered": r.status_code == 200}


@router.post("/buyer/approve")
async def buyer_approve(offer_id: str = Body(...), approved: bool = Body(True)):
    if not approvals.resolve(offer_id, approved):
        return JSONResponse({"error": "no_pending_approval", "offer_id": offer_id}, status_code=404)
    return {"offer_id": offer_id, "approved": approved}
