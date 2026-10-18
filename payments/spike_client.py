"""x402 spike client: pays the 0.01 USDC route with BUYER_PRIVATE_KEY_1.

Run:  .venv/bin/python payments/spike_client.py [url]
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account
from x402 import x402Client
from x402.http import decode_payment_required_header, decode_payment_response_header
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm.exact import register_exact_evm_client
from x402.mechanisms.evm.signers import EthAccountSigner

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.keys import load_private_key  # noqa: E402

EXPLORER_URL = os.getenv("EXPLORER_URL", "https://sepolia.basescan.org")


async def main(url):
    account = Account.from_key(load_private_key("BUYER_PRIVATE_KEY_1"))
    print("buyer", account.address)

    client = x402Client()
    register_exact_evm_client(client, EthAccountSigner(account), networks=os.getenv("NETWORK", "eip155:84532"))

    async with x402HttpxClient(client, timeout=60) as http:
        resp = await http.get(url)

    print("status", resp.status_code)
    print("body", resp.text)
    if resp.status_code == 402 and resp.headers.get("payment-required"):
        required = decode_payment_required_header(resp.headers["payment-required"])
        print("refused", required.error)
    header = resp.headers.get("payment-response")
    if header:
        settle = decode_payment_response_header(header)
        print("settle", settle.model_dump())
        if settle.transaction:
            print(f"{EXPLORER_URL}/tx/{settle.transaction}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4021/spike"))
