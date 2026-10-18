"""Per-buyer watermark on delivered content, to trace a resold or leaked copy back to its sale.

Two marks on every delivered text:
- visible: a license line naming the payer wallet, the offer and the receipt id;
- invisible: the same receipt id written in zero-width characters after the first sentence and at the end,
  so it survives a copy-paste that drops the license line.

The id is an HMAC of (offer_id, payer) with a server secret, so nobody can forge another buyer's mark
to frame them. trace() finds the sale from a leaked text (POST /compliance/trace, owner only).
The invisible mark is removed by anyone who normalizes the text; it is a deterrent and evidence, not DRM.
"""
import hashlib
import hmac
import os
import re

ZERO, ONE, EDGE = "​", "‌", "⁠"
_CODE = re.compile(f"{EDGE}([{ZERO}{ONE}]{{48}}){EDGE}")
_VISIBLE = re.compile(r"receipt id ([0-9a-f]{12})")


def _secret() -> bytes:
    return (os.getenv("WATERMARK_SECRET") or os.getenv("JWT_SECRET") or "dev-watermark").encode()


def watermark_id(offer_id: str, payer: str) -> str:
    return hmac.new(_secret(), f"{offer_id}|{payer.lower()}".encode(), hashlib.sha256).hexdigest()[:12]


def _encode(wid: str) -> str:
    bits = bin(int(wid, 16))[2:].rjust(48, "0")
    return EDGE + "".join(ONE if b == "1" else ZERO for b in bits) + EDGE


def _decode(code: str) -> str:
    return format(int("".join("1" if c == ONE else "0" for c in code), 2), "012x")


def apply(content: dict, offer_id: str, payer: str, license: str) -> tuple[dict, str]:
    wid = watermark_id(offer_id, payer)
    code = _encode(wid)
    notice = f"\n\n[Licensed to {payer} under {license}, offer {offer_id}, receipt id {wid}. Do not redistribute.]"
    out = {}
    for cid, text in content.items():
        if not isinstance(text, str):
            out[cid] = text
            continue
        cut = text.find(". ")
        marked = text[: cut + 1] + code + text[cut + 1:] if cut >= 0 else text
        out[cid] = marked + code + notice
    return out, wid


def extract(text: str) -> set[str]:
    return {_decode(m) for m in _CODE.findall(text or "")} | set(_VISIBLE.findall(text or ""))


def trace(text: str, sales: list[dict]) -> list[dict]:
    """sales: rows with offer_id, payer, tx_hash. Returns the sales whose mark is in text."""
    found = extract(text)
    return [s for s in sales if watermark_id(s["offer_id"], s["payer"]) in found]
