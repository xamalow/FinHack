"""Event history and live stream for the live view (7.4)."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sse_starlette.sse import EventSourceResponse

from shared import db
from shared.owner import publisher_only

# The live view shows buyer conversations and wallets: publisher only (loopback or owner token).
router = APIRouter(tags=["events"], dependencies=[Depends(publisher_only)])

POLL_SECONDS = 0.3


@router.get("/events")
def events(session_id: Optional[str] = None, after_id: int = 0, limit: int = 500) -> list[dict]:
    return db.list_events(session_id=session_id, after_id=after_id, limit=min(limit, 2000))


@router.get("/events/stream")
async def events_stream(
    request: Request,
    session_id: Optional[str] = None,
    after_id: Optional[int] = None,
    last_event_id: Optional[str] = Header(default=None),
) -> EventSourceResponse:
    """SSE stream. Starts after `after_id` (or Last-Event-ID on reconnect), else only new events."""
    if last_event_id and last_event_id.isdigit():
        cursor = int(last_event_id)
    elif after_id is not None:
        cursor = after_id
    else:
        latest = db.fetch_one("SELECT MAX(event_id) AS m FROM events")
        cursor = (latest or {}).get("m") or 0

    async def generator():
        nonlocal cursor
        while not await request.is_disconnected():
            rows = await asyncio.to_thread(db.list_events, session_id, cursor, 200)
            for row in rows:
                cursor = row["event_id"]
                yield {"id": str(row["event_id"]), "data": json.dumps(row)}
            if not rows:
                await asyncio.sleep(POLL_SECONDS)

    return EventSourceResponse(generator(), ping=15)
