"""POST /buyer/run, POST /buyer/approve, GET /buyer/runs/{run_id} (agent.md 6.5, P3).

The buyer agent lives in /buyer-agent and only talks HTTP to the gateway.
This router starts it in the background and relays human approvals.
"""
import asyncio
import importlib.util
import os
import secrets

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from payments import config, deps

_spec = importlib.util.spec_from_file_location("buyer_agent", config.ROOT / "buyer-agent" / "agent.py")
buyer_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(buyer_agent)

router = APIRouter()
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


@router.post("/buyer/approve")
async def buyer_approve(offer_id: str = Body(...), approved: bool = Body(True)):
    if not approvals.resolve(offer_id, approved):
        return JSONResponse({"error": "no_pending_approval", "offer_id": offer_id}, status_code=404)
    return {"offer_id": offer_id, "approved": approved}
