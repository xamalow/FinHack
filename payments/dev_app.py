"""Standalone app to run P3 before P2's gateway exists.

Run:  .venv/bin/uvicorn payments.dev_app:app --port 4022
P2 mounts the real routers with:
    app.include_router(payments.router.router)
    app.include_router(payments.buyer_router.router)
mock_gateway (manifest, discover, KYA, Sales agent, offer accept) is replaced by P2's endpoints.
"""
import os

# Before importing payments: this app always runs on the P2 mocks, with its own database and manifest,
# so it never touches the demo database or sends its buyer to the real gateway configured in .env.
os.environ["P3_USE_MOCKS"] = "1"
os.environ["DB_PATH"] = os.getenv("DEV_DB_PATH", "dev.db")
os.environ["BUYER_MANIFEST_URL"] = "http://127.0.0.1:4022/.well-known/ai-data.json"

from fastapi import FastAPI  # noqa: E402

from payments import buyer_router, mock_gateway, mock_p2, store  # noqa: E402
from payments.router import router  # noqa: E402

app = FastAPI()
app.include_router(router)
app.include_router(buyer_router.router)
app.include_router(mock_gateway.router)


@app.post("/dev/offer")
async def dev_offer(tier: str, content_id: str = "rpt_battery_2025#s2"):
    return mock_p2.create_offer("ses_dev", tier, [content_id])


@app.post("/dev/exclude")
async def dev_exclude(content_id: str):
    mock_p2.EXCLUDED.add(content_id)
    return {"excluded": sorted(mock_p2.EXCLUDED)}


@app.get("/dev/events")
async def dev_events():
    return mock_p2.EVENTS


@app.post("/dev/simulate-lost-delivery")
async def dev_simulate_lost_delivery(offer_id: str):
    """Puts a settled sale back in the state a crash would leave: row pending without tx hash, offer accepted."""
    with store._conn() as conn:
        conn.execute("UPDATE transactions SET status = 'pending', tx_hash = NULL WHERE offer_id = ?", (offer_id,))
    mock_p2.OFFERS[offer_id]["status"] = "accepted"
    return store.get_by_offer(offer_id)
