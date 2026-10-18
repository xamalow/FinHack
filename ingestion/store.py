"""Catalog and content tables (owned by P1, section 6.1 of agent.md).

Public API used by the other roles:
    get_catalog(status=None) -> list[dict]       metadata only, never raw text
    get_content(content_ids) -> dict[id, text]   refuses excluded or unknown ids
"""
import json
from contextlib import closing
from pathlib import Path

from ingestion.compat import get_connection

STATUSES = ("sellable", "free", "excluded")
MOCK_CATALOG = Path(__file__).parent / "mock_catalog.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (
    content_id     TEXT PRIMARY KEY,
    report_id      TEXT NOT NULL,
    title          TEXT NOT NULL,
    section        TEXT NOT NULL,
    topic          TEXT,
    region         TEXT,
    period         TEXT,
    data_types     TEXT NOT NULL DEFAULT '[]',
    sensitivity    TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('sellable', 'free', 'excluded')),
    suggested_tier TEXT
);
CREATE TABLE IF NOT EXISTS content (
    content_id TEXT PRIMARY KEY,
    raw_text   TEXT NOT NULL
);
"""

CATALOG_FIELDS = (
    "content_id", "report_id", "title", "section", "topic", "region", "period",
    "data_types", "sensitivity", "status", "suggested_tier",
)


class ContentNotAvailable(Exception):
    """Raised when someone asks for content that is excluded or unknown."""


def init_db():
    with closing(get_connection()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _row_to_item(row):
    item = dict(row)
    item["data_types"] = json.loads(item["data_types"] or "[]")
    return item


def replace_catalog(items, contents):
    """Store a fresh scan. A status already chosen by the publisher for a
    content_id that still exists is kept, so a rescan never re-exposes an
    item the publisher excluded."""
    init_db()
    with closing(get_connection()) as conn:
        previous = {r["content_id"]: r["status"] for r in conn.execute("SELECT content_id, status FROM catalog")}
        conn.execute("DELETE FROM catalog")
        conn.execute("DELETE FROM content")
        for item in items:
            row = dict(item)
            if row["content_id"] in previous and row["status"] != "excluded":
                row["status"] = previous[row["content_id"]]
            row["data_types"] = json.dumps(row.get("data_types") or [])
            conn.execute(
                f"INSERT INTO catalog ({', '.join(CATALOG_FIELDS)}) VALUES ({', '.join('?' * len(CATALOG_FIELDS))})",
                [row.get(f) for f in CATALOG_FIELDS],
            )
        conn.executemany(
            "INSERT INTO content (content_id, raw_text) VALUES (?, ?)",
            [(cid, text) for cid, text in contents.items()],
        )
        conn.commit()
    _invalidate_leak_index()


def load_mock_catalog():
    """Load the hand-written catalog (no raw content) so other roles can
    work before the first real scan."""
    items = json.loads(MOCK_CATALOG.read_text(encoding="utf-8"))
    replace_catalog(items, {})
    return items


def get_catalog(status=None):
    init_db()
    query, args = "SELECT * FROM catalog", ()
    if status:
        query, args = query + " WHERE status = ?", (status,)
    with closing(get_connection()) as conn:
        rows = conn.execute(query + " ORDER BY content_id", args).fetchall()
    return [_row_to_item(r) for r in rows]


def get_catalog_item(content_id):
    init_db()
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM catalog WHERE content_id = ?", (content_id,)).fetchone()
    return _row_to_item(row) if row else None


def set_status(content_id, status):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    init_db()
    with closing(get_connection()) as conn:
        cur = conn.execute("UPDATE catalog SET status = ? WHERE content_id = ?", (status, content_id))
        conn.commit()
    if cur.rowcount == 0:
        return None
    _invalidate_leak_index()
    return get_catalog_item(content_id)


def get_content(content_ids):
    """Raw text of purchased content, for delivery after settlement only.
    Refuses the whole request if any id is unknown or excluded, so an
    excluded item can never be delivered even if an offer slipped through."""
    ids = list(dict.fromkeys(content_ids))
    if not ids:
        return {}
    init_db()
    marks = ", ".join("?" * len(ids))
    with closing(get_connection()) as conn:
        rows = conn.execute(
            f"SELECT c.content_id, c.status, t.raw_text FROM catalog c "
            f"LEFT JOIN content t ON t.content_id = c.content_id WHERE c.content_id IN ({marks})",
            ids,
        ).fetchall()
    found = {r["content_id"]: r for r in rows}
    missing = [i for i in ids if i not in found or found[i]["raw_text"] is None]
    excluded = [i for i in ids if i in found and found[i]["status"] == "excluded"]
    if excluded:
        raise ContentNotAvailable(f"excluded content cannot be delivered: {excluded}")
    if missing:
        raise ContentNotAvailable(f"unknown content: {missing}")
    return {i: found[i]["raw_text"] for i in ids}


def get_texts_by_status():
    """(status, raw_text) pairs for every stored item, used by the leak filter."""
    init_db()
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT c.status, t.raw_text FROM catalog c JOIN content t ON t.content_id = c.content_id"
        ).fetchall()
    return [(r["status"], r["raw_text"]) for r in rows]


def _invalidate_leak_index():
    from ingestion import leak_filter
    leak_filter.invalidate()
