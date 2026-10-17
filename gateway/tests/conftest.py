import os
import sys
from pathlib import Path

import pytest
from eth_account import Account

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

BLOCKED = Account.create()

# Must be set before shared.config is imported (load_dotenv never overrides these).
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-0123456789"
os.environ["KYA_BLOCKLIST"] = BLOCKED.address
os.environ["DEMO_SITE_URL"] = "https://demo-site.example"
os.environ["ANTHROPIC_API_KEY"] = "test-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from shared import db
    db.init_db()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from gateway.main import app
    with TestClient(app) as c:
        yield c
