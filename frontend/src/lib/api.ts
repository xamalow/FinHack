// Client for the gateway endpoints in agent.md section 6.5.
// Request and response bodies are not frozen yet; every assumption about a body
// shape lives in this file so plugging the real gateway only touches here.
import { BUYER_WALLET, GATEWAY_URL, USE_MOCKS } from "./config";
import { emitMock, mockHistory, playScript, subscribeMock } from "./mockBus";
import {
  MOCK_PUBLISHER_WALLET,
  mockAudit,
  mockCatalog,
  mockManifest,
  mockStats,
  mockTiers,
  mockTransactions,
  purchaseScript,
  scanScript,
  securityScript,
  type ScriptStep,
} from "./mocks";
import type {
  AppEvent,
  Audit,
  CatalogItem,
  CatalogStatus,
  Manifest,
  PublisherStats,
  Tier,
  Transaction,
} from "./types";

async function http<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${GATEWAY_URL}${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

// ---- Mock state ------------------------------------------------------------

const mock = {
  catalog: mockCatalog.map((c) => ({ ...c })),
  publisherWallet: MOCK_PUBLISHER_WALLET,
  balances: { [BUYER_WALLET.toLowerCase()]: 5.0, [MOCK_PUBLISHER_WALLET.toLowerCase()]: 0 } as Record<string, number>,
  pending: new Map<string, ScriptStep[]>(), // offer_id -> steps after approval
  sessions: 0,
};

// Keep mock balances in sync with balance_changed events so /balance agrees with the stream.
if (USE_MOCKS) {
  subscribeMock((e) => {
    if (e.type !== "balance_changed") return;
    const p = e.payload as { buyer: string; buyer_usdc: number; publisher: string; publisher_usdc: number };
    mock.balances[p.buyer.toLowerCase()] = p.buyer_usdc;
    mock.balances[p.publisher.toLowerCase()] = p.publisher_usdc;
  });
}

// ---- Publisher (P1, P2) ------------------------------------------------------

export async function scan(url: string): Promise<void> {
  if (USE_MOCKS) {
    await playScript(scanScript(url), null);
    return;
  }
  await http("POST", "/publisher/scan", { url });
}

export async function getCatalog(): Promise<CatalogItem[]> {
  if (USE_MOCKS) return mock.catalog.map((c) => ({ ...c }));
  return http("GET", "/publisher/catalog");
}

export async function setCatalogStatus(contentId: string, status: CatalogStatus): Promise<void> {
  if (USE_MOCKS) {
    const it = mock.catalog.find((c) => c.content_id === contentId);
    if (it) it.status = status;
    emitMock({ session_id: null, actor: "publisher", type: "catalog_updated", summary: `${contentId} set to ${status}`, payload: { content_id: contentId, status } });
    return;
  }
  await http("PATCH", `/publisher/catalog/${encodeURIComponent(contentId)}`, { status });
}

export async function putRules(rawText: string): Promise<Tier[]> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 1200));
    return mockTiers;
  }
  const res = await http<{ tiers: Tier[] } | Tier[]>("PUT", "/publisher/rules", { raw_text: rawText });
  return Array.isArray(res) ? res : res.tiers;
}

export async function confirmRules(): Promise<void> {
  if (USE_MOCKS) {
    emitMock({ session_id: null, actor: "publisher", type: "rules_confirmed", summary: "Pricing tiers confirmed", payload: { tiers: mockTiers } });
    return;
  }
  await http("POST", "/publisher/rules/confirm");
}

export async function setWallet(address: string): Promise<void> {
  if (USE_MOCKS) {
    mock.publisherWallet = address;
    mock.balances[address.toLowerCase()] ??= 0;
    emitMock({ session_id: null, actor: "publisher", type: "wallet_connected", summary: `Wallet ${address.slice(0, 6)}…${address.slice(-4)} connected`, payload: { wallet_address: address } });
    return;
  }
  await http("POST", "/publisher/wallet", { wallet_address: address });
}

export async function activate(): Promise<{ gateway: string; manifest: Manifest }> {
  if (USE_MOCKS) {
    const manifest = mockManifest(mock.publisherWallet);
    emitMock({ session_id: null, actor: "publisher", type: "activated", summary: "Site activated, paid routes live", payload: manifest as unknown as Record<string, unknown> });
    return { gateway: manifest.gateway, manifest };
  }
  const res = await http<{ manifest?: Manifest } & Partial<Manifest>>("POST", "/publisher/activate");
  const manifest = (res.manifest ?? res) as Manifest;
  return { gateway: GATEWAY_URL, manifest };
}

export async function getManifest(): Promise<Manifest> {
  if (USE_MOCKS) return mockManifest(mock.publisherWallet);
  return http("GET", "/.well-known/ai-data.json");
}

// ---- Buyer and payments (P3) -------------------------------------------------

export type DemoScenario = "single_fact" | "full_section" | "security";

// The mock picks a scenario from the mission text; the real buyer agent decides by itself.
export function scenarioFor(mission: string): DemoScenario {
  const m = mission.toLowerCase();
  if (/inject|ignore your|security|replay/.test(m)) return "security";
  if (/full|section|methodology|ranking/.test(m)) return "full_section";
  return "single_fact";
}

export async function runBuyer(mission: string, budgetUsdc: number): Promise<{ session_id: string }> {
  if (!USE_MOCKS) return http("POST", "/buyer/run", { mission, budget_usdc: budgetUsdc });

  const sessionId = `ses_${(++mock.sessions).toString(16).padStart(3, "0")}${Math.random().toString(16).slice(2, 5)}`;
  const scenario = scenarioFor(mission);
  const buyer = BUYER_WALLET.toLowerCase();
  const pub = mock.publisherWallet.toLowerCase();

  if (scenario === "security") {
    void playScript(securityScript(mock.publisherWallet), sessionId);
    return { session_id: sessionId };
  }
  const offerId = `off_${Math.random().toString(16).slice(2, 6)}`;
  const { beforeApproval, afterApproval } = purchaseScript({
    sessionId,
    offerId,
    tier: scenario,
    budget: budgetUsdc,
    buyerBalance: mock.balances[buyer] ?? 0,
    publisherBalance: mock.balances[pub] ?? 0,
    payTo: mock.publisherWallet,
  });
  if (afterApproval.length) mock.pending.set(offerId, afterApproval);
  void playScript(beforeApproval, sessionId);
  return { session_id: sessionId };
}

export async function approve(offerId: string, sessionId: string | null): Promise<void> {
  if (!USE_MOCKS) {
    await http("POST", "/buyer/approve", { offer_id: offerId });
    return;
  }
  const steps = mock.pending.get(offerId);
  mock.pending.delete(offerId);
  if (steps) void playScript(steps, sessionId);
}

export async function getBalance(address: string): Promise<number> {
  if (USE_MOCKS) return mock.balances[address.toLowerCase()] ?? 0;
  const res = await http<{ balance_usdc?: number; balance?: number | string }>("GET", `/balance/${address}`);
  return Number(res.balance_usdc ?? res.balance ?? 0);
}

export async function getTransactions(): Promise<Transaction[]> {
  if (USE_MOCKS) return mockTransactions;
  return http("GET", "/transactions");
}

export async function getStats(): Promise<PublisherStats> {
  if (USE_MOCKS) return mockStats;
  return http("GET", "/publisher/stats");
}

// ---- Audit and events (P2) ---------------------------------------------------

export async function getAudit(offerId: string): Promise<Audit> {
  if (USE_MOCKS) return mockAudit(offerId);
  return http("GET", `/audit/${encodeURIComponent(offerId)}`);
}

export async function getEvents(sessionId?: string): Promise<AppEvent[]> {
  if (USE_MOCKS) return mockHistory(sessionId);
  return http("GET", `/events${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`);
}
