"""Single entry point to code owned by other roles.

P2 provides sessions, offers, tiers, publisher wallet and log_event (/shared).
P1 provides get_content. Until they are merged, everything falls back to
payments/mock_p2.py. Once /shared exists, only this file changes.
"""
from payments import mock_p2

try:
    from shared.events import log_event
except ImportError:
    log_event = mock_p2.log_event

get_session = mock_p2.get_session
get_offer = mock_p2.get_offer
set_offer_status = mock_p2.set_offer_status
get_tier_price = mock_p2.get_tier_price
get_publisher_wallet = mock_p2.get_publisher_wallet
get_content = mock_p2.get_content
