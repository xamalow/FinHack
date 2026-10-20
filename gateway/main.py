"""Gateway entry point. One FastAPI app for every role's routers.

Run from the repo root:  uvicorn gateway.main:app --reload --port 8000
"""

from __future__ import annotations

import importlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from gateway import p1_bridge
from gateway.routers import audit, compliance, discovery, events, kya, rules, session
from shared import config, db, retention

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gateway")

# Routers owned by other roles, registered as soon as they exist on main.
OPTIONAL_ROUTERS = [
    "gateway.routers.publisher_scan",  # P1
    "payments.router",                 # P3: /query, /receipt, /transactions, /balance, /publisher/stats
    "payments.buyer_router",           # P3: /buyer/run, /buyer/approve
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    config.jwt_secret()  # fail fast if JWT_SECRET is missing
    try:
        retention.purge()  # personal data past its retention period (shared/retention.py)
    except Exception as e:
        log.warning("Retention purge skipped: %s", e)
    if p1_bridge.using_mock():
        log.warning("Catalog is the P2 mock (gateway/mock_catalog.json) until P1 ingestion is available")
    yield


app = FastAPI(title="FinHack gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.env_list("CORS_ORIGINS") or ["http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Agent-Id", "X-Agent-Wallet", "PAYMENT-SIGNATURE",
                   "X-Owner-Token", "Last-Event-ID"],
    expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger UI loads its own scripts
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.url.path.startswith(("/query", "/receipt", "/compliance", "/audit", "/events", "/session")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


for module in (discovery, kya, session, rules, audit, events, compliance):
    app.include_router(module.router)

for name in OPTIONAL_ROUTERS:
    try:
        app.include_router(importlib.import_module(name).router)
        log.info("Registered %s", name)
    except ModuleNotFoundError as e:
        if not e.name or not name.startswith(e.name):
            raise  # a real import error inside an existing module
        log.info("%s not present yet, skipped", name)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "catalog_source": "mock" if p1_bridge.using_mock() else "p1"}
