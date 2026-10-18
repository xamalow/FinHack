"""Owner check on the /buyer/* routes.  Run: .venv/bin/python -m pytest payments/tests -q

GET /buyer/runs/unknown has no side effect: 404 means the caller got through, 403 means it was blocked.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from payments import buyer_router

app = FastAPI()
app.include_router(buyer_router.router)


def client(host):
    return TestClient(app, client=(host, 50000))


@pytest.fixture(autouse=True)
def no_token(monkeypatch):
    monkeypatch.delenv("BUYER_OWNER_TOKEN", raising=False)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_local_owner_allowed_without_token(host):
    assert client(host).get("/buyer/runs/unknown").status_code == 404


@pytest.mark.parametrize("path, method", [
    ("/buyer/runs/unknown", "get"),
    ("/buyer/run", "post"),
    ("/buyer/approve", "post"),
    ("/buyer/replay-last", "post"),
])
def test_remote_caller_blocked_without_token(path, method):
    c = client("203.0.113.7")
    r = c.get(path) if method == "get" else c.post(path, json={"mission": "x", "offer_id": "off_1"})
    assert r.status_code == 403


def test_forwarded_header_does_not_make_remote_local():
    r = client("203.0.113.7").get("/buyer/runs/unknown", headers={"X-Forwarded-For": "127.0.0.1"})
    assert r.status_code == 403


def test_token_required_when_set_even_locally(monkeypatch):
    monkeypatch.setenv("BUYER_OWNER_TOKEN", "s3cret-owner-token")
    assert client("127.0.0.1").get("/buyer/runs/unknown").status_code == 403
    assert client("127.0.0.1").get("/buyer/runs/unknown", headers={"X-Owner-Token": "wrong"}).status_code == 403


def test_remote_owner_with_token_allowed(monkeypatch):
    monkeypatch.setenv("BUYER_OWNER_TOKEN", "s3cret-owner-token")
    r = client("203.0.113.7").get("/buyer/runs/unknown", headers={"X-Owner-Token": "s3cret-owner-token"})
    assert r.status_code == 404
