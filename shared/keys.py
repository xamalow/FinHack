"""Private keys without plaintext in .env.

load_private_key("BUYER_PRIVATE_KEY_1") looks, in order, for:
1. NAME in the environment (plaintext, dev only, kept so nothing breaks);
2. NAME_KEYSTORE: path to an encrypted keystore (Web3 Secret Storage v3, scrypt + AES-128-CTR, the format
   of geth and MetaMask exports), whose password comes from the macOS Keychain (service "doubloon",
   account NAME) or, where there is no Keychain, from KEYSTORE_PASSWORD.

scripts/encrypt_keys.py moves the keys of an env file into keystores and the Keychain.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from eth_account import Account

ROOT = Path(__file__).resolve().parent.parent
KEYCHAIN_SERVICE = "doubloon"


def keychain_password(name: str) -> str:
    env = os.getenv("KEYSTORE_PASSWORD", "")
    if env:
        return env
    out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name, "-w"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"No password for {name} in the macOS Keychain (service {KEYCHAIN_SERVICE}). "
                           "Run scripts/encrypt_keys.py, or set KEYSTORE_PASSWORD.")
    return out.stdout.strip()


def _hex(key) -> str:
    h = key.hex()
    return h if h.startswith("0x") else "0x" + h


def load_private_key(name: str) -> str | None:
    plain = os.getenv(name, "").strip()
    if plain:
        return plain
    path = os.getenv(f"{name}_KEYSTORE", "").strip()
    if not path:
        return None
    file = Path(path) if Path(path).is_absolute() else ROOT / path
    return _hex(Account.decrypt(json.loads(file.read_text()), keychain_password(name)))


def has_key(name: str) -> bool:
    return bool(os.getenv(name, "").strip() or os.getenv(f"{name}_KEYSTORE", "").strip())
