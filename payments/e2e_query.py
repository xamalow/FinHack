"""End-to-end test of /query on Base Sepolia (spends 0.10 test USDC per run).

Start:  .venv/bin/uvicorn payments.dev_app:app --port 4022
Run:    .venv/bin/python payments/e2e_query.py
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
from payments.mock_p2 import DEV_TOKEN

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:4022")
AUTH = {"Authorization": f"Bearer {DEV_TOKEN}"}
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))


async def sign_for(http, x402, route, offer_id):
    r = await http.post(f"{BASE}/query/{route}", json={"offer_id": offer_id}, headers=AUTH)
    required = decode_payment_required_header(r.headers["payment-required"])
    payload = await x402.create_payment_payload(required)
    return r, required, encode_payment_signature_header(payload)


async def main():
    x402 = x402Client()
    account = Account.from_key(os.environ["BUYER_PRIVATE_KEY_1"])
    register_exact_evm_client(x402, EthAccountSigner(account), networks=config.NETWORK)

    async with httpx.AsyncClient(timeout=90) as http:
        offer = (await http.post(f"{BASE}/dev/offer", params={"tier": "single_fact"})).json()

        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]})
        check("no session token -> 401", r.status_code == 401, r.status_code)

        r, required, sig = await sign_for(http, x402, "t010", offer["offer_id"])
        accept = required.accepts[0]
        check("no payment -> 402", r.status_code == 402)
        check("402 amount is server-side tier price", accept.amount == "100000", accept.amount)
        check("402 payTo is publisher wallet", accept.pay_to.lower() == os.environ["PUBLISHER_WALLET_ADDRESS"].lower())

        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": sig})
        body = r.json()
        tx_hash = body.get("receipt", {}).get("tx_hash")
        check("valid payment -> 200 with content", r.status_code == 200 and bool(body.get("content")), r.status_code)
        check("PAYMENT-RESPONSE header present", "payment-response" in r.headers)
        print("     tx", body.get("receipt", {}).get("explorer"))

        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": sig})
        check("replay same payment, same offer -> 409", r.status_code == 409, r.status_code)

        offer2 = (await http.post(f"{BASE}/dev/offer", params={"tier": "single_fact"})).json()
        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer2["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": sig})
        check("replay same nonce on a new offer -> 409", r.status_code == 409, r.status_code)

        offer3 = (await http.post(f"{BASE}/dev/offer", params={"tier": "small_table"})).json()
        _, _, cheap_sig = await sign_for(http, x402, "t010", offer2["offer_id"])
        r = await http.post(f"{BASE}/query/t050", json={"offer_id": offer3["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": cheap_sig})
        check("0.10 payment for a 0.50 offer -> 402, nothing delivered", r.status_code == 402 and "content" not in r.json(), r.status_code)

        r = await http.post(f"{BASE}/query/t010", json={"offer_id": offer3["offer_id"]}, headers=AUTH)
        check("route t010 for a small_table offer -> 400", r.status_code == 400, r.status_code)

        r = await http.get(f"{BASE}/receipt/{tx_hash}", headers=AUTH)
        check("receipt re-download, same payer -> 200", r.status_code == 200 and bool(r.json().get("content")), r.status_code)

        r = await http.get(f"{BASE}/receipt/{tx_hash}")
        check("receipt without session -> 401", r.status_code == 401, r.status_code)

        ghost = (await http.post(f"{BASE}/dev/offer", params={"tier": "single_fact", "content_id": "rpt_ghost#s9"})).json()
        r = await http.post(f"{BASE}/query/t010", json={"offer_id": ghost["offer_id"]}, headers=AUTH)
        check("unknown content -> 409 before any 402", r.status_code == 409 and "payment-required" not in r.headers,
              r.status_code)

        late = (await http.post(f"{BASE}/dev/offer", params={"tier": "single_fact",
                                                             "content_id": "rpt_battery_2025#s4"})).json()
        r, _, late_sig = await sign_for(http, x402, "t010", late["offer_id"])
        check("content available -> 402", r.status_code == 402, r.status_code)
        await http.post(f"{BASE}/dev/exclude", params={"content_id": "rpt_battery_2025#s4"})
        r = await http.post(f"{BASE}/query/t010", json={"offer_id": late["offer_id"]},
                            headers={**AUTH, "PAYMENT-SIGNATURE": late_sig})
        txs = (await http.get(f"{BASE}/transactions")).json()
        check("content excluded after 402 -> 409, payment not taken",
              r.status_code == 409 and not any(t["offer_id"] == late["offer_id"] for t in txs), r.status_code)

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
