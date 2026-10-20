<p><img src="docs/img/doubloon-logo.png" alt="Doubloon" width="240"></p>

# Doubloon

**We monetize the web for agentic traffic.**
*Any website. Any AI agent. Any piece of information. One payment.*

2026 Shenzhen International FinTech Competition, International Track, Topic F (Agent Wallet) · Maximilien Rambaud, Cosme de Ranieri, Aristote Pellissier, Nathanaël Muller

AI agents are the web's fastest-growing audience: about 1.7% of web activity in 2026, a quarter of web traffic expected by 2035 (DataDome, June 2026; Cisco, 2026). They read pages without seeing ads or paying, so websites earn almost nothing from them, and blocking agents is their only safe default. On the other side, an agent that needs one precise figure can only scrape public pages, or buy a whole report built for humans, which it cannot do on its own.

Doubloon makes every website **payable for all AI agent readers**. A content owner pastes its URL, and in about 60 seconds its content becomes data that any AI agent can discover, negotiate for and buy, with no code. For publishers, it is a **new revenue stream** from an audience that never sees an ad. For buyers, it is **access to information without buying the whole report**: one figure for 0.10 USDC, a small table for 0.50, a full section for 2.00, while the rest of the report stays protected.

Every sale runs on **x402**, the open protocol that finally puts HTTP's `402 Payment Required` to work. The agent receives an invoice, signs a payment and gets the data in seconds, settled in **USDC on the Base blockchain**. Every transaction is public and verifiable, and the publisher is paid before any data leaves.

| Submission documents | |
| --- | --- |
| Technical Documentation (PDF, submitted with this repository) | Architecture, payment flow, core algorithms, data model, API, deployment, evidence, limits |
| Security Self-Assessment Report (PDF, submitted with this repository) | Threat model, 6 permission tiers, 24 controls, 18 known risks, evidence, hardening roadmap |
| [On-chain evidence](payments/docs/ONCHAIN_EVIDENCE.md) | Every payment, read from the chain's USDC `Transfer` logs |

---

## Contents

1. [Proof it works](#proof-it-works)
2. [Who it is for](#who-it-is-for)
3. [How it works](#how-it-works)
4. [Why x402 and the blockchain](#why-x402-and-the-blockchain)
5. [Security and compliance](#security-and-compliance)
6. [The demo](#the-demo)
7. [Use your own Claude as a buyer](#use-your-own-claude-as-a-buyer)
8. [Run it locally](#run-it-locally)
9. [Repository map and tech stack](#repository-map-and-tech-stack)
10. [Limits and roadmap](#limits-and-roadmap)

---

## Proof it works

Real payments, not mock-ups, verifiable by anyone on a public block explorer:

- **64 payments settled on-chain**: 62 on Base Sepolia (39.21 test USDC, 17 to 19 October 2026) and 2 on Base mainnet with real USDC.
- **A full product sale on Base mainnet**: agent identity check, sales agent negotiation, LLM decision, code guards, x402 payment, delivery after settlement, for 0.10 USDC: [transaction on basescan.org](https://basescan.org/tx/0xc70ea043716023f1e76ef26dac5e27c814d51ae0ca541d797ee249c949d36f8f).
- **A 2.00 USDC sale paid only after human approval**: [transaction on Base Sepolia](https://sepolia.basescan.org/tx/0xb59df8f6496f54d360c487d052cc10fa888a9cb6b97664d1fe2a8552050d80ea).
- **160 automated tests** across gateway, ingestion, payments, buyer agent and MCP connector.

The full list is read from the chain itself, not from our database: [payments/docs/ONCHAIN_EVIDENCE.md](payments/docs/ONCHAIN_EVIDENCE.md).

The demo publisher is **Velstrand Research**, a fictional research firm whose company names and figures are invented: [velstrand-research.vercel.app](https://velstrand-research.vercel.app).

---

## Who it is for

Three types of content owners cannot get paid by AI agents today:

| Content owner | Earns from | Why agents don't pay | Order |
| --- | --- | --- | --- |
| **Research and data providers** (market studies, reports, datasets) | Reports sold for thousands of euros | Agents need one figure, not a whole report | **Now, initial focus** |
| Subscription publishers (news, magazines, professional databases) | Monthly or yearly subscriptions | Agents need one article, not a subscription | Next |
| Ad-funded websites (news, blogs, reviews) | Ads shown to human readers | Agents read the page but never see an ad | Then |

**Business model.** Publishers set their prices and keep them in full. Doubloon's planned revenue is a fixed fee of 0.01 USD per transaction, paid by the buyer on top of the publisher's price. The prototype does not charge this fee yet.

---

## How it works

### For the publisher: about 60 seconds, no code

1. **Paste the website URL.** Doubloon crawls it (respecting `robots.txt`), reads HTML pages and PDF reports, and splits them into sections.
2. **Review the catalog.** Mark each section *Sell*, *Free* or *Private*. Pages that look internal are detected and kept private. Agents only ever see titles and topics, never a figure.
3. **Write prices in plain words**, such as "one figure at $0.10, a small table at $0.50, a full section at $2.00". An LLM turns them into a price table that the publisher confirms. From then on, every check uses that confirmed table.
4. **Connect a wallet and go live.** A signed manifest tells agents what is for sale and where to pay. USDC goes straight to the publisher's wallet, and a dashboard shows every sale with its audit trail.

### For the buyer agent: a sale in six steps

1. **Discover.** Read the publisher's signed manifest (`/.well-known/ai-data.json`) and check the signature.
2. **Identify (KYA, Know Your Agent).** Sign a one-time code with its wallet. The wallet is screened against the US sanctions list.
3. **Negotiate.** Explain the need to the publisher's sales agent, a language model that only sees titles and never the figures. Code checks every offer: price, tier, and that no paid figure leaks.
4. **Decide.** Code checks the budget, the per-purchase cap and daily limits. Above 1.00 USDC, the owner must say yes.
5. **Pay (x402).** Receive a `402` invoice, sign a USDC transfer (EIP-3009); a facilitator settles it on Base and pays the gas.
6. **Deliver.** Only after settlement: the data, watermarked for the buyer, with a license receipt signed by the publisher.

**The design rule throughout: a language model may propose, but only code decides price, permission and money.**

### Architecture

```
   PUBLISHER WEBSITE              ANTHROPIC API (LLM)               BUYER AGENT
   pages, PDF reports             metadata, pricing rules,          our test agent, or anyone's
                                  sales agent, buyer choice         own Claude through MCP
          | crawl                          | structured JSON                 | HTTP + x402
          v                                v                                 v
+------------------------------------------------------------------------------------------+
|                               DOUBLOON GATEWAY (FastAPI)                                  |
|   Ingestion                  Discovery and sales                 Payments                 |
|   crawler, catalog,          signed manifest, KYA, sales         x402 paid routes,        |
|   leak filter                agent, offer checks, live events    settle first, receipts   |
|   Compliance: sanctions screening, SHA-256 audit chain, signed receipts, watermark        |
|   Shared SQLite: catalog, offers, transactions, events                                    |
+------------------------------------------------------------------------------------------+
          | REST + live events             | balanceOf                       | /verify, /settle
          v                                v                                 v
   WEB APP (Next.js)              BASE (USDC contract)  <-----------  x402 FACILITATOR
   onboarding, live view,         public record of sales             submits the transfer,
   dashboard, MetaMask                                               pays the gas
```

Every step emits an event. The live view and the audit trail are built only from these events, so what the screen shows is what happened. The full algorithms are in the Technical Documentation.

---

## Why x402 and the blockchain

- **x402 lets machines pay machines over plain HTTP.** One purchase is four messages: request, `402` invoice, retry with a signed payment, content with its receipt. No account, no card, no checkout page.
- **No fixed fee.** x402 has no protocol fee and settlement on Base costs a fraction of a cent, so a sale of a few cents stays profitable where card fees would eat it.
- **Instant, final settlement.** USDC reaches the publisher in seconds, with no monthly payouts and no chargebacks.
- **EIP-3009 signatures** authorise one exact transfer (amount, recipient, 120-second window, single-use nonce). The agent needs no gas: the facilitator submits the transfer.
- **The blockchain is the receipt.** Every sale is public and verifiable by the publisher, the buyer and any auditor, without trusting our database.
- **Same code on testnet and mainnet.** Moving from Base Sepolia to Base mainnet is configuration only, and has been done.

---

## Security and compliance

Code, not AI, decides every price, permission and payment.

| Question | Answer | How |
| --- | --- | --- |
| Can anyone get paid data without paying? | No | Content leaves only after on-chain settlement, to the paying wallet. The sales agent never sees paid content, and a leak filter checks every message |
| Can a wallet pay the wrong amount or party? | No | The invoice is fixed server-side, the buyer checks every field against the signed manifest, and each payment is unique (replay refused with 409) |
| Can an agent spend more than its owner allows? | No | Budget (5.00 USDC), per-purchase cap (2.50), daily and hourly caps are checked in code before signing. A human approves anything above 1.00 USDC |

Main controls, among the 24 listed in the report:

| Risk | Control | Where |
| --- | --- | --- |
| Fake agent, sanctioned or blocked wallet | KYA signature on a single-use nonce, OFAC SDN screening (Chainalysis oracle), short session bound to the identity | `gateway/routers/kya.py`, `shared/sanctions.py` |
| Fake payment address | The publisher signs its manifest; the buyer pins the signer and refuses a changed or unsigned one | `shared/signing.py`, `buyer-agent/agent.py` |
| Sales agent leaks or misprices | It sees metadata only. Deterministic checks on tier, exact price, sellable content, daily limit and leaks before any offer reaches the buyer | `gateway/sales_agent.py`, `ingestion/leak_filter.py` |
| Prompt injection | Buyer text is untrusted data, flagged and logged; prices come from the confirmed table only | `gateway/sales_agent.py` |
| Client changes the amount, replays a payment | Invoice rebuilt server-side, payer must be the KYA wallet, unique nonce and offer | `payments/router.py`, `payments/store.py` |
| Data taken without paying, or paid but not delivered | Settlement before delivery; recovery from the chain after a crash; 24-hour re-download | `payments/router.py`, `payments/recovery.py` |
| Agent overspends or splits purchases | Spending limits in code, near-threshold splitting forces approval, signing ceiling in the x402 client | `buyer-agent/agent.py`, `buyer-mcp/server.py` |
| History rewritten, proof of sale, resale | SHA-256 audit chain, publisher-signed license receipt, per-buyer watermark | `shared/audit_chain.py`, `payments/watermark.py` |
| Personal data kept forever | Conversations erased after 30 days and on request; payment records kept (AML) | `shared/retention.py` |
| Setup, dashboards or buyer controls exposed | Owner only: a caller on the gateway's machine, or an owner token | `shared/owner.py`, `payments/buyer_router.py` |
| Secrets | `.env` (git-ignored) and encrypted keystores; confidential values masked in every logged event | `shared/events.py`, `scripts/encrypt_keys.py` |

Threat model, permission tiers, all 24 controls, the 18 known risks and the evidence for each: Security Self-Assessment Report. Regulatory references (OFAC, GDPR, AML record keeping, China PIPL): [docs/SECURITY_AND_COMPLIANCE.md](docs/SECURITY_AND_COMPLIANCE.md).

---

## The demo

Three minutes, no terminal on screen. Run sheet: [frontend/DEMO.md](frontend/DEMO.md).

1. **A publisher goes live.** Paste the Velstrand URL, review the catalog ("Internal notes" is already private), write the prices in plain words, connect the wallet, go live.
2. **Someone's own Claude buys.** In Claude Desktop: "find the 2025 European market share of the leading battery manufacturer". Claude discovers the site, proves its identity, gets an offer at 0.10 USDC, asks for confirmation, pays, and shows the figure with its transaction link. The live view shows each purchase as a conversation between the buyer's agent and the sales agent.
3. **A bigger purchase needs the owner.** A full section at 2.00 USDC is above the 1.00 limit, so Claude asks its user first.
4. **Security.** A prompt injection is blocked on screen.
5. **The publisher gets paid.** The dashboard shows revenue, each sale with its audit trail, and the blockchain payment history.

Backup: with mock data (`NEXT_PUBLIC_USE_MOCKS=true`), the live view offers scenario buttons that replay the same story without a gateway or a wallet.

---

## Use your own Claude as a buyer

`buyer-mcp/` is an MCP server. Add it to Claude Desktop or Claude Code and your own Claude becomes a buyer agent:

| Tool | What it does |
| --- | --- |
| `search_data(question)` | Reads the manifest and the free catalog summary |
| `ask_seller(message)` | Proves the wallet identity on first use, then talks to the sales agent and returns any offer with a budget verdict |
| `buy(offer_id, owner_approved)` | Checks the offer and the invoice, signs the x402 payment, returns the data and the explorer link |
| `wallet_status()` | Wallet, on-chain USDC balance, budget left, receipts |

Money is never left to the LLM: only offers the sales agent really made can be bought, the price comes from that offer, and budget, cap and invoice are checked in code with the same guards as the test agent. Setup: [buyer-mcp/README.md](buyer-mcp/README.md).

---

## Run it locally

Requirements: Python 3.11+, Node 20+, an Anthropic API key, and test USDC on Base Sepolia for the buyer wallets ([faucet.circle.com](https://faucet.circle.com)).

```bash
# 1. Backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r payments/requirements.txt -r ingestion/requirements.txt -r buyer-mcp/requirements.txt
cp .env.example .env                        # set JWT_SECRET (32+ chars) and ANTHROPIC_API_KEY
.venv/bin/python scripts/create_wallets.py  # publisher + 4 buyer wallets, then fund the buyers
.venv/bin/python scripts/encrypt_keys.py --apply --rewrite-env   # move keys to encrypted keystores
.venv/bin/python scripts/check_funds.py
.venv/bin/uvicorn gateway.main:app --port 8000

# 2. Simulated publisher site (or use https://velstrand-research.vercel.app)
.venv/bin/python site-demo/serve.py --port 8001   # local scan needs SCAN_ALLOW_PRIVATE_HOSTS=1

# 3. Web app
cd frontend && npm install
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000 npm run dev   # http://localhost:3000

# 4. Before a demo
.venv/bin/python scripts/preflight.py       # config, gateway, catalog, facilitator, RPC, balances, audit chain
```

- Without `NEXT_PUBLIC_GATEWAY_URL`, the web app runs on built-in mock data, with a "mock data" badge in the navigation.
- Base mainnet with real USDC: create `.env.mainnet` and prefix commands with `scripts/mainnet.sh` (see its header).
- Interactive API docs of the running gateway: http://localhost:8000/docs.

### Tests

```bash
.venv/bin/python -m pytest gateway/tests ingestion/tests payments/tests buyer-agent buyer-mcp/tests -q
cd frontend && npx tsc --noEmit && npm run lint
```

The gateway tests replace the LLM with scripted outputs, so they need no API key. End-to-end scripts that run against a live gateway and the chain are listed in [payments/docs/PAYMENTS.md](payments/docs/PAYMENTS.md).

---

## Repository map and tech stack

| Folder | What it is |
| --- | --- |
| `site-demo/` | Simulated publisher site (Velstrand Research), built from `truth.json`, deployed on Vercel |
| `ingestion/` | Crawler, splitting of PDF reports and data-rich HTML pages, catalog, leak filter, publisher scan endpoints ([README](ingestion/README.md)) |
| `gateway/`, `shared/` | FastAPI app: manifest, discovery, KYA, sales agent, offers, pricing rules, audit, live events; shared schemas, database, events and compliance modules ([README](gateway/README.md)) |
| `payments/` | x402 paid routes, replay protection, receipts, watermark, recovery, on-chain balances, stats ([PAYMENTS](payments/docs/PAYMENTS.md)) |
| `buyer-agent/` | Autonomous test buyer agent with budget, cap, approval, invoice and manifest checks |
| `buyer-mcp/` | MCP connector: anyone's own Claude becomes a buyer agent ([README](buyer-mcp/README.md)) |
| `frontend/` | Next.js web app: onboarding, live view, dashboard ([README](frontend/README.md), [DEMO](frontend/DEMO.md)) |
| `scripts/` | Wallet creation, key encryption, funds check, pre-demo preflight, on-chain evidence, mainnet launcher |
| `docs/` | Compliance reference with regulations ([SECURITY_AND_COMPLIANCE.md](docs/SECURITY_AND_COMPLIANCE.md)), images |

| Layer | Tools |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn, Pydantic v2, SQLite |
| Crawling and parsing | httpx, BeautifulSoup, PyMuPDF, `robots.txt` via `urllib.robotparser` |
| LLM | Anthropic API (Claude) with structured JSON output: sales agent, pricing rules, catalog metadata, buyer decisions |
| Payments | x402 v2 (official Python SDK), EIP-3009, x402 facilitator (x402.org on testnet, PayAI on mainnet) |
| Blockchain | Base Sepolia and Base mainnet, USDC, `eth_account`, `web3.py`, Chainalysis sanctions oracle |
| Agent connector | Model Context Protocol (MCP) Python SDK |
| Web app | Next.js, React, Tailwind, wagmi and viem (MetaMask), Server-Sent Events |
| Hosting | Vercel (publisher site) |

---

## Limits and roadmap

**Priority 1: sell from the publisher's own domain.** Today, agents find the publisher through its manifest, then negotiate and pay on the Doubloon gateway: for the demo, we chose not to expose our own computers through a public tunnel. Next, the `402` comes from the publisher's own URL, through an edge proxy that forwards only the agent routes, or a plugin on the publisher's server (WordPress, Next.js, Cloudflare Worker). Humans keep seeing the normal pages.

**Priority 2: price each fact, not each section.** Today, the smallest unit sold is a report section, so a 0.10 "one figure" sale delivers a paragraph with several figures. Next, a classifier splits each report into individual facts, each with its own price.

**Then:**

- **Agent identity.** Agents are recognised by the identity headers they send (`X-Agent-Id`, `X-Agent-Wallet`), so an undeclared bot is treated as a human visitor and can read public pages. KYA proves who pays, not whether the caller is a bot. Next: accept signed bot requests (Web Bot Auth, IETF draft) next to wallet KYA. The strongest protection is that premium content is not public at all.
- **Publisher onboarding.** Domain ownership is not verified yet, and the demo site's paid PDFs are public because the scan reads them there (the gateway itself never serves paid content before settlement). Next: verify domain ownership, and scan reports from an upload or a private URL.
- **Keys and compliance.** Move keys to a KMS or server wallet, add the EU, UN and UK sanctions lists, and anchor the audit trail on-chain.
- **Scale and uptime.** A second facilitator, with approvals and rate limits in a shared store.
- **Business model.** Charge the planned 0.01 USD per-transaction fee.

**Out of scope for now:** refunds and disputes, multi-publisher marketplace, protection against rebuilding a report from many wallets beyond the daily limit.

The full limits, with the 18 known risks and their status, are in the Security Self-Assessment Report.
