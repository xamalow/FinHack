"""Write the audit chain head on-chain, so the event history up to now can no longer be rewritten unnoticed.

Sends a 0 ETH transaction from the publisher signing key to itself, with the data field
"doubloon-audit:<event_id>:<chain_hash>". Needs a little ETH for gas on that address.
Anyone can later compare GET /compliance/audit-head and /compliance/audit-chain with the transaction.

    python scripts/anchor_audit.py            # dry run: prints the head and the signer
    python scripts/anchor_audit.py --send
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web3 import Web3  # noqa: E402

from shared import audit_chain, config, db, signing  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    with db.connect() as conn:
        result = audit_chain.verify(conn)
    if not result["ok"]:
        sys.exit(f"Audit chain is broken, not anchoring: {result['problems'][:3]}")
    account = signing.publisher_account()
    data = f"doubloon-audit:{audit_chain_head_id(result)}:{result['head']}"
    print(f"chain ok ({result['checked']} events), head {result['head']}\nsigner {account.address}\ndata {data}")
    if not args.send:
        print("Dry run. Add --send to write it on-chain.")
        return

    w3 = Web3(Web3.HTTPProvider(config.env("RPC_URL", "https://sepolia.base.org")))
    tx = {"to": account.address, "value": 0, "data": Web3.to_hex(text=data), "nonce": w3.eth.get_transaction_count(account.address),
          "chainId": w3.eth.chain_id, "gas": 60000, "maxFeePerGas": w3.eth.gas_price * 2, "maxPriorityFeePerGas": w3.eth.max_priority_fee}
    tx_hash = w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction)
    print(f"anchored: {config.EXPLORER_URL}/tx/{tx_hash.hex()}")


def audit_chain_head_id(result):
    with db.connect() as conn:
        return audit_chain.head(conn)["event_id"]


if __name__ == "__main__":
    main()
