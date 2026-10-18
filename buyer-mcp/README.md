# Buyer connector for your own AI assistant (P4)

An MCP server that lets anyone use **their own Claude** (Claude Desktop or Claude Code) as a buyer agent. They ask in plain language, the assistant discovers the publisher, proves its identity, negotiates with the Sales agent, pays in test USDC and gets the data. Every step shows up in the live view, tagged "Via the user's own AI assistant".

## Tools the assistant gets

| Tool | What it does |
|---|---|
| `search_data(question)` | Reads the manifest and the free `/discover` summary. Topics and periods, never figures. |
| `ask_seller(message)` | Proves wallet ownership (KYA) on first use, then sends one message to the Sales agent. Returns its reply and, if any, a priced offer with a budget verdict. |
| `buy(offer_id, owner_approved=false)` | Accepts the offer, checks the 402, signs the EIP-3009 authorization, pays, returns the data and the explorer link. |
| `wallet_status()` | Wallet address, on-chain USDC balance, budget left, receipts. |

## Guardrails (in code, not in the LLM)

- Only offers the Sales agent really made in `ask_seller` can be bought. The price always comes from that offer, never from the assistant.
- Budget, per purchase cap and approval threshold are checked with P3's `check_offer`, and the 402 with `check_payment_required` (amount, network, asset, payTo equal to the manifest), before any signature. Same rules as P3's buyer agent, same `.env` limits.
- Above the approval threshold (1.00 USDC by default), `buy` refuses until it is called again with `owner_approved=true`. The assistant is told to ask the user in chat first. This step relies on the assistant and on the host's tool permission prompt, so keep "ask every time" for `buy` in Claude Desktop. The hard caps (budget, 2.50 per purchase) still apply whatever the assistant does.
- Seller replies and delivered data are returned under `*_untrusted` keys, as data.
- The private key stays in `.env` on the machine running the connector. Testnet only.

## Setup

The connector runs on the same machine as the gateway: it writes its events into the gateway database so the live view shows them.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r ingestion/requirements.txt -r buyer-mcp/requirements.txt
```

`.env` at the repo root (see `.env.example`):

```
MCP_BUYER_PRIVATE_KEY=0x...      # a funded Base Sepolia test wallet, defaults to BUYER_PRIVATE_KEY_1
MCP_BUDGET_USDC=5.00             # defaults to BUYER_BUDGET_USDC
MCP_MANIFEST_URL=http://127.0.0.1:8000/.well-known/ai-data.json
```

The publisher must be activated (onboarding done) so the manifest exists.

### Claude Desktop

Settings, Developer, Edit Config, then add (absolute paths):

```json
{
  "mcpServers": {
    "finhack-buyer": {
      "command": "/ABSOLUTE/PATH/FinHack/.venv/bin/python",
      "args": ["/ABSOLUTE/PATH/FinHack/buyer-mcp/server.py"]
    }
  }
}
```

Restart Claude Desktop, the tools appear under the connectors menu.

### Claude Code

```bash
claude mcp add finhack-buyer -- /ABSOLUTE/PATH/FinHack/.venv/bin/python /ABSOLUTE/PATH/FinHack/buyer-mcp/server.py
```

## Demo prompts

1. "Use finhack-buyer to find the 2025 European market share of the leading battery manufacturer. One figure is enough. Tell me the price before buying."
2. "Now I need the full methodology section of that report." The price is 2.00 USDC, above the threshold, so the assistant asks you. Answer "yes, go ahead".
3. "What did I spend so far?" → `wallet_status`.

## Status

Tested on a local merge of the four branches with a throwaway wallet: discovery, KYA, Sales agent call, live view events, balance read and the refusal of an offer the seller never made all work. The Sales agent needs a valid `ANTHROPIC_API_KEY` to make offers, and the payment needs a funded wallet, so the paid part (`buy` up to the transaction hash) has not run end to end yet.
