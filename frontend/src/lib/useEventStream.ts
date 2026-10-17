"use client";

import { useEffect, useState } from "react";
import { GATEWAY_URL, USE_MOCKS } from "./config";
import { mockHistory, subscribeMock } from "./mockBus";
import type { AppEvent } from "./types";

// Subscribes to GET /events/stream (SSE) or to the in-browser mock bus.
export function useEventStream(onEvent?: (e: AppEvent) => void) {
  const [events, setEvents] = useState<AppEvent[]>(() => (USE_MOCKS ? mockHistory() : []));
  const [connected, setConnected] = useState(USE_MOCKS);

  useEffect(() => {
    const push = (e: AppEvent) => {
      setEvents((prev) => (e.event_id && prev.some((p) => p.event_id === e.event_id) ? prev : [...prev, e]));
      onEvent?.(e);
    };

    if (USE_MOCKS) return subscribeMock(push);

    const es = new EventSource(`${GATEWAY_URL}/events/stream`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false); // EventSource reconnects by itself
    es.onmessage = (msg) => {
      try {
        const e = JSON.parse(msg.data) as AppEvent;
        if (typeof e.payload === "string") e.payload = JSON.parse(e.payload);
        push(e);
      } catch {
        // ignore malformed lines
      }
    };
    return () => es.close();
    // onEvent is intentionally read once per mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { events, connected, clear: () => setEvents([]) };
}
