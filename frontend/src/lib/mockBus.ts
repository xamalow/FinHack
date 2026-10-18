// In-browser stand-in for GET /events/stream while the gateway does not exist.
import type { AppEvent } from "./types";
import type { ScriptStep } from "./mocks";

type Listener = (e: AppEvent) => void;

const listeners = new Set<Listener>();
const history: AppEvent[] = [];
let counter = 0;

export function subscribeMock(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function mockHistory(sessionId?: string): AppEvent[] {
  return sessionId ? history.filter((e) => e.session_id === sessionId) : [...history];
}

export function emitMock(e: Omit<AppEvent, "event_id" | "ts">) {
  const event: AppEvent = { ...e, event_id: `mock_${++counter}`, ts: new Date().toISOString() };
  history.push(event);
  listeners.forEach((fn) => fn(event));
}

export async function playScript(steps: ScriptStep[], sessionId: string | null) {
  for (const s of steps) {
    await new Promise((r) => setTimeout(r, s.delay));
    emitMock({ session_id: sessionId, actor: s.actor, type: s.type, summary: s.summary, payload: s.payload ?? {} });
  }
}
