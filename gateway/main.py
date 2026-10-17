"""Gateway entry point. One FastAPI app for every role's routers (agent.md section 3).

Run from the repo root:  uvicorn gateway.main:app --reload --port 8000
"""

from __future__ import annotations

import importlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway import p1_bridge
from gateway.routers import audit, discovery, events, kya, rules, session
from shared import config, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gateway")

# Routers owned by other roles, registered as soon as they exist on main.
OPTIONAL_ROUTERS = [
    "gateway.routers.publisher_scan",  # P1
    "gateway.routers.payments",        # P3
    "gateway.routers.buyer",           # P3
    "gateway.routers.balances",        # P3
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    config.jwt_secret()  # fail fast if JWT_SECRET is missing
    if p1_bridge.using_mock():
        log.warning("Catalog is the P2 mock (gateway/mock_catalog.json) until P1 ingestion is available")
    yield


app = FastAPI(title="FinHack gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.env_list("CORS_ORIGINS") or ["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE"],
)

for module in (discovery, kya, session, rules, audit, events):
    app.include_router(module.router)

for name in OPTIONAL_ROUTERS:
    try:
        app.include_router(importlib.import_module(name).router)
        log.info("Registered %s", name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise
        log.info("%s not present yet, skipped", name)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "catalog_source": "mock" if p1_bridge.using_mock() else "p1"}
