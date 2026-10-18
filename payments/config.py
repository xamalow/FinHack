import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

NETWORK = os.getenv("NETWORK", "eip155:84532")
RPC_URL = os.getenv("RPC_URL", "https://sepolia.base.org")
USDC_ADDRESS = os.getenv("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
EXPLORER_URL = os.getenv("EXPLORER_URL", "https://sepolia.basescan.org")
DB_PATH = os.getenv("DB_PATH", str(ROOT / "finhack.db"))
RECEIPT_TTL_HOURS = int(os.getenv("RECEIPT_TTL_HOURS", "24"))
PAYMENT_TIMEOUT_SECONDS = 120

# Paid route -> tier name, from agent.md 6.3
ROUTE_TIERS = {"t010": "single_fact", "t050": "small_table", "t200": "full_section"}


def usdc_to_atomic(price_usdc):
    return int(round(float(price_usdc) * 1_000_000))
