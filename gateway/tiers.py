"""Confirmed pricing tiers (agent.md 6.3). Deterministic checks only ever use these."""

from __future__ import annotations

from typing import Any

from shared import db

# The demo rate card, used until the publisher confirms its own rules.
DEFAULT_TIERS: list[dict[str, Any]] = [
    {"tier": "single_fact", "route": "t010", "price_usdc": 0.10, "scope": "one figure (one company, one metric, one year)"},
    {"tier": "small_table", "route": "t050", "price_usdc": 0.50, "scope": "up to 5 companies or 5 years on one metric"},
    {"tier": "full_section", "route": "t200", "price_usdc": 2.00, "scope": "a full report section with methodology"},
]

# P3 serves exactly these paid routes.
PAID_ROUTES = {"t010", "t050", "t200"}


def route_for_price(price_usdc: float) -> str:
    """0.10 -> t010, 0.50 -> t050, 2.00 -> t200 (price in cents, 3 digits)."""
    return f"t{round(price_usdc * 100):03d}"


def current_tiers() -> list[dict[str, Any]]:
    rules = db.confirmed_rules()
    return rules["tiers_json"] if rules else [dict(t) for t in DEFAULT_TIERS]


def tiers_by_name() -> dict[str, dict[str, Any]]:
    return {t["tier"]: t for t in current_tiers()}
