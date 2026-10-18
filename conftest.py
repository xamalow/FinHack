"""Settings shared by every test suite, set before any module reads them."""
import os

os.environ.setdefault("SANCTIONS_ORACLE", "off")  # no network in tests; the oracle has its own tests
os.environ.setdefault("PUBLISHER_SIGNING_KEY", "0x" + "5a" * 32)  # test-only key, never funded

import tempfile  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="doubloon-tests-")
os.environ.setdefault("BUYER_LEDGER_PATH", os.path.join(_tmp, "ledger.jsonl"))
os.environ.setdefault("BUYER_PINNED_SIGNERS_PATH", os.path.join(_tmp, "pins.json"))
