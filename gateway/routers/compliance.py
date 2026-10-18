"""Compliance routes: audit chain, sanctions screening, license receipts, watermark tracing, data retention.

Public (anyone can check the publisher): /compliance/audit-head, /compliance/signer, /compliance/verify-receipt.
Owner only: everything that reads or erases data.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from payments import store, watermark
from shared import audit_chain, config, db, retention, sanctions, signing
from shared.owner import publisher_only

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _with_conn(fn):
    with db.connect() as conn:
        return fn(conn)


@router.get("/audit-head")
def audit_head() -> dict:
    """Latest chain hash. Record it anywhere (or on-chain): any later edit of earlier events breaks it."""
    return _with_conn(audit_chain.head)


@router.get("/audit-chain", dependencies=[Depends(publisher_only)])
def audit_chain_verify() -> dict:
    return _with_conn(audit_chain.verify)


@router.get("/signer")
def signer() -> dict:
    return {"signer": signing.publisher_account().address, "scheme": "EIP-191 personal_sign over canonical JSON",
            "manifest_domain": signing.MANIFEST_DOMAIN.strip(), "receipt_domain": signing.RECEIPT_DOMAIN.strip()}


@router.post("/verify-receipt")
def verify_receipt(receipt: dict = Body(..., embed=True)) -> dict:
    """Checks a license receipt: publisher signature, and that the sale it describes is in our ledger."""
    ok, recovered, reason = signing.verify_receipt(receipt, signing.publisher_account().address)
    tx = store.get_by_hash(receipt.get("tx_hash") or "")
    matches = bool(tx and tx["status"] == "settled" and tx["payer"] == str(receipt.get("payer", "")).lower()
                   and tx["amount_atomic"] == receipt.get("amount_atomic") and tx["offer_id"] == receipt.get("offer_id"))
    return {"signature_valid": ok, "signer": recovered, "detail": reason, "sale_on_record": matches,
            "explorer": f"{config.EXPLORER_URL}/tx/{receipt.get('tx_hash')}" if receipt.get("tx_hash") else None}


@router.get("/screen/{address}", dependencies=[Depends(publisher_only)])
def screen(address: str) -> dict:
    return sanctions.screen(address).as_payload()


@router.post("/trace", dependencies=[Depends(publisher_only)])
def trace(text: str = Body(..., embed=True)) -> dict:
    """Which sale a leaked text comes from, from its watermark."""
    ids = sorted(watermark.extract(text))
    sales = watermark.trace(text, store.settled_sales())
    for s in sales:
        s["explorer"] = f"{config.EXPLORER_URL}/tx/{s['tx_hash']}"
    return {"watermark_ids_found": ids, "sales": sales}


@router.post("/purge", dependencies=[Depends(publisher_only)])
def purge(days: Optional[int] = Body(None, embed=True)) -> dict:
    if days is not None and days < 0:
        raise HTTPException(422, "days must be >= 0")
    return retention.purge(days)


@router.post("/erase", dependencies=[Depends(publisher_only)])
def erase(wallet: str = Body(..., embed=True)) -> dict:
    if not sanctions.is_address(wallet):
        raise HTTPException(422, "Not a valid EVM address")
    return retention.erase_subject(wallet)


@router.get("/report", dependencies=[Depends(publisher_only)])
def report() -> dict:
    """One page for an auditor: what is enforced and its current state."""
    chain = _with_conn(audit_chain.verify)
    counts = {r["type"]: r["n"] for r in db.fetch_all(
        "SELECT type, COUNT(*) AS n FROM events WHERE type IN ('sanctions_screened', 'sanctions_blocked', "
        "'license_receipt_issued', 'personal_data_purged', 'kya_verified', 'kya_rejected', 'replay_rejected', "
        "'structuring_suspected', 'velocity_limit_hit', 'manifest_signature_failed', 'injection_ignored') GROUP BY type")}
    return {
        "network": config.NETWORK,
        "audit_chain": {k: chain[k] for k in ("ok", "checked", "head", "redacted")} | {"problems": len(chain["problems"])},
        "sanctions": {"source": "Chainalysis sanctions oracle (OFAC SDN) + local blocklist",
                      "oracle": sanctions.oracle_address(), "fail_mode": sanctions.fail_mode(),
                      "checked_at": ["kya", "payment", "payout_wallet", "buyer: pay_to"]},
        "signer": signing.publisher_account().address,
        "retention": {"personal_data_days": retention.retention_days(), "personal_event_types": retention.PERSONAL_EVENT_TYPES,
                      "kept": "offers, transactions, license receipts (AML / accounting record keeping)"},
        "settled_sales": len(store.settled_sales()),
        "event_counts": counts,
    }
