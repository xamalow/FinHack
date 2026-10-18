"""Print ETH and USDC balances on Base Sepolia for every wallet in .env."""
import os
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RPC_URL = os.getenv("RPC_URL", "https://sepolia.base.org")
USDC_ADDRESS = os.getenv("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
BALANCE_OF_ABI = [{
    "name": "balanceOf", "type": "function", "stateMutability": "view",
    "inputs": [{"name": "account", "type": "address"}],
    "outputs": [{"name": "", "type": "uint256"}],
}]


def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=BALANCE_OF_ABI)
    keys = ["PUBLISHER_PRIVATE_KEY"] + [f"BUYER_PRIVATE_KEY_{i}" for i in range(1, 5)]
    for key in keys:
        if not os.getenv(key):
            continue
        addr = Account.from_key(os.environ[key]).address
        eth = w3.from_wei(w3.eth.get_balance(addr), "ether")
        usdc_bal = usdc.functions.balanceOf(addr).call() / 1_000_000
        print(f"{key.replace('_PRIVATE_KEY', ''):<12} {addr}  {usdc_bal:>10.6f} USDC  {eth:.6f} ETH")


if __name__ == "__main__":
    main()
