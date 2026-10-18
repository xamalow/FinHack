// Mirrors the shared contracts in agent.md section 6. P2 owns the source of truth
// in /shared/schemas.py; keep these in sync when it changes.

export type CatalogStatus = "sellable" | "free" | "excluded";
export type TierName = "single_fact" | "small_table" | "full_section";

export interface CatalogItem {
  content_id: string;
  report_id: string;
  title: string;
  section: string;
  topic: string;
  region: string;
  period: string;
  data_types: string[];
  sensitivity: string;
  status: CatalogStatus;
  suggested_tier: TierName | null; // null for free and excluded items
}

export interface Tier {
  tier: TierName;
  route: string;
  price_usdc: number;
  scope: string;
}

export type Actor =
  | "buyer"
  | "gateway"
  | "sales_agent"
  | "facilitator"
  | "chain"
  | "publisher";

export interface AppEvent {
  event_id?: number | string;
  ts: string;
  session_id: string | null;
  actor: Actor;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
}

export type OfferStatus = "proposed" | "accepted" | "paid" | "expired" | "rejected";

export interface Offer {
  offer_id: string;
  session_id?: string;
  content_ids: string[];
  scope: string;
  tier: TierName;
  price_usdc: number;
  license: string;
  status?: OfferStatus;
  expires_in_s?: number;
}

export interface Transaction {
  tx_id: string;
  offer_id: string;
  payer: string;
  pay_to: string;
  amount_atomic: number | string;
  nonce: string;
  tx_hash: string | null;
  status: string;
  ts: number | string; // epoch seconds from the transactions table, ISO in mocks
}

export interface PublisherStats {
  requests: number;
  paid_requests: number;
  revenue_usdc: number;
  average_usdc: number;
}

export interface Manifest {
  publisher: string;
  gateway: string;
  discover: string;
  kya: string;
  topics: string[];
  payment: { protocol: string; network: string; asset: string; pay_to: string };
  license_default: string;
}

export interface Audit {
  offer: Offer;
  agent: { agent_id: string; wallet_address: string; status: string } | null;
  messages: { role: "buyer" | "sales_agent"; content: string; ts: string }[];
  transaction: Transaction | null;
  events: AppEvent[];
}
