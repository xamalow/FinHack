# Demo run sheet (3 minutes)

Follows agent.md section 2. No terminal on screen at any time.

## Before going on stage

- [ ] Gateway running, `NEXT_PUBLIC_GATEWAY_URL` set, no "mock data" badge in the nav.
- [ ] Simulated site deployed and reachable, its URL ready to paste.
- [ ] MetaMask unlocked on Base Sepolia, publisher account selected, USDC token added so the balance shows.
- [ ] Buyer wallet funded (at least 5 test USDC), check its balance in the live view.
- [ ] Tabs open in this order: simulated site, `/onboarding`, `/live`, `/dashboard`, MetaMask.
- [ ] Previous runs cleared (`Clear` in the live view).
- [ ] Backup video ready to play.

## 0:00 to 0:45, the publisher activates its site

1. Show the simulated research firm site.
2. `/onboarding`: paste the URL, **Scan site**. The progress follows the real scan events.
3. Catalog: set **Internal notes** to `excluded`. Say: "metadata only, no figure ever leaves".
4. **Generate tiers** from the rules text, show 0.10, 0.50, 2.00, **Confirm tiers**.
5. **Connect MetaMask**, then **Activate**. Show the manifest.
6. Back on the simulated site: it now says it sells data to AI agents.

## 0:45 to 2:00, an agent buys

1. `/live`, scenario **Small purchase, 0.10 USDC**, budget 5, **Run agent**.
2. Narrate the columns: KYA verified, Sales agent offer with no figure, 402, signature, facilitator verify and settle, tx hash.
3. Point at both balances moving. Click the hash, the Base Sepolia explorer opens.
4. Click a line (for example "Invoice sent") to show the raw 402 payload.

### Variant: a real person with their own Claude

Instead of the Run agent button, buy from Claude Desktop with the `finhack-buyer` connector (setup in [buyer-mcp/README.md](../buyer-mcp/README.md)). Put Claude Desktop and the live view side by side.

1. Type: "Use finhack-buyer to find the 2025 European market share of the leading battery manufacturer. One figure is enough. Tell me the price before buying."
2. Claude searches, proves its identity, gets an offer at 0.10 USDC and tells you the price. Say "go ahead".
3. The live view fills in real time, each buyer line tagged "Via the user's own AI assistant".
4. For the 2.00 sale, ask for "the full methodology section". The approval banner says it waits for the owner in their assistant: answer "yes" in Claude.

## 2:00 to 2:30, a more expensive sale

1. Scenario **Big purchase, 2.00 USDC**, **Run agent**.
2. The orange banner "The agent needs your approval" appears. Say: "above the 1.00 threshold the agent asks its owner".
3. **Approve 2.00 USDC**, the payment goes through. "The price follows the request."

## 2:30 to 2:50, security

1. Scenario **Attack attempts**, **Run agent**.
2. Red lines: "Manipulation attempt blocked", and with the mocks "Reused payment blocked" (409) and "Agent refuses: too expensive".

## 2:50 to 3:00, the publisher gets paid

1. `/dashboard`: revenue, requests, transactions.
2. Click the 2.00 sale: agent identity, conversation, offer, hash.
3. Switch to MetaMask, the USDC is there.
4. Closing line: "Any website. Any AI agent. Any piece of information. One payment."

## If something breaks

- Gateway down: set `NEXT_PUBLIC_USE_MOCKS=true` and restart the frontend, the full scripted demo still plays (hashes are fake, do not click them).
- Anything worse: play the backup video.
