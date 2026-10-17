"""Generate 1 publisher wallet and 4 buyer wallets for Base Sepolia tests.

Private keys are written to .env (never committed). Only addresses are printed.
Existing keys in .env are kept, so running it twice does not lose funded wallets.
"""
from pathlib import Path

from eth_account import Account

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

KEYS = ["PUBLISHER_PRIVATE_KEY"] + [f"BUYER_PRIVATE_KEY_{i}" for i in range(1, 5)]


def read_env():
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def main():
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
