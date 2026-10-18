"""End-to-end test of GET /balance, balance_changed polling and GET /publisher/stats
on Base Sepolia (spends 0.10 test USDC per run).

Start:  .venv/bin/uvicorn payments.dev_app:app --port 4022
Run:    .venv/bin/python payments/e2e_balances_stats.py
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


async def get_events(http):
    """dev_app exposes /dev/events, the P2 gateway exposes /events."""
    r = await http.get(f"{BASE}/dev/events")
    if r.status_code == 404:
        r = await http.get(f"{BASE}/events", params={"after_id": 0, "limit": 10000})
    return r.json()


async def main():
    async with httpx.AsyncClient(timeout=30) as http:
        publisher = os.environ.get("PUBLISHER_WALLET_ADDRESS") or (await http.get(f"{BASE}/publisher/stats")).json()["publisher_wallet"]

        r = await http.get(f"{BASE}/balance/{publisher}")
        check("GET /balance publisher -> 200", r.status_code == 200, r.json())
        publisher_before = r.json()["balance_atomic"]

        r = await http.get(f"{BASE}/balance/not-an-address")
        check("GET /balance invalid address -> 400", r.status_code == 400, r.status_code)

        stats_before = (await http.get(f"{BASE}/publisher/stats")).json()

        run = (await http.post(f"{BASE}/buyer/run", json={
            "mission": "I need the 2025 market share of the top European battery manufacturer, one figure.",
            "budget_usdc": 5.0, "wallet": int(os.getenv("E2E_WALLET", "1"))})).json()
        for _ in range(240):
            state = (await http.get(f"{BASE}/buyer/runs/{run['run_id']}")).json()
            if state["status"] in {"done", "refused", "failed"}:
                break
            await asyncio.sleep(0.5)
        check("0.10 purchase completes", state["status"] == "done", state["status"])
        session_id = state["session_id"]

        changes = []
        for _ in range(20):
            events = await get_events(http)
            changes = [e for e in events if e["type"] == "balance_changed" and e["session_id"] == session_id]
            if {c["payload"]["role"] for c in changes} >= {"buyer", "publisher"}:
                break
            await asyncio.sleep(1)
        by_role = {c["payload"]["role"]: c["payload"] for c in changes}
        check("balance_changed for publisher +0.10", by_role.get("publisher", {}).get("delta_atomic") == 100000,
              by_role.get("publisher", {}).get("delta_atomic"))
        check("balance_changed for buyer -0.10", by_role.get("buyer", {}).get("delta_atomic") == -100000,
              by_role.get("buyer", {}).get("delta_atomic"))
        for c in changes:
            print("    ", c["summary"])

        publisher_after = (await http.get(f"{BASE}/balance/{publisher}")).json()["balance_atomic"]
        check("on-chain publisher balance +0.10", publisher_after - publisher_before == 100000,
              publisher_after - publisher_before)

        stats = (await http.get(f"{BASE}/publisher/stats")).json()
        check("stats paid_requests +1", stats["paid_requests"] == stats_before["paid_requests"] + 1, stats["paid_requests"])
        check("stats revenue +0.10", abs(stats["revenue_usdc"] - stats_before["revenue_usdc"] - 0.10) < 1e-9,
              stats["revenue_usdc"])
        check("stats requests +2 (402 then 200)", stats["requests"] == stats_before["requests"] + 2, stats["requests"])
        check("stats average = revenue / paid",
              abs(stats["average_usdc"] - stats["revenue_usdc"] / stats["paid_requests"]) < 1e-6, stats["average_usdc"])
        print("    ", stats)

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
