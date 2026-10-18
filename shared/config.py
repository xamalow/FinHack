"""Environment configuration shared by every role. Values come from `.env`."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    value = env(name)
    return int(value) if value else default


def env_list(name: str) -> list[str]:
    return [v.strip() for v in env(name).split(",") if v.strip()]


NETWORK = env("NETWORK", "eip155:84532")
USDC_ADDRESS = env("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
EXPLORER_URL = env("EXPLORER_URL", "https://sepolia.basescan.org")

GATEWAY_PUBLIC_URL = env("GATEWAY_PUBLIC_URL", "http://localhost:8000/")
PUBLISHER_NAME = env("PUBLISHER_NAME", "Demo Research Firm")
DEMO_SITE_URL = env("DEMO_SITE_URL")

SESSION_TTL_SECONDS = env_int("SESSION_TTL_SECONDS", 900)
OFFER_TTL_SECONDS = env_int("OFFER_TTL_SECONDS", 300)
KYA_CHALLENGE_TTL_SECONDS = env_int("KYA_CHALLENGE_TTL_SECONDS", 120)
DAILY_SECTION_LIMIT = env_int("DAILY_SECTION_LIMIT", 3)
MAX_NEGOTIATION_ROUNDS = env_int("MAX_NEGOTIATION_ROUNDS", 3)

LLM_MODEL = env("LLM_MODEL", "claude-opus-5-5")
SALES_AGENT_EFFORT = env("SALES_AGENT_EFFORT", "low")
RULES_PARSER_EFFORT = env("RULES_PARSER_EFFORT", "medium")


def db_path() -> Path:
    """Read at call time so tests can point DB_PATH at a temporary file."""
    path = Path(env("DB_PATH", "finhack.db"))
    return path if path.is_absolute() else REPO_ROOT / path


def jwt_secret() -> str:
    secret = env("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set. Add it to .env (see .env.example).")
    if len(secret) < 32 and not _warned_short_secret:
        # Session tokens are HS256: a short secret can be brute-forced offline from one token.
        _warn_short_secret()
    return secret


_warned_short_secret = False


def _warn_short_secret() -> None:
    global _warned_short_secret
    _warned_short_secret = True
    import sys
    print("WARNING: JWT_SECRET is shorter than 32 characters, session tokens can be forged. "
          "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"", file=sys.stderr)


def kya_blocklist() -> set[str]:
    return {w.lower() for w in env_list("KYA_BLOCKLIST")}
