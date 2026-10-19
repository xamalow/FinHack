"""Rebuild the Base Sepolia part of payments/docs/ONCHAIN_EVIDENCE.md from the chain.

Reads USDC Transfer logs (eth_getLogs) from our buyer wallets to the publisher wallets, so the list comes from
the chain, not from our database. The context of a payment already in the file is kept; a new one is labelled
from the demo database when it knows the sale (Claude connector or test agent), else "integration and demo runs".

    .venv/bin/python scripts/onchain_evidence.py            # prints the new table
    .venv/bin/python scripts/onchain_evidence.py --write    # updates the doc in place
"""
import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))
from shared.keys import load_private_key  # noqa: E402

DOC = ROOT / "payments/docs/ONCHAIN_EVIDENCE.md"
RPC = "https://sepolia.base.org"
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
FIRST_BLOCK = 48255700  # just before the first x402 payment (2026-10-17)
PUBLISHERS = {
    "0x797486c95c00d40f30e41996b0da5417ff256844": "PUBLISHER (generated)",
    "0xa82763beadcd9052e6e1e9f348bd5cd4e57e07fe": "PUBLISHER (MetaMask)",
}


def rpc(method, params):
    r = httpx.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def topic(address):
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


def logs_to(payee, start, end):
    out, chunk, block = [], 1000, start
    while block <= end:
        hi = min(block + chunk - 1, end)
        try:
            out += rpc("eth_getLogs", [{"address": USDC, "fromBlock": hex(block), "toBlock": hex(hi),
                                        "topics": [TRANSFER, None, topic(payee)]}])
            block = hi + 1
        except Exception:
            if chunk <= 100:
                raise
            chunk //= 2
    return out


def buyers():
    from eth_account import Account
    out = {}
    for i in range(1, 5):
        key = load_private_key(f"BUYER_PRIVATE_KEY_{i}")
        if key:
            out[Account.from_key(key).address.lower()] = f"BUYER_{i}"
    return out


def known_contexts():
    text = DOC.read_text()
    return {m.group(2): m.group(1).strip() for m in re.finditer(r"\| [\d.]+ \| ([^|]+) \| \[0x[0-9a-f]+…\]\(https://sepolia\.basescan\.org/tx/(0x[0-9a-f]{64})\)", text)}


def demo_contexts():
    """tx hash -> context, from the demo database when it recorded the sale."""
    out = {}
    db = ROOT / "demo.db"
    if not db.exists():
        return out
    conn = sqlite3.connect(db)
    mcp = {r[0] for r in conn.execute("SELECT DISTINCT session_id FROM events WHERE payload_json LIKE '%\"source\": \"mcp\"%'")}
    for tx_hash, session in conn.execute(
            "SELECT t.tx_hash, o.session_id FROM transactions t JOIN offers o ON o.offer_id = t.offer_id WHERE t.status = 'settled'"):
        out[(tx_hash or "").lower()] = "Claude connector (MCP), live demo gateway" if session in mcp else "Test agent, live demo gateway"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    latest = int(rpc("eth_blockNumber", []), 16)
    wallets = buyers()
    old, demo = known_contexts(), demo_contexts()
    rows = []
    for payee, payee_label in PUBLISHERS.items():
        for log in logs_to(payee, FIRST_BLOCK, latest):
            payer = "0x" + log["topics"][1][-40:]
            if payer not in wallets:
                continue  # faucet or other transfers, not a sale
            rows.append({"block": int(log["blockNumber"], 16), "hash": log["transactionHash"], "payer": wallets[payer],
                         "payee": payee_label, "amount": int(log["data"], 16) / 1e6,
                         "ts": int(log["blockTimestamp"], 16) if log.get("blockTimestamp") else None})
    rows.sort(key=lambda r: r["block"])
    times = {}
    for r in rows:
        if r["block"] not in times:
            times[r["block"]] = r["ts"] or int(rpc("eth_getBlockByNumber", [hex(r["block"]), False])["timestamp"], 16)
        r["time"] = datetime.fromtimestamp(times[r["block"]], timezone.utc).strftime("%m-%d %H:%M")
        r["context"] = old.get(r["hash"]) or demo.get(r["hash"]) or "Integration and demo runs"

    total = sum(r["amount"] for r in rows)
    days = sorted({datetime.fromtimestamp(times[r["block"]], timezone.utc).strftime("%Y-%m-%d") for r in rows})
    table = ["| Time (UTC) | Block | Payer | Payee | Amount | Context | Tx |", "|---|---|---|---|---|---|---|"]
    table += [f"| {r['time']} | {r['block']} | {r['payer']} | {r['payee']} | {r['amount']:.2f} | {r['context']} | "
              f"[{r['hash'][:12]}…](https://sepolia.basescan.org/tx/{r['hash']}) |" for r in rows]
    summary = f"- Total: **{len(rows)} payments, {total:.2f} USDC**, from {days[0]} to {days[-1]} (UTC), read at block {latest}"
    print(summary)
    print("\n".join(table))
    if not args.write:
        return

    text = DOC.read_text()
    text = re.sub(r"- Total: \*\*.*", summary, text, count=1)
    text = re.sub(r"- Publisher wallet \(payTo\): .*",
                  "- Publisher wallets (payTo): [`0x797486c95c00d40F30E41996b0DA5417fF256844`](https://sepolia.basescan.org/address/0x797486c95c00d40F30E41996b0DA5417fF256844) "
                  "(generated, until 18 Oct) and [`0xa82763beAdCD9052e6e1e9f348Bd5Cd4E57e07FE`](https://sepolia.basescan.org/address/0xa82763beAdCD9052e6e1e9f348Bd5Cd4E57e07FE) "
                  "(the publisher's MetaMask, from 18 Oct)", text, count=1)
    start = text.index("## All payments to the publisher")
    end = text.index("Buyer wallets:", start)
    text = text[:start] + "## All payments to the publisher\n\n" + "\n".join(table) + "\n\n" + text[end:]
    text = re.sub(r"Regenerate: .*", "Regenerate: `.venv/bin/python scripts/onchain_evidence.py --write` (`eth_getLogs` on the USDC contract, "
                  "topic `Transfer`, `to` = a publisher wallet, `from` = one of our buyer wallets).", text, count=1)
    DOC.write_text(text)
    print(f"updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
