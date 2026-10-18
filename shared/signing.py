"""Publisher signatures: the manifest (so a buyer can trust its payTo) and each license receipt.

Both are EIP-191 personal_sign signatures over canonical JSON (sorted keys, no spaces, UTF-8) with a
domain line in front, so a manifest signature can never be replayed as a receipt or the other way round.
Anyone can check them offline with any Ethereum library (recover the signer, compare with `signer`).

The signing key is the publisher's, not the payout wallet (that one stays in MetaMask). It comes from
PUBLISHER_SIGNING_KEY or PUBLISHER_SIGNING_KEY_KEYSTORE (shared/keys.py); without either, one is created
once in PUBLISHER_SIGNING_KEY_FILE (default .publisher_signing_key, mode 600, git-ignored), so the
signer address stays the same across restarts and buyers that pinned it keep trusting it.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct

from shared.keys import ROOT, load_private_key

log = logging.getLogger("signing")

MANIFEST_DOMAIN = "Doubloon signed manifest v1\n"
RECEIPT_DOMAIN = "Doubloon license receipt v1\n"

_account = None
_lock = threading.Lock()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _key_file() -> Path:
    path = Path(os.getenv("PUBLISHER_SIGNING_KEY_FILE", ".publisher_signing_key"))
    return path if path.is_absolute() else ROOT / path


def publisher_account():
    global _account
    with _lock:
        if _account is not None:
            return _account
        key = load_private_key("PUBLISHER_SIGNING_KEY")
        if not key:
            file = _key_file()
            if file.exists():
                key = file.read_text().strip()
            else:
                key = Account.create().key.hex()
                key = key if key.startswith("0x") else "0x" + key
                fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(key)
                log.warning("Created a publisher signing key in %s (set PUBLISHER_SIGNING_KEY_KEYSTORE in production)", file)
        _account = Account.from_key(key)
        return _account


def reset() -> None:
    """Forget the cached key (tests)."""
    global _account
    with _lock:
        _account = None


def _sign(obj: dict, domain: str) -> dict:
    account = publisher_account()
    body = {k: v for k, v in obj.items() if k != "signature"}
    body["signer"] = account.address
    signature = account.sign_message(encode_defunct(text=domain + canonical(body))).signature.hex()
    return {**body, "signature": signature if signature.startswith("0x") else "0x" + signature}


def _verify(obj: dict, domain: str, expected_signer: str | None = None) -> tuple[bool, str | None, str]:
    signature, signer = obj.get("signature"), obj.get("signer")
    if not signature or not signer:
        return False, None, "not signed"
    body = {k: v for k, v in obj.items() if k != "signature"}
    try:
        recovered = Account.recover_message(encode_defunct(text=domain + canonical(body)), signature=signature)
    except Exception:
        return False, None, "unreadable signature"
    if recovered.lower() != str(signer).lower():
        return False, recovered, "signature does not match the signer field (content changed after signing)"
    if expected_signer and recovered.lower() != expected_signer.lower():
        return False, recovered, f"signed by {recovered}, expected {expected_signer}"
    return True, recovered, "valid"


def sign_manifest(manifest: dict) -> dict:
    return _sign(manifest, MANIFEST_DOMAIN)


def verify_manifest(manifest: dict, expected_signer: str | None = None):
    return _verify(manifest, MANIFEST_DOMAIN, expected_signer)


def sign_receipt(receipt: dict) -> dict:
    return _sign({"type": "doubloon.license_receipt.v1", **receipt}, RECEIPT_DOMAIN)


def verify_receipt(receipt: dict, expected_signer: str | None = None):
    return _verify(receipt, RECEIPT_DOMAIN, expected_signer)
