# Frontend (P4)

Next.js app for the publisher onboarding, the live view and the publisher dashboard (agent.md section 8, P4).

## Run

```bash
cd frontend
npm install
cp .env.example .env.local   # optional
npm run dev                  # http://localhost:3000
```

With `NEXT_PUBLIC_GATEWAY_URL` empty, every screen runs on mock data and a "mock data" badge shows in the nav. Set it to the gateway (for example `http://localhost:8000`) to use the real endpoints and `GET /events/stream`.

## Screens

| Route | What it shows | Endpoints used |
|---|---|---|
| `/onboarding` | URL and scan animation (scan events), catalog review, rules to tiers, MetaMask on Base Sepolia, Activate | `POST /publisher/scan`, `GET/PATCH /publisher/catalog`, `PUT /publisher/rules`, `POST /publisher/rules/confirm`, `POST /publisher/wallet`, `POST /publisher/activate` |
| `/live` | Three columns from the event stream, clickable JSON payloads, explorer links, on-chain balances, approval button, mission and budget | `GET /events/stream`, `POST /buyer/run`, `POST /buyer/approve`, `GET /balance/{address}`, `GET /.well-known/ai-data.json` |
| `/dashboard` | Revenue, requests, transactions, audit per sale | `GET /publisher/stats`, `GET /transactions`, `GET /audit/{offer_id}` |

## Code map

- `src/lib/types.ts` copies the shared contracts (agent.md section 6). Keep it in sync with `/shared/schemas.py`.
- `src/lib/api.ts` is the only place that knows request and response bodies. When P2 or P3 freeze a body, adjust it here.
- `src/lib/mocks.ts` and `src/lib/mockBus.ts` hold the fake data and the scripted event sequences (0.10 sale, 2.00 sale with approval, security refusals).
- `src/lib/useEventStream.ts` reads the SSE stream, or the mock bus.

## Assumptions to confirm with P2 and P3

- `PUT /publisher/rules` takes `{ raw_text }` and returns `{ tiers }` or a tier array.
- `PATCH /publisher/catalog/{id}` takes `{ status }`. `POST /publisher/wallet` takes `{ wallet_address }`.
- `POST /buyer/run` takes `{ mission, budget_usdc }` and returns `{ session_id }`. `POST /buyer/approve` takes `{ offer_id }`.
- `GET /balance/{address}` returns `{ balance_usdc }`.
- SSE messages are `data: <event JSON>` with the event shape of section 6.4. Transaction hashes are in `payload.tx_hash` (or `payload.transaction` for `settle_response`).
- `balance_changed` triggers an immediate balance refresh; the view also polls every 2 seconds.
- The gateway must allow CORS from the frontend origin.

Demo run sheet: [DEMO.md](DEMO.md).
