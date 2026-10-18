"""x402 spike: one FastAPI route sold at 0.01 USDC on Base Sepolia.

Run:  .venv/bin/uvicorn payments.spike_server:app --port 4021
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact import ExactEvmServerScheme

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

NETWORK = os.getenv("NETWORK", "eip155:84532")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
PAY_TO = os.environ["PUBLISHER_WALLET_ADDRESS"]

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(NETWORK, ExactEvmServerScheme())

routes = {
    "GET /spike": {
        "accepts": {
            "scheme": "exact",
            "payTo": PAY_TO,
            "price": "$0.01",
            "network": NETWORK,
        },
        "description": "x402 spike, one figure",
    }
}

app = FastAPI()
x402_mw = payment_middleware(routes, server)


@app.middleware("http")
async def x402_middleware(request, call_next):
    return await x402_mw(request, call_next)


@app.get("/spike")
async def spike():
    return {"metric": "battery_market_share_2025", "value": "31.4%"}


@app.get("/health")
async def health():
    return {"ok": True, "pay_to": PAY_TO, "network": NETWORK}
