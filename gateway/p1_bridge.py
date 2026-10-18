"""Bridge to P1's functions: get_catalog(), get_content(), contains_paid_figures().

P2 consumes them but does not own them. Until P1's `ingestion` package exports
them, this module falls back to the `catalog` / `content` tables, then to
`mock_catalog.json`, so the gateway runs end to end with mock data.

P1 interface (agent.md section 8, P1 "Exposes"):

    from ingestion.store import get_catalog, get_content
    from ingestion.leak_filter import contains_paid_figures
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared import db

log = logging.getLogger("p1_bridge")

try:  # pragma: no cover - depends on P1's branch being merged
    from ingestion.leak_filter import contains_paid_figures as _p1_contains_paid_figures
    from ingestion.store import get_catalog as _p1_get_catalog
    from ingestion.store import get_content as _p1_get_content

    P1_AVAILABLE = True
except ModuleNotFoundError as e:
    if not e.name or not e.name.startswith("ingestion"):
        raise  # P1 is present but one of its dependencies is missing
    P1_AVAILABLE = False

MOCK_PATH = Path(__file__).with_name("mock_catalog.json")


@lru_cache(maxsize=1)
def _mock() -> dict[str, Any]:
    return json.loads(MOCK_PATH.read_text(encoding="utf-8"))


def using_mock() -> bool:
    return not P1_AVAILABLE and not db.list_catalog()


def get_catalog() -> list[dict[str, Any]]:
    if P1_AVAILABLE:
        return [dict(item) if not isinstance(item, dict) else item for item in _p1_get_catalog()]
    rows = db.list_catalog()
    return rows if rows else [dict(i) for i in _mock()["catalog"]]


def get_content(content_ids: list[str]) -> dict[str, str]:
    """content_id -> raw text. P2 never sends this to the Sales agent."""
    if P1_AVAILABLE:
        result = _p1_get_content(content_ids)
        if isinstance(result, dict):
            return result
        return {r["content_id"]: r["raw_text"] for r in result}
    rows = db.get_content_rows(content_ids)
    if rows:
        return {r["content_id"]: r["raw_text"] for r in rows}
    mock = _mock()["content"]
    return {cid: mock[cid] for cid in content_ids if cid in mock}


# ---------------------------------------------------------------------------
# Leak filter fallback (P1 owns the real one)
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:[.,]\d+|\s\d{3}(?!\d))*")


def _number_forms(token: str) -> set[str]:
    """Canonical forms of a number token, covering 31,4 / 31.4 / 7,412 / 7 412."""
    forms = set()
    compact = token.replace(" ", "")
    # Decimal comma reading: 31,4 -> 31.4
    forms.add(compact.replace(",", "."))
    # Thousands separator reading: 7,412 -> 7412
    forms.add(compact.replace(",", ""))
    out = set()
    for f in forms:
        try:
            value = float(f)
        except ValueError:
            continue
        out.add(f"{value:g}")
    return out


def _is_trivial(token: str) -> bool:
    """Years and small counts are not proprietary figures."""
    if any(sep in token for sep in ".,"):
        return False
    value = int(token.replace(" ", ""))
    return value <= 12 or 1990 <= value <= 2100


@lru_cache(maxsize=1)
def _paid_forms_cached(cache_key: str) -> frozenset[str]:
    catalog = get_catalog()
    paid_ids = [c["content_id"] for c in catalog if c.get("status") != "free"]
    forms: set[str] = set()
    for text in get_content(paid_ids).values():
        for token in _NUMBER.findall(text):
            if not _is_trivial(token):
                forms |= _number_forms(token)
    return frozenset(forms)


def contains_paid_figures(text: str) -> bool:
    if P1_AVAILABLE:
        return bool(_p1_contains_paid_figures(text))
    paid = _paid_forms_cached(str(len(db.list_catalog())))
    for token in _NUMBER.findall(text or ""):
        if _is_trivial(token):
            continue
        if _number_forms(token) & paid:
            return True
    return False
