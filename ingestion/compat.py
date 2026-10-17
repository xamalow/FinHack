"""Bridge to /shared (owned by P2).

Uses shared.events.log_event and shared.db.get_connection when P2 has
shipped them. Until then, falls back to a local SQLite file and to
printing events, so P1 can run on its own. Delete the fallbacks once
/shared is merged.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from shared.events import log_event  # noqa: F401
except ImportError:
    def log_event(session_id, actor, type, summary, payload=None):
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "session_id": session_id,
            "actor": actor,
            "type": type,
            "summary": summary,
            "payload": payload or {},
        }
        print("EVENT " + json.dumps(event, ensure_ascii=False), flush=True)
        return event

try:
    from shared.db import get_connection  # noqa: F401
except ImportError:
    DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent / ".data" / "finhack.db"))

    def get_connection():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
