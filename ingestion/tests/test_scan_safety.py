"""The scan only reaches public websites (no localhost, private network or cloud metadata endpoint)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routers.publisher_scan import router
from ingestion.crawl import UnsafeURL, check_public_url


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.delenv("SCAN_ALLOW_PRIVATE_HOSTS", raising=False)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/",
    "http://192.168.1.1/admin",
    "http://[::1]/",
    "file:///etc/passwd",
    "ftp://example.com/",
])
def test_non_public_targets_are_refused(strict, url):
    with pytest.raises(UnsafeURL):
        check_public_url(url)


def test_public_address_is_allowed(strict):
    check_public_url("http://93.184.216.34/")  # a public IPv4 literal, no DNS lookup needed


def test_scan_endpoint_answers_400_for_a_metadata_url(strict):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, client=("127.0.0.1", 50000))
    res = client.post("/publisher/scan", json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert res.status_code == 400 and "non-public" in res.json()["detail"]


def test_dev_opt_in_allows_a_local_site(monkeypatch):
    monkeypatch.setenv("SCAN_ALLOW_PRIVATE_HOSTS", "1")
    check_public_url("http://localhost:8001/")
