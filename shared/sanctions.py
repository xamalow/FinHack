"""Sanctions screening of wallet addresses (OFAC SDN list through the Chainalysis oracle).

Used on both sides of a sale:
- gateway: the agent wallet at KYA, the payer again right before settlement, the publisher payout wallet;
- buyer: the publisher's payTo before signing a payment.

Sources, in order:
1. the local blocklist (KYA_BLOCKLIST), for addresses the operator blocks itself;
2. the Chainalysis sanctions oracle, a free on-chain contract mirroring the OFAC SDN crypto addresses,
   `isSanctioned(address) -> bool` at 0x40C57923924B5c5c5455c48D93317139ADDaC8fb. It is read on Ethereum
   mainnet by default (an EVM address is the same on every chain, and the contract is not deployed at this
   address on Base mainnet).

When the oracle cannot be reached, SANCTIONS_FAIL_MODE decides: "closed" refuses, "open" lets the address
through and says so. Default: closed on Base mainnet (real money), open on testnet (demo).
SANCTIONS_ORACLE=off keeps the local blocklist only (tests, offline work).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass

import httpx

DEFAULT_ORACLE = "0x40C57923924B5c5c5455c48D93317139ADDaC8fb"
DEFAULT_RPC = "https://ethereum-rpc.publicnode.com"
IS_SANCTIONED_SELECTOR = "0xdf592f7d"  # keccak("isSanctioned(address)")[:4]
CACHE_SECONDS = 3600
MAINNET = "eip155:8453"

_cache: dict[str, tuple[float, bool]] = {}
_lock = threading.Lock()


@dataclass
class Screening:
    address: str
    blocked: bool
    sanctioned: bool | None  # None: the oracle could not be read
    source: str  # local_blocklist, chainalysis_oracle, oracle_off, oracle_unavailable
    detail: str

    def as_payload(self) -> dict:
        return asdict(self)


def oracle_address() -> str:
    return os.getenv("SANCTIONS_ORACLE", DEFAULT_ORACLE).strip()


def fail_mode() -> str:
    mode = os.getenv("SANCTIONS_FAIL_MODE", "").strip().lower()
    if mode in ("open", "closed"):
        return mode
    return "closed" if os.getenv("NETWORK", "eip155:84532") == MAINNET else "open"


def _local_blocklist() -> set[str]:
    return {w.strip().lower() for w in os.getenv("KYA_BLOCKLIST", "").split(",") if w.strip()}


def _call_oracle(address: str) -> bool:
    data = IS_SANCTIONED_SELECTOR + address.lower().removeprefix("0x").rjust(64, "0")
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": oracle_address(), "data": data}, "latest"]}
    r = httpx.post(os.getenv("SANCTIONS_RPC_URL", DEFAULT_RPC), json=body, timeout=8)
    r.raise_for_status()
    result = r.json().get("result")
    if not result or result == "0x":
        raise RuntimeError("no sanctions oracle at this address on this chain")
    return int(result, 16) == 1


def is_address(value: str) -> bool:
    v = (value or "").lower()
    return v.startswith("0x") and len(v) == 42 and all(c in "0123456789abcdef" for c in v[2:])


def screen(address: str) -> Screening:
    """Never raises. `blocked` is the decision to apply."""
    key = (address or "").lower()
    if not is_address(key):
        return Screening(address, True, None, "invalid", "not an EVM address")
    if key in _local_blocklist():
        return Screening(address, True, True, "local_blocklist", "address is on the operator blocklist")
    if oracle_address().lower() == "off":
        return Screening(address, False, None, "oracle_off", "oracle screening disabled, local blocklist only")

    with _lock:
        cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        sanctioned = cached[1]
    else:
        try:
            sanctioned = _call_oracle(key)
        except Exception as e:
            closed = fail_mode() == "closed"
            return Screening(address, closed, None, "oracle_unavailable",
                             f"oracle unreachable ({type(e).__name__}), fail {'closed' if closed else 'open'}")
        with _lock:
            _cache[key] = (time.time(), sanctioned)
    if sanctioned:
        return Screening(address, True, True, "chainalysis_oracle", "address is on the OFAC SDN list")
    return Screening(address, False, False, "chainalysis_oracle", "not on the OFAC SDN list")


def clear_cache() -> None:
    with _lock:
        _cache.clear()
