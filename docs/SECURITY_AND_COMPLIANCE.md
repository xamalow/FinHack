# Security and compliance: reference for the docs

This file is the written record of every security and compliance control in Doubloon. It covers what each control does, why it exists, where the code is, how it was tested, what it shows in the live view, and the regulation or standard behind it. Use it as the source when writing the README, the deck or the submission.

Last update: 18 Oct 2026. Status: everything below is on `main`. 159 automated tests pass. Each control was also checked live on Base Sepolia (testnet USDC), and the connector end-to-end test passed 13/13.

Related documents:
- [payments/docs/SECURITY_P3.md](../payments/docs/SECURITY_P3.md): payment controls, buyer permission tiers, risk register.
- [payments/docs/ONCHAIN_EVIDENCE.md](../payments/docs/ONCHAIN_EVIDENCE.md): real transactions on testnet and mainnet.
- [gateway/README.md](../gateway/README.md): Sales agent guarantees.

---

## 1. Summary for a jury (one paragraph)

AI agents pay publishers in USDC. So Doubloon treats every sale as a financial transaction between two parties that do not trust each other.

Before any money moves:
- Both sides screen each other's wallet against the US Treasury sanctions list (OFAC SDN), read on-chain from the Chainalysis oracle.
- The buyer agent checks that the payment address is signed by the publisher.
- The buyer agent enforces spending limits per payment, per day and per hour, in code.
- When purchases look split to dodge the human approval threshold, the agent asks its owner.

After the payment:
- The publisher signs a license receipt that ties the on-chain transaction to what was sold and under which license.
- It watermarks the data for that buyer, so a leak can be traced back to the sale.

Every step goes into an audit log chained by SHA-256, which anyone can verify. Personal data is erased after 30 days, while the financial records are kept, as AML rules require.

---

## 2. Compliance controls

### 2.1 Sanctions screening (OFAC SDN)

| | |
|---|---|
| What | Every wallet that pays or gets paid is checked against the OFAC Specially Designated Nationals list before any money moves. |
| Where it runs | **Seller:** the agent wallet at identity check (KYA); the payer again right before settlement; the publisher payout wallet when it is set. **Buyer:** the publisher's `payTo` before signing a payment. |
| Source | 1) The local blocklist `KYA_BLOCKLIST`. 2) The Chainalysis sanctions oracle: a free on-chain contract that mirrors the crypto addresses on the OFAC SDN list. The call is `isSanctioned(address) -> bool`, at `0x40C57923924B5c5c5455c48D93317139ADDaC8fb`. |
| Chain read | Ethereum mainnet, through `SANCTIONS_RPC_URL` (default publicnode). An EVM address is the same on every chain, and on 18 Oct 2026 this contract was **not** deployed at that address on Base mainnet. Verified live: a Lazarus Group address (Ronin hack, OFAC-listed) returns `true`, and our wallets return `false`. |
| Oracle down | `SANCTIONS_FAIL_MODE`: `closed` refuses, `open` lets the wallet through and logs it. Default: closed on Base mainnet (real money), open on testnet (demo). |
| Cache | 1 hour per address. |
| Code | `shared/sanctions.py`. Called from `gateway/routers/kya.py`, `gateway/routers/rules.py` (payout wallet), `payments/router.py` (before reserve and settle), `buyer-agent/agent.py` and `buyer-mcp/server.py` (before signing). |
| Events | `sanctions_screened` (shown as "Sanctions check passed · OFAC list · Chainalysis oracle"), `sanctions_blocked`. |
| Tests | `gateway/tests/test_compliance.py`: a listed wallet is refused at KYA and marked blocked; a passed screening is logged in the session; fail closed on mainnet and open on testnet; a sanctioned payout wallet is refused. |
| References | OFAC, *Sanctions Compliance Guidance for the Virtual Currency Industry* (Oct 2021); OFAC SDN list (digital currency addresses since 2018); Chainalysis Sanctions Oracle documentation. |
| Limits | The oracle covers OFAC only, not EU, UN or UK lists. Chainalysis does not guarantee timeliness. Production would add a paid screening API (Chainalysis KYT, TRM, Elliptic) and other lists. |

### 2.2 Tamper-evident audit log

| | |
|---|---|
| What | Every event (identity, negotiation, payment, delivery) is chained to the previous one. Each event's hash is `sha256(prev_hash + event_id + sha256(event))`. Editing, deleting or inserting an event breaks the chain from that point. |
| How | `shared/db.insert_event` inserts the event and its chain row in one `BEGIN IMMEDIATE` transaction. The gateway and the MCP connector write the same SQLite file, and this way the chain cannot fork. |
| Verify | `GET /compliance/audit-chain` (owner) recomputes everything and lists the problems. `GET /compliance/audit-head` (public) returns the latest hash: publish it, or anchor it on-chain with `scripts/anchor_audit.py --send`, and the history up to that point is frozen. |
| Code | `shared/audit_chain.py`, `shared/db.py`, `gateway/routers/compliance.py`, `scripts/anchor_audit.py`, `scripts/preflight.py` (checks the chain). |
| Tests | `test_chain_is_valid_then_detects_edit_delete_and_insert`, `test_audit_head_is_public_and_full_check_is_owner_only`. |
| Live | 61 events chained, `ok: true` (18 Oct, testnet run). |
| References | EU AI Act art. 12 (automatic record-keeping for AI systems; Doubloon is not a high-risk system, this is done by choice); AMLD record keeping (see 2.5); the integrity part of GDPR art. 32. |
| Limits | Events from before this change are not chained (the chain starts at the first new event). On-chain anchoring is a manual script: it needs a little ETH on the signing key. |

### 2.3 Buyer velocity limits and structuring detection

| | |
|---|---|
| What | On top of the budget, the per-payment cap and the approval threshold (SECURITY_P3 §1), the buyer agent enforces three limits **per wallet, across runs and processes**: a daily cap (`BUYER_MAX_PER_DAY_USDC`, default 25), a number of purchases per hour (`BUYER_MAX_TX_PER_HOUR`, default 20), and structuring detection. |
| Structuring | 3 purchases in 24 h priced just under the approval threshold (80 to 100 % of it) force a human approval, even if each one alone is allowed. This stops an agent, or a seller steering it, from splitting a big purchase to avoid the owner's approval. |
| How | An append-only spend ledger (`buyer-agent/.spend_ledger.jsonl`, one line per payment) shared by the autonomous agent and the MCP connector. |
| Code | `buyer-agent/agent.py` (`SpendLedger`, `check_velocity`), `buyer-mcp/server.py`. |
| Events | `velocity_limit_hit`, `structuring_suspected`. |
| Tests | `buyer-agent/test_guards.py`: daily cap, old purchases ignored, hourly count, structuring forces approval, ledger kept per wallet. |
| References | The structuring concept from 31 U.S.C. § 5324 and FATF guidance on red-flag indicators; the human oversight principle of EU AI Act art. 14. |

### 2.4 Signed license receipt

| | |
|---|---|
| What | After settlement, the publisher signs a receipt. It contains: offer, tx hash, network, asset, payer, payee, amount, tier, scope, license, content ids, a SHA-256 of the exact content delivered, the watermark id and the issue date. It gives the buyer proof of a lawful purchase and of its license terms, and gives the publisher proof of what it delivered for which payment. |
| Signature | EIP-191 `personal_sign` over canonical JSON, with a domain line (`Doubloon license receipt v1`). Any Ethereum library can verify it offline. The key is the publisher signing key (see 3.2). |
| Buyer side | The buyer checks the signature against the key pinned from the manifest, and checks that the tx hash, payer and amount match its own payment. A bad receipt is flagged (`receipt_verified` with problems) so the owner can dispute the sale. |
| Public check | `POST /compliance/verify-receipt` returns whether the signature is valid and whether the sale is on record. A forged amount is caught (tested live). |
| Code | `shared/signing.py`, `payments/router.py` (`license_content`), `payments/store.py` (`license_receipts` table), `buyer-agent/agent.py` (`check_license_receipt`), `gateway/routers/compliance.py`. |
| Events | `license_receipt_issued` (gateway), `receipt_verified` (buyer). |
| Tests | `test_license_receipt_is_signed_stored_and_stable` (same receipt on re-delivery, tampering detected), `test_license_receipt_check`. |

### 2.5 Personal data retention and erasure

| | |
|---|---|
| Personal data | The free text agents send: missions, buyer messages, the Sales agent's replies, and the LLM outputs that quote them. |
| Retention | `PERSONAL_DATA_RETENTION_DAYS` (default 30). At each gateway start, and on `POST /compliance/purge` (owner), message rows are deleted and the event text is replaced by `[personal data erased]`. The audit chain keeps the hash of what was there, so it still verifies. |
| Erasure request | `POST /compliance/erase {wallet}` (owner) erases that wallet's conversations at once. |
| Kept | Offers, transactions, license receipts, wallet addresses and payment events. They are the record of a financial transaction and of its license. |
| Why kept | AML and accounting record keeping is a legal obligation, which is an exception to erasure. |
| Code | `shared/retention.py`, `gateway/main.py` (purge at start), `gateway/routers/compliance.py`. |
| Event | `personal_data_purged` ("Personal data erased"). |
| Tests | `test_purge_erases_old_conversations_and_keeps_the_chain_valid`, `test_erasure_request_removes_messages_but_keeps_financial_records`. |
| References | GDPR art. 5(1)(c) data minimisation, art. 5(1)(e) storage limitation, art. 17 erasure and 17(3)(b) the legal obligation exception, art. 25 data protection by design. EU AMLD (Directive 2015/849) art. 40: 5-year record keeping. China PIPL art. 19 (retention limited to the shortest necessary period) and art. 47 (deletion). |
| Also minimised | No IP address is stored (the rate limiter keeps them in memory only). Secrets are masked in events (`shared/events.py`). |

### 2.6 Owner-only access to data about buyers

The live view, the per-sale audit, the sales list, the stats and the compliance routes all hold buyer conversations or wallets. They are now restricted to the publisher: either from its own machine (loopback), or with `PUBLISHER_OWNER_TOKEN`.

- **Public routes:** discovery, KYA, Sales agent, paid routes, `/compliance/audit-head`, `/compliance/signer`, `/compliance/verify-receipt`.
- **Code:** `shared/owner.py`, `gateway/routers/events.py`, `gateway/routers/audit.py`, `payments/router.py`.
- **Test:** `test_dashboards_holding_buyer_data_are_owner_only`.

---

## 3. Security controls

### 3.1 Signed manifest, pinned by the buyer

| | |
|---|---|
| Threat | The buyer reads the publisher's payment address (`payTo`) from `/.well-known/ai-data.json`. If the DNS, the host or a proxy is compromised, the attacker changes `payTo` and the money goes to them. The buyer's 402 check (payTo must equal the manifest) does not help if the manifest itself is fake. |
| Control | The publisher signs the manifest (EIP-191, domain `Doubloon signed manifest v1`). The buyer trusts the first valid signer it sees for a publisher origin, the way SSH does, and pins it. From then on it refuses: a manifest whose content changed after signing, a manifest signed by another key, and an unsigned manifest. `BUYER_TRUSTED_SIGNERS` pins keys explicitly. `BUYER_REQUIRE_SIGNED_MANIFEST=1` (default on mainnet) refuses unsigned manifests even on first contact. |
| Code | `shared/signing.py`, `gateway/routers/discovery.py`, `payments/mock_gateway.py`, `buyer-agent/agent.py` (`check_manifest_signature`), `buyer-mcp/server.py`. |
| Events | `manifest_signature_checked`, `manifest_signature_failed`. |
| Tests | `test_manifest_is_signed_by_the_publisher_key` (a changed payTo is detected); `test_manifest_signer_is_pinned_then_enforced` (pin, tampered payTo, new key, downgrade to unsigned); `test_unsigned_manifest_refused_when_required`. |
| Limits | Trust on first use: the first contact must be genuine. Production would have the payout wallet (MetaMask) sign a one-time delegation to the signing key, or publish the signer in DNS, so the first contact is verifiable too. |

### 3.2 Keys out of plaintext

| | |
|---|---|
| Before | Buyer private keys were in plaintext in `.env` (git-ignored). |
| Now | `shared/keys.load_private_key(NAME)` accepts `NAME_KEYSTORE`: an encrypted keystore (Web3 Secret Storage v3, scrypt + AES-128-CTR, the format geth and MetaMask use). Its password is kept in the macOS Keychain (service `doubloon`), or in `KEYSTORE_PASSWORD` on machines without a Keychain. Plaintext still works, for dev. |
| Migration | `scripts/encrypt_keys.py` is a dry run by default. `--apply` writes `keys/<NAME>.json` (mode 600) and stores a random password in the Keychain. `--rewrite-env` also replaces the plaintext lines and keeps a backup that you delete by hand. `scripts/preflight.py` warns while keys are still in plaintext. |
| Publisher signing key | `PUBLISHER_SIGNING_KEY(_KEYSTORE)`. Without either, one is created once in `.publisher_signing_key` (mode 600, git-ignored), so buyers that pinned it keep trusting it after a restart. |
| Code | `shared/keys.py`, `scripts/encrypt_keys.py`, used in `payments/buyer_router.py`, `buyer-mcp/server.py` and the `buyer-agent/agent.py` CLI. |
| Tests | `test_private_key_loads_from_an_encrypted_keystore`, `test_encrypt_keys_script_removes_plaintext_from_the_env_file`. |
| Done on 18 Oct (P3's machine) | `.env` migrated: 4 buyer keys + the generated publisher key are in `keys/*.json`, passwords in the Keychain, no plaintext key left in `.env`. Gateway, connector (e2e 13/13 from a keystore), preflight, `check_funds` and `create_wallets` all load them. `.env.mainnet` (real-money wallets) is not migrated yet: run `python scripts/encrypt_keys.py --env-file .env.mainnet --apply --rewrite-env`. Every teammate should run the script on their own machine. Production target: a KMS or CDP server wallet (brief item 9). |

### 3.3 Per-buyer watermark and leak tracing

| | |
|---|---|
| What | Every delivered text carries two marks. A visible license line: "Licensed to <payer> under <license>, offer <id>, receipt id <id>". An invisible copy of the receipt id, written in zero-width characters after the first sentence and at the end, so it survives when someone deletes the license line. |
| Id | HMAC-SHA256 of (offer, payer) with `WATERMARK_SECRET` (defaults to `JWT_SECRET`), 48 bits. Nobody can forge another buyer's mark to frame them. Re-delivery (recovery, `/receipt`) carries the same marks. |
| Trace | `POST /compliance/trace {text}` (owner) returns the sale, payer and transaction behind a leaked text. Tested live. |
| Connector | `buyer-mcp/server.py` still removes control characters, bidi overrides and Unicode tag characters (hidden "ASCII smuggling" injections), but keeps the zero-width marks. |
| Code | `payments/watermark.py`, `payments/router.py`, `gateway/routers/compliance.py`. |
| Tests | `test_watermark_traces_a_leak_back_to_its_sale`, `test_watermark_cannot_be_forged_without_the_secret`. |
| Limits | It is a deterrent and evidence, not DRM: normalising the text removes the invisible mark, and rewording removes both. |

### 3.4 Hygiene

| Item | State |
|---|---|
| Python dependencies | `pip-audit` on the 140 installed packages: **no known vulnerability** (18 Oct). |
| npm dependencies | `npm audit --omit=dev`: 25 alerts (23 moderate, 2 high), all transitive in WalletConnect / Reown (`ws`, `viem` copies). The fix is a breaking wagmi upgrade, so it is **deferred until after the hackathon**. Exposure is low: client-side wallet libraries in a local demo. |
| Gateway headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'` on API responses (not on `/docs`), `Cache-Control: no-store` on paid content, sessions, events and compliance, HSTS over HTTPS. Test: `test_security_headers_on_gateway_responses`. |
| Frontend headers | `next.config.ts`: no framing (`X-Frame-Options`, `frame-ancestors 'none'`, protects the wallet and approval buttons from clickjacking), `nosniff`, `Referrer-Policy`, `Permissions-Policy`. There is no strict script CSP, because wagmi and MetaMask need inline scripts in dev. |
| CORS | Origins from `CORS_ORIGINS` (default `http://localhost:3000`). Methods and headers are now listed explicitly instead of `*`. |
| Owner tokens | Rotation: the variable can hold `new,old`. Expiry: `<VAR>_EXPIRES_AT`. Each token is compared in constant time with no early exit. The loopback check also accepts `::ffff:127.0.0.1` (dual-stack). Tests in `gateway/tests/test_publisher_auth.py`. |

---

## 4. Earlier security work (for completeness)

These are already documented in [SECURITY_P3.md](../payments/docs/SECURITY_P3.md) §2:
- **Payments:** price rebuilt server side; payer must be the KYA wallet; replay blocked by UNIQUE nonce and offer; settle before delivery; stuck payments recovered from the chain; rate limit.
- **Buyer:** budget, per-payment cap and approval threshold in code; every field of the 402 checked before signing; seller text treated as untrusted.
- **Review of 18 Oct:**
  - publisher setup routes are owner-only;
  - tier floor;
  - daily limit counted per wallet and re-checked at accept;
  - scan blocked from reaching private addresses (SSRF);
  - connector approval order;
  - balance read on-chain;
  - KYA binding checked before the blocklist;
  - prompt tag escaping;
  - Unicode normalisation in the leak filter;
  - short `JWT_SECRET` warning.

---

## 5. Where to see each control (demo or docs screenshots)

| Control | How to show it |
|---|---|
| Sanctions | Live view, any visit: "Sanctions check passed · OFAC list · Chainalysis oracle". To show a refusal: put a wallet in `KYA_BLOCKLIST` and run an agent with it, which gives "Sanctioned wallet refused". |
| Audit chain | `curl localhost:8000/compliance/audit-chain` shows `ok: true`. Edit one row of `events` in SQLite, run it again, and the problem is listed with its event id. |
| License receipt | Live view: "Signed license receipt · Receipt <id> · signed", then the buyer's "Receipt checked by the agent". `POST /compliance/verify-receipt` with that receipt. |
| Watermark | Copy the delivered text, delete the license line, send it to `POST /compliance/trace`, and it returns the sale and its basescan link. |
| Signed manifest | `curl /.well-known/ai-data.json` shows `signer` and `signature`. `curl /compliance/signer`. |
| Velocity and structuring | `BUYER_STRUCTURING_COUNT=1` with an offer between 0.80 and 1.00 USDC shows "Split purchases detected", and a human must approve. |
| Retention | `POST /compliance/purge {"days": 0}` shows "Personal data erased" in the live view, and the audit chain still verifies. |
| Full report | `GET /compliance/report`: one JSON page with chain state, sanctions setup, signer, retention and counters. |

---

## 6. Endpoints, settings, events

**Endpoints** (`gateway/routers/compliance.py`):

| Route | Access | Purpose |
|---|---|---|
| `GET /compliance/audit-head` | public | latest chain hash |
| `GET /compliance/audit-chain` | owner | full verification |
| `GET /compliance/signer` | public | publisher signing address and signature scheme |
| `POST /compliance/verify-receipt` | public | checks a license receipt |
| `GET /compliance/screen/{address}` | owner | sanctions check on demand |
| `POST /compliance/trace` | owner | finds the sale behind a leaked text |
| `POST /compliance/purge` | owner | runs the retention purge |
| `POST /compliance/erase` | owner | erasure request for one wallet |
| `GET /compliance/report` | owner | auditor summary |

**Settings:** see the "Compliance" and "Buyer velocity" blocks of `.env.example`.

**New event types** (`shared/events.py`, labels in `frontend/src/lib/eventLabels.ts`):
- gateway: `sanctions_screened`, `sanctions_blocked`, `license_receipt_issued`, `personal_data_purged`;
- buyer: `sanctions_screened`, `sanctions_blocked`, `velocity_limit_hit`, `structuring_suspected`, `manifest_signature_checked`, `manifest_signature_failed`, `receipt_verified`.

---

## 7. Open items and honest limits

| # | Item | Owner |
|---|---|---|
| 1 | The demo site serves its paid PDFs as public files on Vercel: anyone can download what agents pay for. Move them out of `public/` and redeploy. | P1 |
| 2 | Keys are encrypted on P3's machine (`.env`). `.env.mainnet` and the teammates' machines still need `scripts/encrypt_keys.py --apply --rewrite-env`. | team, on each machine |
| 3 | Sanctions: OFAC only, through a free oracle. No EU, UN or UK lists, no risk scoring of counterparties (mixers, scams). | post-hackathon |
| 4 | Travel rule (FATF R.16): not applied. Payments are far below the USD/EUR 1,000 threshold, and the parties are an agent and a merchant, not two VASPs. To revisit if Doubloon custodies funds. | post-hackathon |
| 5 | Manifest trust is trust on first use (see 3.1). | post-hackathon |
| 6 | npm alerts in the WalletConnect dependencies (see 3.4). | after the wagmi upgrade |
| 7 | Watermark: a deterrent, not DRM (see 3.3). | accepted |
| 8 | The audit chain lives in the same database it protects: tampering is detectable, not prevented. Anchoring the head on-chain closes this. | script ready, needs gas |
