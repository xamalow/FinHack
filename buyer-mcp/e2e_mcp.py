"""End-to-end test of the buyer connector, driven over MCP stdio exactly like Claude Desktop does.

Needs: the gateway running with the publisher activated, and a funded Base Sepolia buyer wallet in .env.
Spends about 2.10 test USDC (one figure, then one full section after owner approval).

    .venv/bin/python buyer-mcp/e2e_mcp.py
Use the same DB_PATH as the gateway, so the connector's events land in the live view.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))


async def call(session, tool, **args):
    res = await session.call_tool(tool, args)
    text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text, "_is_error": res.isError}


def offer_of(reply):
    """The connector's ask_seller result holds the priced offer somewhere under 'offer'."""
    if isinstance(reply.get("offer"), dict):
        return reply["offer"]
    for v in reply.values():
        if isinstance(v, dict) and isinstance(v.get("offer"), dict):
            return v["offer"]
    return None


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "buyer-mcp" / "server.py")],
                                   env={**os.environ}, cwd=str(ROOT))
    start = max([e["event_id"] for e in httpx.get(f"{GATEWAY}/events", params={"after_id": 0, "limit": 10000}).json()] or [0])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            check("connector exposes the 4 tools", tools == ["ask_seller", "buy", "search_data", "wallet_status"], tools)

            before = await call(session, "wallet_status")
            print("     wallet:", {k: before.get(k) for k in ("wallet", "balance_usdc_onchain", "remaining_usdc")})
            check("wallet_status reads the on-chain balance", isinstance(before.get("balance_usdc_onchain"), (int, float)))

            found = await call(session, "search_data", question="2025 European market share of the leading battery manufacturer")
            check("search_data returns the free summary", "_raw" not in found, json.dumps(found)[:120])

            reply = await call(session, "ask_seller",
                               message="I need the 2025 market share of the leading European battery manufacturer, one figure.")
            offer = offer_of(reply)
            print("     seller:", json.dumps(reply)[:300])
            check("ask_seller gets a priced offer", offer and offer.get("offer_id"), (offer or {}).get("price_usdc"))

            bought = await call(session, "buy", offer_id=offer["offer_id"]) if offer else {}
            print("     buy:", json.dumps(bought)[:300])
            explorer = json.dumps(bought)
            tx_ok = "sepolia.basescan.org/tx/0x" in explorer
            check("buy pays and returns the data with an explorer link", tx_ok)

            fake = await call(session, "buy", offer_id="off_never_offered")
            check("buy refuses an offer the seller never made", "sepolia.basescan.org/tx/" not in json.dumps(fake), json.dumps(fake)[:120])

            reply2 = await call(session, "ask_seller", message="Now I need the full battery market share section with methodology.")
            offer2 = offer_of(reply2)
            print("     seller 2:", (offer2 or {}).get("tier"), (offer2 or {}).get("price_usdc"))
            if offer2 and float(offer2.get("price_usdc", 0)) > 1.0:
                blocked = await call(session, "buy", offer_id=offer2["offer_id"])
                check("offer above 1.00 needs the owner's approval", "basescan.org/tx/" not in json.dumps(blocked), json.dumps(blocked)[:140])
                approved = await call(session, "buy", offer_id=offer2["offer_id"], owner_approved=True)
                check("with owner_approved=true the 2.00 purchase goes through", "basescan.org/tx/0x" in json.dumps(approved),
                      json.dumps(approved)[:140])
            else:
                check("second offer is above the approval threshold", False, json.dumps(reply2)[:200])

            after = await call(session, "wallet_status")
            print("     wallet after:", {k: after.get(k) for k in ("balance_usdc_onchain", "remaining_usdc", "spent_usdc")})

    events = httpx.get(f"{GATEWAY}/events", params={"after_id": start, "limit": 10000}).json()
    types = [e["type"] for e in events]
    tagged = [e for e in events if e["actor"] == "buyer" and (e.get("payload") or {}).get("source") == "mcp"]
    check("connector events reach the live view (source=mcp)", bool(tagged), f"{len(tagged)} buyer events")
    for t in ["kya_verified", "offer_validated", "payment_settled", "content_delivered"]:
        check(f"gateway event {t}", t in types)
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
