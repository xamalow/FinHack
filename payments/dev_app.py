"""Standalone app to run the paid routes before P2's gateway exists.

Run:  .venv/bin/uvicorn payments.dev_app:app --port 4022
P2 mounts the real thing with: app.include_router(payments.router.router)
"""
from fastapi import FastAPI

from payments import mock_p2
from payments.router import router

app = FastAPI()
app.include_router(router)


@app.post("/dev/offer")
async def dev_offer(tier: str, content_id: str = "rpt_battery_2025#s2"):
    return mock_p2.create_offer("ses_dev", tier, [content_id])


@app.get("/dev/events")
async def dev_events():
    return mock_p2.EVENTS
