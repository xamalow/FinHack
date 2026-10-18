# Gateway (P2)

One FastAPI app for every role. P2 owns discovery, KYA, the Sales agent, offers, rules, audit and events, plus `/shared`.

## Run

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env    # then set JWT_SECRET and ANTHROPIC_API_KEY
.venv/Scripts/python -m uvicorn gateway.main:app --reload --port 8000
```

API docs are at http://localhost:8000/docs. Tests run with `.venv/Scripts/python -m pytest gateway/tests -q`. The tests script the LLM, so they need no API key.

## For other roles

| You are | What you use from P2 |
|---|---|
| Everyone | `from shared.events import log_event` and `log_event(session_id, actor, type, summary, payload)`. Unknown types raise, so add new ones to `EVENT_TYPES` in `shared/events.py` through P2. Payload keys containing `token`, `secret`, `private_key`, `authorization` and similar are masked. |
| Everyone | `from shared import db`: all tables from agent.md 6.1 plus `kya_challenges`. Call `db.init_db()` once. Timestamps are ISO UTC strings (`db.now_iso()`). |
| P1 | Export `get_catalog`, `get_content`, `contains_paid_figures` from `ingestion/__init__.py`. Until then `gateway/p1_bridge.py` reads the `catalog`/`content` tables, then falls back to `gateway/mock_catalog.json`. You can write rows with `db.upsert_catalog_item()` and `db.set_content()`. Put your router at `gateway/routers/publisher_scan.py` exposing `router`; `main.py` registers it automatically. |
| P3 | `payments.router` and `payments.buyer_router` are registered automatically. `gateway/integration.py` implements the `payments/deps.py` interface (`get_session`, `get_offer` with `expires_at` as epoch, `set_offer_status`, `get_tier_price`, `get_publisher_wallet`, `get_content`, `log_event`). After the merge, `deps.py` only needs to import from it. The buyer must send `X-Agent-Id` and `X-Agent-Wallet` on `/discover` too, otherwise it gets a 307. |
| P4 | Live view: `GET /events/stream` (SSE default `message` events, so `EventSource.onmessage` works; `data` = event JSON, `id` = event_id; add `?session_id=` to filter, `?after_id=0` to replay everything). History: `GET /events`. Audit: `GET /audit/{offer_id}`. Onboarding: `PUT /publisher/rules`, `POST /publisher/rules/confirm`, `POST /publisher/wallet`, `POST /publisher/activate`. CORS allows `CORS_ORIGINS`. |

## Buyer flow

1. `GET /.well-known/ai-data.json` returns the manifest. It is 404 until the publisher activates.
2. `GET /discover?q=` with headers `X-Agent-Id` and `X-Agent-Wallet`. Requests without these headers get a 307 redirect to `DEMO_SITE_URL`.
3. `POST /kya/challenge` returns `{nonce, message}`. Sign the nonce (or `message`) with EIP-191 (`Account.sign_message(encode_defunct(text=nonce), key)`).
4. `POST /kya/verify` takes `{nonce, signature}` and returns `{session_id, token, session_token}` (the two are the same value). Then send `Authorization: Bearer <token>` together with the identity headers.
5. `POST /session/message` takes `{message}` and returns `{action, message_to_buyer, offer?}`.
6. `POST /offer/accept` takes `{offer_id}` and returns `{route, pay_url, price_usdc}`. Then pay on `POST /query/{route}` (P3).

## Sales agent guarantees

- The LLM sees catalog metadata only, never paid content or excluded items.
- Every output passes deterministic checks before reaching the buyer: the tier exists, the price equals the tier price, there is exactly one sellable `content_id`, the daily limit of `DAILY_SECTION_LIMIT` sections per report per agent holds, the leak filter passes on the message and scope, and at most one clarifying question is asked. A rejected output gets one retry with the errors as feedback, then a safe refusal.
- Prompt injection is flagged by both a regex and the LLM, and is logged as `injection_ignored`.
- If the LLM is down, the Sales agent returns a safe refusal and the rules endpoint falls back to a deterministic parser.
