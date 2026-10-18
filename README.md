# FinHack

Paste your website URL and turn your proprietary content into data that AI agents can discover, negotiate and pay for in stablecoins (USDC on Base Sepolia, x402 protocol). The full brief is in [agent.md](agent.md).

| Folder | Role | What it is |
|---|---|---|
| `site-demo/`, `ingestion/` | P1 | Simulated publisher site ([velstrand-research.vercel.app](https://velstrand-research.vercel.app)), crawler, catalog, leak filter |
| `gateway/`, `shared/` | P2 | FastAPI gateway: discovery, KYA, Sales agent, offers, rules, audit, events |
| `payments/`, `buyer-agent/`, `scripts/` | P3 | x402 paid routes, replay protection, balances, test buyer agent |
| `frontend/`, `buyer-mcp/` | P4 | Onboarding, live view, dashboard; connector that lets anyone's own Claude buy |

Demo run sheet: [frontend/DEMO.md](frontend/DEMO.md). Connector setup: [buyer-mcp/README.md](buyer-mcp/README.md).

## Limits and proposed improvements

### 1. Agents buy on our gateway, not on the publisher's domain

**Today.** The agent finds the publisher, then discovers, proves its identity, negotiates and pays on our gateway. The publisher's site only points to it. This is the scope chosen in agent.md (section 11): no DNS proxy, no middleware on the publisher's server.

**Proposed.** The agent does everything on the publisher's own domain, which is what x402 is designed for: it requests `velstrand-research.vercel.app/...` and gets the 402 invoice, then the data, from that site. Humans keep seeing the normal pages. Cloudflare's "Pay per crawl" works the same way.

```
Agent → publisher domain (Vercel rewrites of agent routes) → public tunnel → agent edge proxy → gateway
```

What it takes (about 1 to 2 hours):

1. **Agent edge proxy**: a small proxy in front of the gateway that only forwards the agent routes: `/.well-known/ai-data.json`, `/discover`, `/kya/*`, `/session/message`, `/offer/accept`, `/query/*`, `/receipt/*`. It must block everything else, because the publisher routes have no auth (anyone could change the payTo wallet) and the buyer controls trust loopback callers (a tunnel connects from loopback).
2. **Public URL for the gateway**: a tunnel (Cloudflare Tunnel or ngrok) or a hosted gateway. Use a named tunnel or a fixed host: a free quick tunnel changes URL on every restart.
3. **Vercel rewrites** in `site-demo/deploy.py`: proxy the agent routes above to the gateway. An agent that opens a report directly (request with `X-Agent-Id`) gets what is for sale in it and how to buy, instead of the file.
4. **`GATEWAY_PUBLIC_URL`** set to the publisher's URL, so the manifest sends agents to the publisher's domain.
5. Redeploy the site (needs P1's `VERCEL_TOKEN`).

In production, the same idea becomes a DNS proxy or a middleware or plugin on the publisher's server (WordPress, Next.js, Cloudflare Worker), plus a check that the person onboarding owns the domain.

### 2. Recognising agents relies on them declaring themselves

**Today.** An agent is recognised by the `X-Agent-Id` and `X-Agent-Wallet` headers it sends on every request (agent.md 7.2, step 2). A request without them is treated as a human and redirected to the website. KYA then proves the agent controls its wallet (signed nonce) and that the wallet is not blocklisted.

**Limit.** This works for agents that play by the rules. A bot that does not declare itself is seen as a human visitor: it gets the public site and can scrape whatever is public there. KYA proves who pays, not whether the caller is a bot.

**How it is done in the real world**, usually combined:

| Method | How it works | Reliability |
|---|---|---|
| User-Agent | Known crawlers announce themselves (`GPTBot`, `ClaudeBot`, `PerplexityBot`) | Easy to fake |
| Verified IP ranges and reverse DNS | OpenAI, Anthropic and Google publish the addresses their crawlers use | Reliable for the big providers |
| Signed requests (Web Bot Auth, IETF draft) | The bot signs each HTTP request with a published key; used by Cloudflare's Pay per crawl | Reliable, cryptographic |
| Behavioural bot detection | Request rate, no JavaScript, navigation patterns (Cloudflare, Akamai, DataDome) | Probabilistic |

For FinHack: accept signed requests (Web Bot Auth) next to our wallet KYA, and treat unknown bots as unpaid visitors. The strongest protection is not detection: premium content is not public at all and is only served to agents that pay.

### 3. Paid PDFs are public on the demo site

The report PDFs sold in the demo are downloadable by anyone on the simulated site (for example `/reports/rpt_battery_2025.pdf`), because the crawler reads them from there. Any bot, or a juror, can get them without paying. Fix (P1): keep the PDFs out of `public/` and give them to the scan another way (upload or a private URL), so the site only shows the locked previews.

### 4. Other limits

- Only test USDC on Base Sepolia. Moving to mainnet is a configuration change (agent.md section 10) once everything works on testnet.
- Selling public HTML pages is only meaningful as licensed data (right to use, provenance, receipt). Scanning someone else's site is a technical test, not something we may sell.
- Above the approval threshold, the `finhack-buyer` connector relies on the assistant asking its user in chat, plus the host's tool permission prompt. The budget and per purchase caps are enforced in code whatever the assistant does.
