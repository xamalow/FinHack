"""Manifest and free discovery (7.1 step 7, 6.5). Never returns a paid figure."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from gateway import p1_bridge
from gateway.auth import AgentIdentity, agent_identity, log_request
from gateway.tiers import current_tiers
from shared import config, db, signing
from shared.schemas import DiscoverItem, DiscoverOut, Manifest, ManifestPayment

router = APIRouter(tags=["discovery"])


def build_manifest() -> Optional[Manifest]:
    publisher = db.get_publisher()
    if not publisher.get("activated_at") or not publisher.get("wallet_address"):
        return None
    topics = sorted({c["topic"] for c in p1_bridge.get_catalog() if c["status"] != "excluded"})
    manifest = Manifest(
        publisher=publisher.get("name") or config.PUBLISHER_NAME,
        gateway=config.GATEWAY_PUBLIC_URL.rstrip("/"),
        topics=topics,
        payment=ManifestPayment(network=config.NETWORK, pay_to=publisher["wallet_address"]),
    )
    return Manifest(**signing.sign_manifest(manifest.model_dump(mode="json")))


@router.get("/.well-known/ai-data.json", response_model=Manifest)
def manifest() -> Manifest:
    m = build_manifest()
    if not m:
        raise HTTPException(status_code=404, detail="Publisher is not activated yet")
    return m


def _matches(item: dict, query: str) -> bool:
    haystack = " ".join(
        [item["title"], item["section"], item["topic"], item["region"], item["period"], *item.get("data_types", [])]
    ).lower()
    return all(word in haystack for word in query.lower().split())


@router.get("/discover", response_model=DiscoverOut)
def discover(request: Request, q: str = "", identity: AgentIdentity = Depends(agent_identity)) -> DiscoverOut:
    log_request(request, identity)
    catalog = [c for c in p1_bridge.get_catalog() if c["status"] != "excluded"]
    matches = [c for c in catalog if not q or _matches(c, q)]

    items = []
    for c in matches:
        item = DiscoverItem(**{k: c.get(k) for k in DiscoverItem.model_fields})
        # Metadata never holds figures, but check anyway before it leaves the gateway.
        if p1_bridge.contains_paid_figures(item.model_dump_json()):
            continue
        items.append(item)

    return DiscoverOut(
        publisher=db.get_publisher().get("name") or config.PUBLISHER_NAME,
        topics=sorted({c["topic"] for c in catalog}),
        regions=sorted({c["region"] for c in catalog}),
        periods=sorted({c["period"] for c in catalog}),
        tiers=current_tiers(),
        items=items,
    )
