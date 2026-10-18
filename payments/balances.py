"""On-chain USDC balances (agent.md P3 item 6).

read_balance() calls balanceOf on the USDC contract. watch() polls the buyer and
publisher wallets of a session every 2 seconds and emits chain/balance_changed
on every change. /query starts a watch when it sends a 402, so the baseline is
read before the payment, whoever the buyer agent is.
"""
import asyncio
import time

from web3 import AsyncHTTPProvider, AsyncWeb3

from payments import config, deps

POLL_SECONDS = 2
WATCH_TTL_SECONDS = 120
BALANCE_OF_ABI = [{
    "name": "balanceOf", "type": "function", "stateMutability": "view",
    "inputs": [{"name": "account", "type": "address"}],
    "outputs": [{"name": "", "type": "uint256"}],
}]

w3 = AsyncWeb3(AsyncHTTPProvider(config.RPC_URL))
usdc = w3.eth.contract(address=AsyncWeb3.to_checksum_address(config.USDC_ADDRESS), abi=BALANCE_OF_ABI)


def is_address(address):
    return AsyncWeb3.is_address(address)


async def read_balance(address):
    """USDC balance in atomic units (6 decimals)."""
    return await usdc.functions.balanceOf(AsyncWeb3.to_checksum_address(address)).call()


def fmt(atomic):
    return f"{atomic / 1_000_000:.2f}"


class Watcher:
    """One poll loop for all watched wallets. Each wallet is watched once, whatever the number of
    sessions: a change is reported a single time, on the latest session that registered the wallet."""

    def __init__(self):
        self.wallets = {}  # address -> {"role", "session_id", "last", "deadline"}
        self.task = None

    async def add(self, session_id, roles, ttl):
        deadline = time.time() + ttl
        for role, address in roles.items():
            address = address.lower()
            entry = self.wallets.get(address)
            if entry is None:
                entry = self.wallets[address] = {"last": await read_balance(address), "deadline": 0}
            entry.update(role=role, session_id=session_id, deadline=max(entry["deadline"], deadline))
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.loop())

    async def loop(self):
        while self.wallets:
            await asyncio.sleep(POLL_SECONDS)
            for address, entry in list(self.wallets.items()):
                try:
                    balance = await read_balance(address)
                except Exception:
                    continue
                old = entry["last"]
                if balance != old:
                    entry["last"] = balance
                    delta = balance - old
                    deps.log_event(
                        entry["session_id"], "chain", "balance_changed",
                        f"{entry['role'].capitalize()} {'+' if delta > 0 else '-'}{fmt(abs(delta))} USDC (now {fmt(balance)})",
                        {"address": AsyncWeb3.to_checksum_address(address), "role": entry["role"],
                         "old_atomic": old, "new_atomic": balance, "delta_atomic": delta,
                         "balance_usdc": balance / 1_000_000},
                    )
                if time.time() > entry["deadline"]:
                    self.wallets.pop(address, None)


WATCHER = Watcher()


async def watch(session_id, roles, ttl=WATCH_TTL_SECONDS):
    """Start or extend the balance watch of a session's wallets. roles = {"buyer": addr, "publisher": addr}."""
    await WATCHER.add(session_id, roles, ttl)
