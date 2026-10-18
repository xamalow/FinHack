"""Watermark, signed license receipt and encrypted keys."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from eth_account import Account

from payments import router, store, watermark
from shared import keys, signing

ROOT = Path(__file__).resolve().parents[2]
PAYER = "0x797486c95c00d40F30E41996b0DA5417fF256844"


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))


def test_watermark_traces_a_leak_back_to_its_sale():
    content = {"s2": "Aurelion holds 31.4% of the market. Second is Nordvolt."}
    marked, wid = watermark.apply(content, "off_1", PAYER, "internal_use_only")
    assert PAYER in marked["s2"] and wid in marked["s2"]
    leak = marked["s2"].split("\n\n[Licensed")[0]  # the reseller drops the visible license line
    sales = [{"offer_id": "off_1", "payer": PAYER.lower(), "tx_hash": "0x1"},
             {"offer_id": "off_2", "payer": PAYER.lower(), "tx_hash": "0x2"}]
    assert [s["offer_id"] for s in watermark.trace(leak, sales)] == ["off_1"]


def test_watermark_cannot_be_forged_without_the_secret(monkeypatch):
    wid = watermark.watermark_id("off_1", PAYER)
    monkeypatch.setenv("WATERMARK_SECRET", "another-secret")
    assert watermark.watermark_id("off_1", PAYER) != wid


def test_license_receipt_is_signed_stored_and_stable(monkeypatch):
    tx_id = store.reserve("off_1", "0x" + "01" * 32, PAYER, "0x" + "22" * 20, 100000)
    store.mark_settled(tx_id, "0x" + "ab" * 32)
    offer = {"offer_id": "off_1", "tier": "single_fact", "scope": "one figure", "license": "internal_use_only",
             "content_ids": ["s2"], "price_usdc": 0.10, "session_id": None}
    monkeypatch.setattr(router.deps, "log_event", lambda *a, **k: None)
    content, receipt = router.license_content(offer, {"s2": "Text. More."}, "0x" + "ab" * 32, PAYER)
    ok, signer, _ = signing.verify_receipt(receipt, signing.publisher_account().address)
    assert ok and receipt["amount_atomic"] == 100000 and receipt["payer"] == PAYER.lower()
    again, receipt2 = router.license_content(offer, {"s2": "Text. More."}, "0x" + "ab" * 32, PAYER)
    assert receipt2 == receipt and again == content  # re-delivery carries the same marks and receipt
    assert not signing.verify_receipt({**receipt, "amount_atomic": 1})[0]


def test_private_key_loads_from_an_encrypted_keystore(tmp_path, monkeypatch):
    acct = Account.create()
    path = tmp_path / "k.json"
    path.write_text(json.dumps(Account.encrypt(acct.key, "pw-for-test")))
    monkeypatch.delenv("BUYER_PRIVATE_KEY_9", raising=False)
    monkeypatch.setenv("BUYER_PRIVATE_KEY_9_KEYSTORE", str(path))
    monkeypatch.setenv("KEYSTORE_PASSWORD", "pw-for-test")
    assert Account.from_key(keys.load_private_key("BUYER_PRIVATE_KEY_9")).address == acct.address


def test_encrypt_keys_script_removes_plaintext_from_the_env_file(tmp_path):
    acct = Account.create()
    env_file = tmp_path / ".env"
    env_file.write_text(f"NETWORK=eip155:84532\nBUYER_PRIVATE_KEY_1={acct.key.hex()}\n")
    out = tmp_path / "keys"
    env = {**os.environ, "KEYSTORE_PASSWORD": "pw-for-test"}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "encrypt_keys.py"), "--env-file", str(env_file), "--out", str(out),
                    "--apply", "--rewrite-env", "--password-store", "none"], check=True, capture_output=True, env=env)
    text = env_file.read_text()
    assert acct.key.hex().removeprefix("0x") not in text and "BUYER_PRIVATE_KEY_1_KEYSTORE=" in text
    assert oct((out / "BUYER_PRIVATE_KEY_1.json").stat().st_mode)[-3:] == "600"
    keystore = json.loads((out / "BUYER_PRIVATE_KEY_1.json").read_text())
    assert Account.from_key(Account.decrypt(keystore, "pw-for-test")).address == acct.address
