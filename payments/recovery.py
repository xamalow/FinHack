"""Recovery of payments stuck in `pending` (crash or facilitator error after the transfer landed).

The USDC contract is the source of truth: `authorizationState(payer, nonce)` says whether the
EIP-3009 authorization was executed, and the `AuthorizationUsed` event gives the tx hash.
- used           -> mark settled with the on-chain tx hash, the payer gets the content
- unused, expired -> the authorization can never execute any more, release the reservation
- unused, recent  -> a payment may still be in flight, leave it pending
"""
import time

from web3 import AsyncWeb3

from payments import config, store
from payments.balances import w3

AUTHORIZATION_ABI = [{
    "name": "authorizationState", "type": "function", "stateMutability": "view",
    "inputs": [{"name": "authorizer", "type": "address"}, {"name": "nonce", "type": "bytes32"}],
    "outputs": [{"name": "", "type": "bool"}],
}]
AUTHORIZATION_USED_TOPIC = "0x" + AsyncWeb3.keccak(text="AuthorizationUsed(address,bytes32)").hex().removeprefix("0x")
# authorizations are valid PAYMENT_TIMEOUT_SECONDS; after that plus a margin, an unused one is dead
EXPIRY_SECONDS = config.PAYMENT_TIMEOUT_SECONDS + 60
LOOKBACK_BLOCKS = 3000  # ~100 minutes on Base
LOG_CHUNK = 100  # the public Base RPC rejects larger log queries (413)

usdc = w3.eth.contract(address=AsyncWeb3.to_checksum_address(config.USDC_ADDRESS), abi=AUTHORIZATION_ABI)


async def authorization_used(payer, nonce):
    return await usdc.functions.authorizationState(
        AsyncWeb3.to_checksum_address(payer), bytes.fromhex(nonce.removeprefix("0x"))).call()


async def find_authorization_tx(payer, nonce):
    latest = await w3.eth.block_number
    payer_topic = "0x" + "0" * 24 + payer.lower().removeprefix("0x")
    nonce_topic = "0x" + nonce.lower().removeprefix("0x").rjust(64, "0")
    to_block = latest
    while to_block > latest - LOOKBACK_BLOCKS:
        from_block = max(to_block - LOG_CHUNK + 1, latest - LOOKBACK_BLOCKS + 1)
        logs = await w3.eth.get_logs({
            "address": usdc.address, "fromBlock": from_block, "toBlock": to_block,
            "topics": [AUTHORIZATION_USED_TOPIC, payer_topic, nonce_topic],
        })
        if logs:
            return "0x" + logs[0]["transactionHash"].hex().removeprefix("0x")
        to_block = from_block - 1
    return None


async def reconcile(row):
    """Returns ("settled", tx_hash), ("released", None) or ("pending", None) for a pending transactions row."""
    if await authorization_used(row["payer"], row["nonce"]):
        tx_hash = await find_authorization_tx(row["payer"], row["nonce"])
        if tx_hash:
            store.mark_settled(row["tx_id"], tx_hash)
            return "settled", tx_hash
        return "pending", None
    if time.time() - row["ts"] > EXPIRY_SECONDS:
        store.release(row["tx_id"])
        return "released", None
    return "pending", None
