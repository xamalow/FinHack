import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routers.publisher_scan import router
from ingestion import store
from ingestion.catalog import SectionMetadata, finalize_item
from ingestion.leak_filter import build_index, contains_paid_figures

MOCK = json.loads((Path(__file__).resolve().parents[1] / "mock_catalog.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client(scanned):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, client=("127.0.0.1", 50000))  # the publisher, on its own machine


def test_scan_builds_the_full_catalog(scanned):
    catalog = store.get_catalog()
    assert [i["content_id"] for i in catalog] == sorted(i["content_id"] for i in MOCK)
    assert scanned["sellable"] == 16 and scanned["free"] == 4 and scanned["excluded"] == 1


def test_internal_notes_are_flagged_and_excluded(scanned):
    item = store.get_catalog_item("page_internal_notes#s1")
    assert item["sensitivity"] == "internal" and item["status"] == "excluded"
    assert scanned["flagged_internal"] == ["page_internal_notes#s1"]


def test_robots_txt_is_respected(scanned):
    assert any(u.endswith("/drafts/sodium-ion-draft.html") for u in scanned["blocked_by_robots"])
    assert not any("79.8" in t for _, t in store.get_texts_by_status())


def test_catalog_never_contains_a_paid_figure(scanned):
    for item in store.get_catalog():
        assert not contains_paid_figures(json.dumps(item)), item


def test_leak_filter_uses_scanned_content(scanned):
    assert contains_paid_figures("Rumour says Aurelion holds 31,4 percent of Europe.")
    assert contains_paid_figures("The Nordic utility pays 48 500 EUR.")   # internal notes count too
    assert not contains_paid_figures("We cover batteries in Europe for 2025.")


def test_get_content_delivers_sections_and_refuses_excluded(scanned):
    content = store.get_content(["rpt_battery_2025#s2"])
    assert "31.4" in content["rpt_battery_2025#s2"]
    with pytest.raises(store.ContentNotAvailable):
        store.get_content(["rpt_battery_2025#s2", "page_internal_notes#s1"])
    with pytest.raises(store.ContentNotAvailable):
        store.get_content(["rpt_unknown#s1"])


def test_llm_metadata_with_a_figure_is_redacted():
    index = build_index(["Aurelion holds 31.4% of the market."])
    planned = dict(content_id="r#s1", report_id="r", title="Report", section="Market share",
                   text="", kind="report_section", url="", internal=False)
    meta = SectionMetadata(topic="batteries (leader at 31.4%)", region="Europe", period="2025",
                           data_types=["market_share"], sensitivity="proprietary", suggested_tier="small_table")
    item, leaked = finalize_item(planned, meta, index)
    assert leaked == ["topic"] and "31.4" not in item["topic"]


def test_llm_cannot_unflag_an_internal_page():
    planned = dict(content_id="p#s1", report_id="p", title="Internal notes", section="Internal notes",
                   text="", kind="internal_page", url="", internal=True)
    meta = SectionMetadata(topic="x", region="Europe", period="2025", data_types=["summary"],
                           sensitivity="public", suggested_tier="single_fact")
    item, _ = finalize_item(planned, meta, frozenset())
    assert item["status"] == "excluded" and item["suggested_tier"] is None


def test_get_catalog_endpoint(client):
    res = client.get("/publisher/catalog")
    assert res.status_code == 200 and len(res.json()) == len(MOCK)


def test_patch_status_with_encoded_id(client):
    res = client.patch("/publisher/catalog/rpt_lithium_2025%23s4", json={"status": "free"})
    assert res.status_code == 200 and res.json()["status"] == "free"
    # A section made free is public: its figures no longer count as paid.
    assert not contains_paid_figures("Built from 19 expert interviews.")
    res = client.patch("/publisher/catalog/rpt_lithium_2025%23s4", json={"status": "sellable"})
    assert res.json()["status"] == "sellable"
    assert contains_paid_figures("Built from 19 expert interviews.")


def test_patch_rejects_bad_requests(client):
    assert client.patch("/publisher/catalog/page_internal_notes%23s1", json={"status": "sellable"}).status_code == 409
    assert client.patch("/publisher/catalog/nope%23s1", json={"status": "free"}).status_code == 404
    assert client.patch("/publisher/catalog/rpt_lithium_2025%23s4", json={"status": "gratis"}).status_code == 422


def test_rescan_keeps_publisher_choices(client, site_url):
    client.patch("/publisher/catalog/rpt_sodium_2025%23s4", json={"status": "excluded"})
    res = client.post("/publisher/scan", json={"url": site_url, "wait": True})
    assert res.status_code == 202 and res.json()["status"] == "ready"
    assert store.get_catalog_item("rpt_sodium_2025#s4")["status"] == "excluded"
