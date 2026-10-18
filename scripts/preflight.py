"""Pre-demo check: run it 5 minutes before going on stage.

    .venv/bin/python scripts/preflight.py [--gateway http://localhost:8000] [--frontend http://localhost:3000]

Checks config, gateway, catalog, activated publisher, facilitator, RPC and wallet balances.
Exit code 1 if anything blocks the demo (FAIL), 0 otherwise (WARN does not block).
"""
import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

NETWORK = os.getenv("NETWORK", "eip155:84532")
RPC_URL = os.getenv("RPC_URL", "https://sepolia.base.org")
USDC_ADDRESS = os.getenv("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
DEMO_NEEDS_USDC = 2.10  # one 0.10 sale + one 2.00 sale
BALANCE_OF_ABI = [{"name": "balanceOf", "type": "function", "stateMutability": "view",
                   "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]}]

results = []


def report(level, name, detail=""):
    results.append(level)
    print(f"{level:<4} {name}" + (f"  ({detail})" if detail else ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default=os.getenv("GATEWAY_PUBLIC_URL", "http://localhost:8000").rstrip("/"))
    parser.add_argument("--frontend", default="http://localhost:3000")
    args = parser.parse_args()

    print("== config")
    for var in ["JWT_SECRET", "ANTHROPIC_API_KEY", "PUBLISHER_WALLET_ADDRESS", "BUYER_PRIVATE_KEY_1"]:
        report("OK" if os.getenv(var) else ("WARN" if var == "ANTHROPIC_API_KEY" else "FAIL"),
               f"{var} set", "" if os.getenv(var) else "missing in .env")
    mainnet = NETWORK == "eip155:8453"
    report("OK" if NETWORK in ("eip155:84532", "eip155:8453") else "WARN", "network",
           "Base mainnet, REAL USDC" if mainnet else NETWORK)

    print("== gateway")
    with httpx.Client(timeout=15) as http:
        try:
            health = http.get(f"{args.gateway}/health").json()
            report("OK", "gateway up", args.gateway)
            report("OK" if health.get("catalog_source") == "p1" else "WARN", "catalog from P1 scan",
                   f"source={health.get('catalog_source')}, scan the site in onboarding if 'mock'")
        except Exception as e:
            report("FAIL", "gateway up", f"{args.gateway}: {type(e).__name__}")
            health = None

        manifest = None
        if health is not None:
            r = http.get(f"{args.gateway}/.well-known/ai-data.json")
            if r.status_code == 200:
                manifest = r.json()
                report("OK", "publisher activated", f"pays to {manifest['payment']['pay_to']}")
            else:
                report("WARN", "publisher activated", "manifest 404: do onboarding (rules, wallet, Activate) first")
            try:
                sales = http.get(f"{args.gateway}/transactions").json()
                report("OK" if not sales else "WARN", "fresh database",
                       "no sales yet" if not sales else
                       f"{len(sales)} sale(s) already: the Sales agent will not re-sell a section the same agent bought "
                       "today, start from an empty DB_PATH for a rehearsal")
            except Exception:
                pass

        try:
            http.get(args.frontend)
            report("OK", "frontend up", args.frontend)
        except Exception:
            report("WARN", "frontend up", f"{args.frontend} not reachable")

        print("== facilitator and chain")
        try:
            kinds = http.get(f"{FACILITATOR_URL}/supported").json().get("kinds", [])
            ok = any(k.get("network") == NETWORK and k.get("scheme") == "exact" for k in kinds)
            report("OK" if ok else "FAIL", "facilitator supports exact on " + NETWORK, FACILITATOR_URL)
        except Exception as e:
            report("FAIL", "facilitator reachable", f"{FACILITATOR_URL}: {type(e).__name__}")

    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=BALANCE_OF_ABI)
        report("OK", "RPC reachable", f"block {w3.eth.block_number}")
    except Exception as e:
        report("FAIL", "RPC reachable", f"{RPC_URL}: {type(e).__name__}")
        usdc = None

    if usdc is not None:
        print("== wallets (USDC on-chain)")
        for i in range(1, 5):
            key = os.getenv(f"BUYER_PRIVATE_KEY_{i}")
            if not key:
                continue
            address = Account.from_key(key).address
            balance = usdc.functions.balanceOf(address).call() / 1_000_000
            level = "OK" if balance >= DEMO_NEEDS_USDC else ("FAIL" if i == 1 else "WARN")
            report(level, f"buyer {i} {address}", f"{balance:.2f} USDC, demo needs {DEMO_NEEDS_USDC:.2f}"
                   + ("" if level == "OK" else (", send USDC on the Base network to this address" if NETWORK == "eip155:8453"
                                               else ", refill at faucet.circle.com (Base Sepolia)")))
        pay_to = (manifest or {}).get("payment", {}).get("pay_to") or os.getenv("PUBLISHER_WALLET_ADDRESS")
        if pay_to:
            report("OK", f"publisher {pay_to}", f"{usdc.functions.balanceOf(Web3.to_checksum_address(pay_to)).call() / 1_000_000:.2f} USDC")

    blocking = results.count("FAIL")
    print(f"\n{results.count('OK')} ok, {results.count('WARN')} warning(s), {blocking} blocking")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
