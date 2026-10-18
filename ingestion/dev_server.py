"""Run the P1 endpoints alone, until P2's gateway registers the router.

Usage: python -m ingestion.dev_server [--port 8010] [--mock]
--mock loads the hand-written catalog instead of waiting for a scan.
"""
import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.routers.publisher_scan import router
from ingestion import store

app = FastAPI(title="P1 publisher data (dev)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    if args.mock:
        store.load_mock_catalog()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
