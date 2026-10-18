// Plain-language wording for every event type in shared/events.py,
// so the jury can follow the live view without knowing the protocol.

export type Phase = "identity" | "negotiation" | "payment" | "delivery";
export type Tone = "info" | "ok" | "warn" | "bad";

export interface EventLabel {
  icon: string;
  title: string;
  explain: string;
  phase: Phase;
  tone: Tone;
}

export const PHASES: { key: Phase; title: string; explain: string }[] = [
  { key: "identity", title: "Identity", explain: "The agent proves who it is" },
  { key: "negotiation", title: "Negotiation", explain: "It asks for data and gets a price" },
  { key: "payment", title: "Payment", explain: "It pays in USDC on the blockchain" },
  { key: "delivery", title: "Delivery", explain: "The data is sent, the publisher is paid" },
];

const L = (icon: string, title: string, explain: string, phase: Phase, tone: Tone = "info"): EventLabel => ({ icon, title, explain, phase, tone });

const LABELS: Record<string, EventLabel> = {
  // Publisher onboarding
  scan_started: L("🔎", "Scanning the website", "Reading the sitemap and the pages.", "identity"),
  scan_extracting: L("📄", "Reading pages and PDFs", "Extracting the text of each report.", "identity"),
  scan_indexing: L("🗂️", "Building the catalog", "Describing each section without revealing any figure.", "identity"),
  scan_failed: L("⚠️", "Scan failed", "The website could not be read. Check the URL and try again.", "identity", "bad"),
  scan_ready: L("✅", "Catalog ready", "The publisher can now review what is for sale.", "identity", "ok"),
  catalog_updated: L("✏️", "Catalog updated", "The publisher changed what is for sale.", "identity"),
  rules_parsed: L("🧾", "Prices drafted", "Your rules were turned into price tiers to confirm.", "identity"),
  rules_confirmed: L("💲", "Prices confirmed", "These prices are now enforced automatically.", "identity", "ok"),
  wallet_connected: L("👛", "Wallet connected", "Sales will be paid to this wallet.", "identity", "ok"),
  activated: L("🚀", "Site activated", "AI agents can now buy data from this site.", "identity", "ok"),

  // Identity
  mission_started: L("🤖", "Agent starts its mission", "An AI agent has a task and a budget set by its owner.", "identity"),
  manifest_read: L("🧭", "Agent finds the data offer", "It reads the publisher's public file that says data is for sale.", "identity"),
  request_received: L("📨", "Agent knocks on the door", "We detect an AI agent, not a human visitor.", "identity"),
  human_redirected: L("🧑", "Human visitor", "Humans are sent back to the normal website.", "identity"),
  discover_called: L("📚", "Agent browses the catalog", "It sees topics and periods, never a figure.", "identity"),
  kya_challenge_issued: L("🔐", "Identity check sent", "We ask the agent to sign a random code with its wallet.", "identity"),
  kya_signed: L("✍️", "Agent signs to prove its identity", "Only the real wallet owner can produce this signature.", "identity"),
  kya_verified: L("🪪", "Identity verified", "Signature is valid and the wallet is not blocked.", "identity", "ok"),
  kya_rejected: L("⛔", "Identity refused", "Bad signature or blocked wallet. Access denied.", "identity", "bad"),

  // Negotiation
  buyer_message: L("💬", "Agent asks for data", "It explains what information it needs.", "negotiation"),
  sales_message: L("🧑‍💼", "Our sales agent answers", "It describes what is available, without giving numbers.", "negotiation"),
  offer_proposed: L("🏷️", "Price offer made", "The price depends on how much data is asked for.", "negotiation"),
  offer_validated: L("🛡️", "Offer checked by our rules", "Right price, nothing excluded, no figure leaked.", "negotiation", "ok"),
  offer_rejected: L("🛡️", "Offer blocked by our rules", "It broke a publisher rule, so the agent never sees it.", "negotiation", "bad"),
  no_match: L("🤷", "We don't have this data", "Nothing to sell, no payment.", "negotiation", "bad"),
  injection_ignored: L("🛡️", "Manipulation attempt blocked", "The agent tried to trick our sales agent. Nothing was revealed.", "negotiation", "bad"),
  offer_evaluated: L("🧮", "Agent checks its budget", "Price is within its budget and spending limits.", "negotiation", "ok"),
  offer_refused_budget: L("🙅", "Agent refuses: too expensive", "The price is above the budget its owner set.", "negotiation", "bad"),
  approval_requested: L("✋", "Agent asks its owner for approval", "This purchase is above the amount it may spend alone.", "negotiation", "warn"),
  approval_granted: L("👍", "Owner approved", "The agent may go ahead with this purchase.", "negotiation", "ok"),
  offer_accepted: L("🤝", "Offer accepted", "The agent takes the offer. The price is now fixed.", "negotiation", "ok"),

  // Payment
  payment_required_sent: L("🧾", "Invoice sent", "We tell the agent the exact amount and where to pay.", "payment", "warn"),
  payment_signed: L("✍️", "Agent signs the payment", "It authorizes the USDC transfer from its wallet.", "payment"),
  verify_response: L("🔍", "Payment checked", "An independent service checks the signature and the funds.", "payment", "ok"),
  payment_verified: L("✅", "Payment is valid", "Everything matches the offer.", "payment", "ok"),
  tx_submitted: L("⛓️", "Sent to the blockchain", "The transfer is published on the blockchain.", "payment"),
  tx_confirmed: L("⛓️", "Confirmed on the blockchain", "The money has moved. Anyone can verify it.", "payment", "ok"),
  settle_response: L("🏦", "Payment settled", "The transfer is final.", "payment", "ok"),
  payment_settled: L("💰", "Publisher paid", "Money is received before any data is sent.", "payment", "ok"),
  payment_rejected: L("⛔", "Payment refused", "Something did not match, nothing is delivered.", "payment", "bad"),
  replay_rejected: L("🔁", "Reused payment blocked", "The same payment cannot be used twice.", "payment", "bad"),

  // Delivery
  balance_watch_failed: L("⚠️", "Balances not tracked", "The blockchain could not be read right now. Payments still work.", "delivery", "warn"),
  balance_changed: L("📊", "Balances updated", "Both wallets read directly from the blockchain.", "delivery", "ok"),
  content_delivered: L("📦", "Data sent to the agent", "Only the part that was paid for.", "delivery", "ok"),
  receipt_redownload: L("🧾", "Data downloaded again", "Using the receipt, without paying twice.", "delivery"),
  data_received: L("📥", "Agent receives the data", "Stored with its payment receipt.", "delivery", "ok"),
  mission_done: L("🏁", "Mission complete", "The agent reports back to its owner.", "delivery", "ok"),
};

export function labelFor(type: string): EventLabel {
  return LABELS[type] ?? L("•", type.replace(/_/g, " "), "", "delivery");
}
