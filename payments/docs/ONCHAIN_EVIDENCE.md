# On-chain evidence (Base Sepolia)

Every payment below is a real `transferWithAuthorization` (EIP-3009) of test USDC on Base Sepolia (`eip155:84532`),
submitted by the x402 facilitator after our gateway verified the payment, and before any content was delivered.
The list is read directly from the chain (USDC `Transfer` logs to the publisher wallet), not from our database.

- USDC contract: [`0x036CbD53842c5426634e7929541eC2318f3dCF7e`](https://sepolia.basescan.org/token/0x036CbD53842c5426634e7929541eC2318f3dCF7e)
- Publisher wallet (payTo): [`0x797486c95c00d40F30E41996b0DA5417fF256844`](https://sepolia.basescan.org/address/0x797486c95c00d40F30E41996b0DA5417fF256844)
- Total: **25 payments, 15.71 USDC**, all on 2026-10-17/18 (UTC)

## Key transactions

| Scenario | Amount | Tx |
|---|---|---|
| First x402 payment (spike, one route at 0.01 USDC) | 0.01 USDC | [0xa1ca62f97b…](https://sepolia.basescan.org/tx/0xa1ca62f97bca90ec70f63d9ea486aa060ae5bf02bcccc88b981b65ef6c89a3dd) |
| P3 standalone: buyer agent buys one figure | 0.10 USDC | [0x4e96b4040a…](https://sepolia.basescan.org/tx/0x4e96b4040a7310610a4a1989f9a4221dca95f598d8f52b51120d218e683e9f46) |
| P3 standalone: full section, paid after human approval | 2.00 USDC | [0x4846326351…](https://sepolia.basescan.org/tx/0x4846326351d3fa333d26886dba899310011dbed258a19df1664b9b9df3dcf399) |
| Buyer agent with LLM decision: one figure | 0.10 USDC | [0xcde68fac69…](https://sepolia.basescan.org/tx/0xcde68fac69f17fad670d5f8e7a8b0f86fe4d3df2478f6e66e1364af3b6dbc56e) |
| Buyer agent with LLM decision: full section after approval | 2.00 USDC | [0xd40eb78d47…](https://sepolia.basescan.org/tx/0xd40eb78d477eac52fdd8fd17cc9d238a5b1de3eb899e525b1cec3e760e8991dc) |
| On P2's real gateway and Sales agent: one figure | 0.10 USDC | [0x2185e54ad0…](https://sepolia.basescan.org/tx/0x2185e54ad0a5644acf94fd04b8142595eccabae6055fd9a3fb64052486bb2a6f) |
| On P2's real gateway and Sales agent: full section after approval | 2.00 USDC | [0x8a6aaff8c3…](https://sepolia.basescan.org/tx/0x8a6aaff8c3255108dee5cdcf8bafa22282bd778307013fbb8fccb6b04e554401) |
| P1 + P2 + P3 with P1's real catalog: one figure | 0.10 USDC | [0x010654b9f1…](https://sepolia.basescan.org/tx/0x010654b9f196a7edf5fb382f3b840a8e1bf2b749756f811f8e2a132eaab830c4) |
| P1 + P2 + P3 with P1's real catalog: full section after approval | 2.00 USDC | [0xb59df8f649…](https://sepolia.basescan.org/tx/0xb59df8f6496f54d360c487d052cc10fa888a9cb6b97664d1fe2a8552050d80ea) |

## All payments to the publisher

| Time (UTC) | Block | Payer | Amount | Context | Tx |
|---|---|---|---|---|---|
| 10-17 23:29 | 48255731 | BUYER_1 | 0.01 | spike | [0xa1ca62f97b…](https://sepolia.basescan.org/tx/0xa1ca62f97bca90ec70f63d9ea486aa060ae5bf02bcccc88b981b65ef6c89a3dd) |
| 10-17 23:32 | 48255828 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xcc8e40526f…](https://sepolia.basescan.org/tx/0xcc8e40526fdebc5d79cc8ef6a4f5cc26691094056ee042067957295995f3327d) |
| 10-17 23:37 | 48255987 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0x16cf843078…](https://sepolia.basescan.org/tx/0x16cf8430780d61034e3198301d755c460eb05e0a9b75f576da654446c49635cb) |
| 10-17 23:38 | 48256014 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0x343c594751…](https://sepolia.basescan.org/tx/0x343c594751c0f4bdb46f8fb60405151b2169405a7e087d71c5fdc485f3147b98) |
| 10-17 23:38 | 48256014 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0x4e96b4040a…](https://sepolia.basescan.org/tx/0x4e96b4040a7310610a4a1989f9a4221dca95f598d8f52b51120d218e683e9f46) |
| 10-17 23:38 | 48256015 | BUYER_1 | 2.00 | P3 standalone (mocked P2) | [0x4846326351…](https://sepolia.basescan.org/tx/0x4846326351d3fa333d26886dba899310011dbed258a19df1664b9b9df3dcf399) |
| 10-17 23:42 | 48256119 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0x0b55d0fbbd…](https://sepolia.basescan.org/tx/0x0b55d0fbbd21579dd2e8251add765a6285dfe2a77d25121406820883fdda62cf) |
| 10-17 23:42 | 48256127 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xe38e592f89…](https://sepolia.basescan.org/tx/0xe38e592f890fd0b8b60b0de53083e880079b272f5599bda9874a969e1d1a6b37) |
| 10-17 23:50 | 48256370 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xcde68fac69…](https://sepolia.basescan.org/tx/0xcde68fac69f17fad670d5f8e7a8b0f86fe4d3df2478f6e66e1364af3b6dbc56e) |
| 10-17 23:50 | 48256372 | BUYER_1 | 2.00 | P3 standalone (mocked P2) | [0xd40eb78d47…](https://sepolia.basescan.org/tx/0xd40eb78d477eac52fdd8fd17cc9d238a5b1de3eb899e525b1cec3e760e8991dc) |
| 10-18 00:01 | 48256693 | BUYER_1 | 0.10 | P2 gateway integration | [0x253a923c0c…](https://sepolia.basescan.org/tx/0x253a923c0c3af0bc9a8723d55fa62368a165d7a924231b8aac3d5c25fb94087a) |
| 10-18 00:01 | 48256703 | BUYER_1 | 2.00 | P2 gateway integration | [0x148de42152…](https://sepolia.basescan.org/tx/0x148de421521a12ffc5f2507fe41eaac0a0a15f3a06a85a9ddf2beb17ccf2df77) |
| 10-18 00:03 | 48256747 | BUYER_1 | 0.10 | P2 gateway integration | [0x2185e54ad0…](https://sepolia.basescan.org/tx/0x2185e54ad0a5644acf94fd04b8142595eccabae6055fd9a3fb64052486bb2a6f) |
| 10-18 00:03 | 48256752 | BUYER_2 | 2.00 | P2 gateway integration | [0x8a6aaff8c3…](https://sepolia.basescan.org/tx/0x8a6aaff8c3255108dee5cdcf8bafa22282bd778307013fbb8fccb6b04e554401) |
| 10-18 00:03 | 48256764 | BUYER_2 | 0.10 | P2 gateway integration | [0xf670b64b6a…](https://sepolia.basescan.org/tx/0xf670b64b6abaa6bdb207c03f4b05a0855bc290511307b87c2b0f460091fb7f51) |
| 10-18 00:04 | 48256778 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xaba4e932ed…](https://sepolia.basescan.org/tx/0xaba4e932edffea470997569ec92cdf399ead68deace835d5853b66cde877ce29) |
| 10-18 00:13 | 48257049 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xd535df3e46…](https://sepolia.basescan.org/tx/0xd535df3e464c81917e28149aa16d2abbccd584f37f576feae3dde0269736bc16) |
| 10-18 00:13 | 48257053 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xd031d0b6c0…](https://sepolia.basescan.org/tx/0xd031d0b6c006a9b4004dbb5b3d9f843a31cdbcad7b3aeced11493fa1c4411f26) |
| 10-18 00:14 | 48257083 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0xaa9484ee4e…](https://sepolia.basescan.org/tx/0xaa9484ee4e77ca3d57d3c33084b9982f54e8aebe8c6e36c5b845c1e2b9308db1) |
| 10-18 00:14 | 48257085 | BUYER_2 | 2.00 | P3 standalone (mocked P2) | [0xfddab60e48…](https://sepolia.basescan.org/tx/0xfddab60e4869f7de79ebd1f0a2d814330fc70d0d4b7870ab546ed29527a2dc69) |
| 10-18 00:16 | 48257142 | BUYER_1 | 0.10 | P1+P2+P3 integration | [0x010654b9f1…](https://sepolia.basescan.org/tx/0x010654b9f196a7edf5fb382f3b840a8e1bf2b749756f811f8e2a132eaab830c4) |
| 10-18 00:16 | 48257146 | BUYER_2 | 2.00 | P1+P2+P3 integration | [0xb59df8f649…](https://sepolia.basescan.org/tx/0xb59df8f6496f54d360c487d052cc10fa888a9cb6b97664d1fe2a8552050d80ea) |
| 10-18 00:16 | 48257158 | BUYER_2 | 0.10 | P1+P2+P3 integration | [0x19b127c498…](https://sepolia.basescan.org/tx/0x19b127c498238247cc09aacbdd7f6f6079fbf06a9a3cc1b980788d0d9fc4e13f) |
| 10-18 00:21 | 48257288 | BUYER_1 | 0.10 | P3 standalone (mocked P2) | [0x2d13583ea8…](https://sepolia.basescan.org/tx/0x2d13583ea8023a21181886119378228541752c295d6556ae903eb60982f13378) |
| 10-18 00:21 | 48257290 | BUYER_2 | 2.00 | P3 standalone (mocked P2) | [0xf6d3d2e759…](https://sepolia.basescan.org/tx/0xf6d3d2e7593fe841c5138580c299c6ee01e868377e959593e3e6720944479938) |

Buyer wallets: BUYER_1 `0xe7f91fc3a65ae959944570de56201920d2bdcba1`, BUYER_2 `0x2c63a1c827ca4a4df34e034270904c4bbb012151`, BUYER_3 `0x563ec68802b450691cda28638a280834e5742f7e`, BUYER_4 `0xefb5cbb9c658774bf1e4b9f9cfb77466bee2b671`

Regenerate: `payments/docs/ONCHAIN_EVIDENCE.md` is built from `eth_getLogs` on the USDC contract (topic `Transfer`, `to` = publisher).
