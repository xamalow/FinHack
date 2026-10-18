"""Single entry point to code owned by other roles.

P2 implements this interface in gateway/integration.py (sessions, offers, tiers,
publisher wallet, log_event, and P1's get_content). Mocks from payments/mock_p2.py
are used when the gateway package is absent, or with P3_USE_MOCKS=1 (dev_app.py).
"""
import os

try:
    if os.getenv("P3_USE_MOCKS") == "1":  # payments/dev_app.py: P3 alone, even when the gateway package exists
        raise ModuleNotFoundError(name="gateway")
    from gateway.integration import (  # noqa: F401
        get_content,
        get_offer,
        get_publisher_wallet,
        get_session,
        get_tier_price,
        log_event,
        set_offer_status,
    )
    USING_MOCKS = False
except ModuleNotFoundError as e:
    if e.name not in ("gateway", "gateway.integration"):
        raise
    from payments import mock_p2

    log_event = mock_p2.log_event
    get_session = mock_p2.get_session
    get_offer = mock_p2.get_offer
    set_offer_status = mock_p2.set_offer_status
    get_tier_price = mock_p2.get_tier_price
    get_publisher_wallet = mock_p2.get_publisher_wallet
    get_content = mock_p2.get_content
    USING_MOCKS = True
