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
WATCHERS = {}


def is_address(address):
    return AsyncWeb3.is_address(address)


async def read_balance(address):
    """USDC balance in atomic units (6 decimals)."""
    return await usdc.functions.balanceOf(AsyncWeb3.to_checksum_address(address)).call()


def fmt(atomic):
    return f"{atomic / 1_000_000:.2f}"


class Watcher:
    def __init__(self, session_id):
        self.session_id = session_id
        self.roles = {}
        self.last = {}
        self.deadline = 0
        self.task = None

    async def add(self, roles, ttl):
        self.deadline = max(self.deadline, time.time() + ttl)
        for role, address in roles.items():
            address = address.lower()
            self.roles[address] = role
            if address not in self.last:
                self.last[address] = await read_balance(address)
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.loop())

    async def loop(self):
        try:
            while time.time() < self.deadline:
                await asyncio.sleep(POLL_SECONDS)
                for address, role in list(self.roles.items()):
                    try:
                        balance = await read_balance(address)
                    except Exception:
                        continue
                    old = self.last[address]
                    if balance != old:
                        self.last[address] = balance
                        delta = balance - old
                        deps.log_event(
                            self.session_id, "chain", "balance_changed",
                            f"{role.capitalize()} {'+' if delta > 0 else '-'}{fmt(abs(delta))} USDC (now {fmt(balance)})",
                            {"address": AsyncWeb3.to_checksum_address(address), "role": role,
                             "old_atomic": old, "new_atomic": balance, "delta_atomic": delta,
                             "balance_usdc": balance / 1_000_000},
                        )
        finally:
            WATCHERS.pop(self.session_id, None)


async def watch(session_id, roles, ttl=WATCH_TTL_SECONDS):
    """Start or extend the balance watch of a session. roles = {"buyer": addr, "publisher": addr}."""
    watcher = WATCHERS.get(session_id)
    if watcher is None:
        watcher = WATCHERS[session_id] = Watcher(session_id)
    await watcher.add(roles, ttl)
