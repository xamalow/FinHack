"""Publisher scan and catalog endpoints (P1).

POST  /publisher/scan                   crawl a URL and build the catalog
GET   /publisher/catalog                full catalog with statuses
PATCH /publisher/catalog/{content_id}   set sellable, free or excluded
GET   /publisher/catalog/{content_id}/preview   raw text, owner only

content_ids contain "#", so clients must URL-encode them in the path
(encodeURIComponent("rpt_battery_2025#s2") -> rpt_battery_2025%23s2).
"""
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from ingestion import catalog, store
from ingestion.crawl import UnsafeURL, check_public_url
from ingestion.compat import log_event
from shared.owner import publisher_only

router = APIRouter(prefix="/publisher", tags=["publisher"])


class ScanRequest(BaseModel):
    url: HttpUrl
    wait: bool = False   # true runs the scan inline and returns the summary


class StatusUpdate(BaseModel):
    status: Literal["sellable", "free", "excluded"]


def _run_scan(url):
    try:
        catalog.run_scan(url)
    except catalog.ScanInProgress:
        pass
    except Exception:
        pass  # already reported by the scan_failed event


@router.post("/scan", status_code=202, dependencies=[Depends(publisher_only)])
def scan(req: ScanRequest, background_tasks: BackgroundTasks):
    url = str(req.url)
    try:
        check_public_url(url)
    except UnsafeURL as err:
        raise HTTPException(400, str(err))
    if req.wait:
        try:
            return {"status": "ready", "summary": catalog.run_scan(url)}
        except catalog.ScanInProgress as err:
            raise HTTPException(409, str(err))
        except Exception as err:
            raise HTTPException(502, f"scan failed: {err}")
    if catalog.is_scanning():
        raise HTTPException(409, "a scan is already running")
    background_tasks.add_task(_run_scan, url)
    return {"status": "started", "url": url}


@router.get("/catalog")
def get_catalog():
    # source_url is added here only: it is for the publisher's review screen, never in the Sales agent's view
    sources = store.get_sources()
    return [{**item, "source_url": sources.get(item["content_id"])} for item in store.get_catalog()]


@router.get("/catalog/{content_id}/preview", dependencies=[Depends(publisher_only)])
def preview_catalog_item(content_id: str):
    """The publisher reads one of its own sections before deciding what to sell. Owner only:
    the text holds the figures agents pay for."""
    item = store.get_catalog_item(content_id)
    if item is None:
        raise HTTPException(404, f"unknown content_id {content_id}")
    text = store.get_preview_text(content_id)
    if text is None:
        raise HTTPException(404, f"no text stored for {content_id}")
    return {"content_id": content_id, "title": item["title"], "section": item["section"], "text": text}


@router.patch("/catalog/{content_id}", dependencies=[Depends(publisher_only)])
def update_catalog_item(content_id: str, update: StatusUpdate):
    item = store.get_catalog_item(content_id)
    if item is None:
        raise HTTPException(404, f"unknown content_id {content_id}")
    if item["sensitivity"] == "internal" and update.status != "excluded":
        raise HTTPException(409, "content flagged as internal cannot be sold or published")
    previous = item["status"]
    item = store.set_status(content_id, update.status)
    log_event(None, "publisher", "catalog_updated",
              f"{item['title']}, {item['section']}: {previous} -> {item['status']}",
              {"content_id": content_id, "previous_status": previous, "status": item["status"]})
    return item
