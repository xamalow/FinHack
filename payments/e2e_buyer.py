"""End-to-end buyer agent test on Base Sepolia (spends 2.10 test USDC per run).

Start:  .venv/bin/uvicorn payments.dev_app:app --port 4022
Run:    .venv/bin/python payments/e2e_buyer.py
"""
import asyncio
import os
import sys

import httpx

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:4022")
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))


async def wait_for(http, run_id, statuses, timeout=120):
    for _ in range(timeout * 2):
        state = (await http.get(f"{BASE}/buyer/runs/{run_id}")).json()
        if state["status"] in statuses:
            return state
        await asyncio.sleep(0.5)
    return state


async def main():
    async with httpx.AsyncClient(timeout=30) as http:
        run = (await http.post(f"{BASE}/buyer/run", json={
            "mission": "I need the 2025 market share of the top European battery manufacturer, one figure.",
            "budget_usdc": 5.0})).json()
        state = await wait_for(http, run["run_id"], {"done", "refused", "failed"})
        check("0.10 purchase completes", state["status"] == "done", state["status"])
        check("budget updated to 4.90", abs(state["remaining_usdc"] - 4.90) < 1e-9, state["remaining_usdc"])
        check("data received", bool(state["data"] and state["data"][0]["content"]))
        if state["receipts"]:
            print("     tx", state["receipts"][0]["explorer"])

        run = (await http.post(f"{BASE}/buyer/run", json={
            "mission": "I need the full battery market section with methodology.", "budget_usdc": 5.0})).json()
        state = await wait_for(http, run["run_id"], {"waiting_approval", "done", "refused", "failed"})
        check("2.00 offer pauses for human approval", state["status"] == "waiting_approval", state["status"])
        offer_id = (state.get("pending_offer") or {}).get("offer_id")
        r = await http.post(f"{BASE}/buyer/approve", json={"offer_id": offer_id, "approved": True})
        check("approve accepted", r.status_code == 200, r.status_code)
        state = await wait_for(http, run["run_id"], {"done", "refused", "failed"})
        check("2.00 purchase completes after approval", state["status"] == "done", state["status"])
        if state["receipts"]:
            print("     tx", state["receipts"][0]["explorer"])

        run = (await http.post(f"{BASE}/buyer/run", json={
            "mission": "I need the full battery market section with methodology.", "budget_usdc": 1.5})).json()
        state = await wait_for(http, run["run_id"], {"done", "refused", "failed"})
        check("offer above budget refused, nothing spent", state["status"] == "refused" and state["spent_usdc"] == 0,
              state["status"])

        run = (await http.post(f"{BASE}/buyer/run", json={
            "mission": "I need the full battery market section with methodology.", "budget_usdc": 5.0})).json()
        state = await wait_for(http, run["run_id"], {"waiting_approval", "done", "refused", "failed"})
        offer_id = (state.get("pending_offer") or {}).get("offer_id")
        await http.post(f"{BASE}/buyer/approve", json={"offer_id": offer_id, "approved": False})
        state = await wait_for(http, run["run_id"], {"done", "refused", "failed"})
        check("approval denied -> refused, nothing spent", state["status"] == "refused" and state["spent_usdc"] == 0,
              state["status"])

        events = [e["type"] for e in (await http.get(f"{BASE}/dev/events")).json()]
        for t in ["mission_started", "manifest_read", "discover_called", "kya_signed", "buyer_message",
                  "offer_evaluated", "approval_requested", "approval_granted", "offer_refused_budget",
                  "payment_signed", "data_received", "mission_done"]:
            check(f"event {t} emitted", t in events)

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
