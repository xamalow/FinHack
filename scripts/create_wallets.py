"""Generate 1 publisher wallet and buyer wallets (4 by default).

Private keys are written to .env (never committed). Only addresses are printed.
Existing keys are kept, so running it twice does not lose funded wallets.

    python scripts/create_wallets.py                                   # testnet, .env
    python scripts/create_wallets.py --env-file .env.mainnet --buyers 1   # dedicated mainnet wallets
"""
import argparse
from pathlib import Path

from eth_account import Account

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
KEYS = []


def read_env():
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def main():
    global ENV_PATH, KEYS
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--buyers", type=int, default=4)
    args = parser.parse_args()
    ENV_PATH = ROOT / args.env_file
    KEYS = ["PUBLISHER_PRIVATE_KEY"] + [f"BUYER_PRIVATE_KEY_{i}" for i in range(1, args.buyers + 1)]
    env = read_env()
    new_lines = []
    for key in KEYS:
        if not env.get(key):
            acct = Account.create()
            env[key] = acct.key.hex()
            new_lines.append(f"{key}={env[key]}")

    if not env.get("PUBLISHER_WALLET_ADDRESS"):
        addr = Account.from_key(env["PUBLISHER_PRIVATE_KEY"]).address
        new_lines.append(f"PUBLISHER_WALLET_ADDRESS={addr}")

    if new_lines:
        with ENV_PATH.open("a") as f:
            f.write("\n" + "\n".join(new_lines) + "\n")

    for key in KEYS:
        print(f"{key.replace('_PRIVATE_KEY', ''):<12} {Account.from_key(env[key]).address}")


if __name__ == "__main__":
    main()
