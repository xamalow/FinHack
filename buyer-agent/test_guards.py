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


def test_wallet_balance_too_low_refused():
    assert "wallet holds 0.05" in agent.check_wallet_balance(0.10, 50_000)


def test_wallet_balance_enough_or_unknown_passes():
    assert agent.check_wallet_balance(0.10, 100_000) is None
    assert agent.check_wallet_balance(2.00, None) is None


def _agent(budget, wallet_atomic):
    a = agent.BuyerAgent(mission="m", limits=agent.Limits(budget_usdc=budget),
                         private_key="0x" + "11" * 32, manifest_url="http://x")
    a.wallet_atomic = wallet_atomic
    return a


def test_spendable_is_capped_by_onchain_wallet():
    assert _agent(5.0, 1_500_000).spendable_usdc == 1.5
    assert _agent(1.0, 9_000_000).spendable_usdc == 1.0
    assert _agent(5.0, None).spendable_usdc == 5.0


# ---------------------------------------------------------------- velocity, manifest signature, receipt

import time as _time  # noqa: E402

from eth_account import Account  # noqa: E402

from shared import signing  # noqa: E402


def entries(*amounts, ago=60):
    return [{"ts": _time.time() - ago, "amount_usdc": a} for a in amounts]


def test_daily_cap_refuses():
    limits = agent.Limits(budget_usdc=50, max_per_day_usdc=3.0)
    ok, _, reason = agent.check_velocity(entries(1.0, 1.5), 1.0, limits)
    assert not ok and "daily cap" in reason


def test_old_purchases_do_not_count_toward_the_daily_cap():
    limits = agent.Limits(budget_usdc=50, max_per_day_usdc=3.0)
    assert agent.check_velocity(entries(2.5, ago=90000), 1.0, limits)[0]


def test_hourly_count_refuses():
    limits = agent.Limits(budget_usdc=50, max_tx_per_hour=2)
    ok, _, reason = agent.check_velocity(entries(0.1, 0.1), 0.1, limits)
    assert not ok and "one hour" in reason


def test_purchases_just_under_the_threshold_force_approval():
    limits = agent.Limits(budget_usdc=50, approval_threshold_usdc=1.0, structuring_count=3)
    ok, force, reason = agent.check_velocity(entries(0.95, 0.90), 0.99, limits)
    assert ok and force and "structuring" in reason
    assert agent.check_velocity(entries(0.10, 0.10), 0.10, limits)[1] is False


def test_ledger_is_per_wallet(tmp_path):
    ledger = agent.SpendLedger(tmp_path / "l.jsonl")
    ledger.record("0xAAA", "off_1", 0.5, "0x1", PUBLISHER)
    ledger.record("0xBBB", "off_2", 0.7, "0x2", PUBLISHER)
    assert [e["offer_id"] for e in ledger.entries("0xaaa")] == ["off_1"]


MANIFEST = {"publisher": "Velstrand", "gateway": "http://pub.example", "payment": {"pay_to": PUBLISHER}}
URL = "http://pub.example/.well-known/ai-data.json"


def test_manifest_signer_is_pinned_then_enforced(monkeypatch):
    monkeypatch.delenv("BUYER_REQUIRE_SIGNED_MANIFEST", raising=False)
    pins = {}
    signed = signing.sign_manifest(MANIFEST)
    ok, _, signer, pin_now = agent.check_manifest_signature(signed, URL, pins)
    assert ok and pin_now
    pins["http://pub.example"] = signer
    assert agent.check_manifest_signature(signed, URL, pins)[0]

    tampered = {**signed, "payment": {"pay_to": "0x000000000000000000000000000000000000dEaD"}}
    ok, reason, _, _ = agent.check_manifest_signature(tampered, URL, pins)
    assert not ok and "changed after signing" in reason

    other = Account.create()
    body = {k: v for k, v in MANIFEST.items()}
    body["signer"] = other.address
    from eth_account.messages import encode_defunct
    resigned = {**body, "signature": "0x" + other.sign_message(encode_defunct(
        text=signing.MANIFEST_DOMAIN + signing.canonical(body))).signature.hex().removeprefix("0x")}
    ok, reason, _, _ = agent.check_manifest_signature(resigned, URL, pins)
    assert not ok and "key changed" in reason

    ok, reason, _, _ = agent.check_manifest_signature(MANIFEST, URL, pins)
    assert not ok and "not signed" in reason  # downgrade to an unsigned manifest after pinning


def test_unsigned_manifest_refused_when_required(monkeypatch):
    monkeypatch.setenv("BUYER_REQUIRE_SIGNED_MANIFEST", "1")
    assert not agent.check_manifest_signature(MANIFEST, URL, {})[0]


def test_license_receipt_check():
    receipt = signing.sign_receipt({"offer_id": "off_1", "tx_hash": "0xabc", "payer": PUBLISHER.lower(),
                                    "amount_atomic": 100000})
    signer = signing.publisher_account().address
    assert agent.check_license_receipt(receipt, "0xabc", PUBLISHER, 0.10, signer) == []
    assert agent.check_license_receipt({**receipt, "amount_atomic": 1}, "0xabc", PUBLISHER, 0.10, signer)
    assert agent.check_license_receipt(None, "0xabc", PUBLISHER, 0.10, signer) == ["no license receipt"]
