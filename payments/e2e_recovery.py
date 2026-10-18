"""End-to-end test of stuck-payment recovery and rate limiting on Base Sepolia (spends 0.10 test USDC).

Start:  .venv/bin/uvicorn payments.dev_app:app --port 4022
Run:    .venv/bin/python payments/e2e_recovery.py
"""
import asyncio
import os
import sys
from pathlib import Path

import httpx
from eth_account import Account

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from x402 import x402Client
from x402.http import decode_payment_required_header, encode_payment_signature_header
from x402.mechanisms.evm.exact import register_exact_evm_client
from x402.mechanisms.evm.signers import EthAccountSigner

from payments import config
from shared.keys import load_private_key
from payments.mock_p2 import DEV_TOKEN

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:4022")
AUTH = {"Authorization": f"Bearer {DEV_TOKEN}"}
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))


async def main():
    x402 = x402Client()
    register_exact_evm_client(x402, EthAccountSigner(Account.from_key(load_private_key("BUYER_PRIVATE_KEY_1"))),
                              networks=config.NETWORK)
    async with httpx.AsyncClient(timeout=120) as http:
        offer = (await http.post(f"{BASE}/dev/offer", params={"tier": "single_fact"})).json()
        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]}, headers=AUTH)
        payload = await x402.create_payment_payload(decode_payment_required_header(r.headers["payment-required"]))
        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": encode_payment_signature_header(payload)})
        paid_tx = r.json().get("receipt", {}).get("tx_hash", "")
        check("real payment settles", r.status_code == 200 and paid_tx.startswith("0x"), r.status_code)

        row = (await http.post(f"{BASE}/dev/simulate-lost-delivery", params={"offer_id": offer["offer_id"]})).json()
        check("crash simulated: row pending without hash", row["status"] == "pending" and row["tx_hash"] is None)

        # The public RPC indexes event logs a few seconds after the block: a client retries on "still being settled".
        for attempt in range(15):
            r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]}, headers=AUTH)
            if r.status_code != 409 or "still being settled" not in r.text:
                break
            await asyncio.sleep(2)
        print(f"     recovered after {attempt + 1} request(s)")
        body = r.json()
        recovered_tx = body.get("receipt", {}).get("tx_hash", "")
        check("retry recovers the payment from the chain and delivers", r.status_code == 200 and bool(body.get("content")),
              r.status_code)
        check("recovered tx hash is the original on-chain one", recovered_tx.lower() == paid_tx.lower(), recovered_tx[:12])
        tx = next(t for t in (await http.get(f"{BASE}/transactions")).json() if t["offer_id"] == offer["offer_id"])
        check("row settled again with the hash", tx["status"] == "settled" and tx["tx_hash"] == paid_tx.lower())

        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]}, headers=AUTH)
        check("after recovery, a new request is a replay -> 409", r.status_code == 409, r.status_code)

        codes = [(await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]}, headers=AUTH)).status_code
                 for _ in range(35)]
        check("flood on paid route -> 429 after the per-minute limit", 429 in codes, f"{codes.count(429)} x 429")

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
