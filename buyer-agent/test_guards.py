"""Unit tests for the buyer's hardcoded checks.  Run: .venv/bin/python -m pytest buyer-agent -q"""
import importlib.util
from pathlib import Path

import pytest
from x402.schemas import PaymentRequired

_spec = importlib.util.spec_from_file_location("buyer_agent", Path(__file__).parent / "agent.py")
agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent)

PUBLISHER = "0x797486c95c00d40F30E41996b0DA5417fF256844"
LIMITS = agent.Limits(budget_usdc=5.0, max_per_tx_usdc=2.5, approval_threshold_usdc=1.0)


def payment_required(**override):
    accept = {"scheme": "exact", "network": "eip155:84532", "asset": agent.USDC_ADDRESS,
              "amount": "100000", "payTo": PUBLISHER, "maxTimeoutSeconds": 120,
              "extra": {"name": "USDC", "version": "2"}}
    accept.update(override)
    return PaymentRequired.model_validate({"x402Version": 2, "accepts": [accept]})


def test_offer_within_limits():
    assert agent.check_offer(0.10, 5.0, LIMITS) == (True, False, "within limits")


def test_offer_above_budget_refused():
    ok, _, reason = agent.check_offer(2.00, 1.50, LIMITS)
    assert not ok and "budget" in reason


def test_offer_above_cap_refused():
    ok, _, reason = agent.check_offer(3.00, 5.0, LIMITS)
    assert not ok and "cap" in reason


def test_offer_above_threshold_needs_approval():
    assert agent.check_offer(2.00, 5.0, LIMITS)[:2] == (True, True)


def test_offer_at_threshold_no_approval():
    assert agent.check_offer(1.00, 5.0, LIMITS)[:2] == (True, False)


def test_valid_402_passes():
    assert agent.check_payment_required(payment_required(), 0.10, PUBLISHER, 5.0, LIMITS) == []


@pytest.mark.parametrize("override, expected", [
    ({"payTo": "0x000000000000000000000000000000000000bEEF"}, "payTo"),
    ({"amount": "200000"}, "amount 200000 differs"),
    ({"network": "eip155:8453"}, "network"),
    ({"asset": "0x0000000000000000000000000000000000000001"}, "asset"),
    ({"scheme": "upto"}, "scheme"),
])
def test_tampered_402_rejected(override, expected):
    problems = agent.check_payment_required(payment_required(**override), 0.10, PUBLISHER, 5.0, LIMITS)
    assert any(expected in p for p in problems), problems


def test_402_above_remaining_budget_rejected():
    problems = agent.check_payment_required(payment_required(amount="2000000"), 2.00, PUBLISHER, 1.0, LIMITS)
    assert "amount above remaining budget" in problems


def test_rule_based_refuses_offer_above_budget():
    reply = {"action": "propose_offer", "offer": {"price_usdc": 2.0}}
    assert agent.rule_based_decision("m", 1.0, reply).decision == "refuse"


async def _approval_flow():
    import asyncio
    approvals = agent.Approvals()
    waiter = asyncio.create_task(approvals.wait("off_1", 5))
    await asyncio.sleep(0)
    assert approvals.resolve("off_1", True)
    return await waiter


def test_approval_resolves():
    import asyncio
    assert asyncio.run(_approval_flow()) is True


def test_approval_times_out_as_refusal():
    import asyncio
    assert asyncio.run(agent.Approvals().wait("off_2", 0.01)) is False
