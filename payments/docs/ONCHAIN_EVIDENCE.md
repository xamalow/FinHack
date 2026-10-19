# On-chain evidence (Base Sepolia)

Every payment below is a real `transferWithAuthorization` (EIP-3009) of test USDC on Base Sepolia (`eip155:84532`),
submitted by the x402 facilitator after our gateway verified the payment, and before any content was delivered.
The list is read directly from the chain (USDC `Transfer` logs to the publisher wallet), not from our database.

- USDC contract: [`0x036CbD53842c5426634e7929541eC2318f3dCF7e`](https://sepolia.basescan.org/token/0x036CbD53842c5426634e7929541eC2318f3dCF7e)
- Publisher wallets (payTo): [`0x797486c95c00d40F30E41996b0DA5417fF256844`](https://sepolia.basescan.org/address/0x797486c95c00d40F30E41996b0DA5417fF256844) (generated, until 18 Oct) and [`0xa82763beAdCD9052e6e1e9f348Bd5Cd4E57e07FE`](https://sepolia.basescan.org/address/0xa82763beAdCD9052e6e1e9f348Bd5Cd4E57e07FE) (the publisher's MetaMask, from 18 Oct)
- Total: **62 payments, 39.21 USDC**, from 2026-10-17 to 2026-10-19 (UTC), read at block 48330403

## Base mainnet (real USDC)

The same payment code runs on Base mainnet (`eip155:8453`) with native USDC
[`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`](https://basescan.org/token/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
and the PayAI facilitator (`https://facilitator.payai.network`, gas paid by the facilitator). Only configuration changes
(`scripts/mainnet.sh` exports `.env.mainnet`); dedicated mainnet wallets, funded with 5 USD of real USDC by card.

| Time (UTC) | Scenario | Amount | Payer | Payee | Tx |
|---|---|---|---|---|---|
| 10-18 20:41 | x402 paid route (`payments/spike_server.py`) | 0.01 USDC | `0xc551aB5B4f72faaC4927B2E2cf2b64dC70fc7372` | `0xAd5ed0c67d17E57b87ce8Beb1a06FDe9f5e77c82` | [0x695cf3bb3a…](https://basescan.org/tx/0x695cf3bb3a354d623890ba7f87d3809ca5a607e326f33905dca0b44723e0e250) |
| 10-18 20:45 | **Full product**: buyer agent (KYA, Sales agent, LLM decision, code guards) buys one figure through `/query/t010`, data delivered after settlement | 0.10 USDC | `0xc551aB5B4f72faaC4927B2E2cf2b64dC70fc7372` | `0xAd5ed0c67d17E57b87ce8Beb1a06FDe9f5e77c82` | [0xc70ea04371…](https://basescan.org/tx/0xc70ea043716023f1e76ef26dac5e27c814d51ae0ca541d797ee249c949d36f8f) |

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

| Time (UTC) | Block | Payer | Payee | Amount | Context | Tx |
|---|---|---|---|---|---|---|
| 10-17 23:29 | 48255731 | BUYER_1 | PUBLISHER (generated) | 0.01 | spike | [0xa1ca62f97b…](https://sepolia.basescan.org/tx/0xa1ca62f97bca90ec70f63d9ea486aa060ae5bf02bcccc88b981b65ef6c89a3dd) |
| 10-17 23:32 | 48255828 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xcc8e40526f…](https://sepolia.basescan.org/tx/0xcc8e40526fdebc5d79cc8ef6a4f5cc26691094056ee042067957295995f3327d) |
| 10-17 23:37 | 48255987 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0x16cf843078…](https://sepolia.basescan.org/tx/0x16cf8430780d61034e3198301d755c460eb05e0a9b75f576da654446c49635cb) |
| 10-17 23:38 | 48256014 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0x343c594751…](https://sepolia.basescan.org/tx/0x343c594751c0f4bdb46f8fb60405151b2169405a7e087d71c5fdc485f3147b98) |
| 10-17 23:38 | 48256014 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0x4e96b4040a…](https://sepolia.basescan.org/tx/0x4e96b4040a7310610a4a1989f9a4221dca95f598d8f52b51120d218e683e9f46) |
| 10-17 23:38 | 48256015 | BUYER_1 | PUBLISHER (generated) | 2.00 | P3 standalone (mocked P2) | [0x4846326351…](https://sepolia.basescan.org/tx/0x4846326351d3fa333d26886dba899310011dbed258a19df1664b9b9df3dcf399) |
| 10-17 23:42 | 48256119 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0x0b55d0fbbd…](https://sepolia.basescan.org/tx/0x0b55d0fbbd21579dd2e8251add765a6285dfe2a77d25121406820883fdda62cf) |
| 10-17 23:42 | 48256127 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xe38e592f89…](https://sepolia.basescan.org/tx/0xe38e592f890fd0b8b60b0de53083e880079b272f5599bda9874a969e1d1a6b37) |
| 10-17 23:50 | 48256370 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xcde68fac69…](https://sepolia.basescan.org/tx/0xcde68fac69f17fad670d5f8e7a8b0f86fe4d3df2478f6e66e1364af3b6dbc56e) |
| 10-17 23:50 | 48256372 | BUYER_1 | PUBLISHER (generated) | 2.00 | P3 standalone (mocked P2) | [0xd40eb78d47…](https://sepolia.basescan.org/tx/0xd40eb78d477eac52fdd8fd17cc9d238a5b1de3eb899e525b1cec3e760e8991dc) |
| 10-18 00:01 | 48256693 | BUYER_1 | PUBLISHER (generated) | 0.10 | P2 gateway integration | [0x253a923c0c…](https://sepolia.basescan.org/tx/0x253a923c0c3af0bc9a8723d55fa62368a165d7a924231b8aac3d5c25fb94087a) |
| 10-18 00:01 | 48256703 | BUYER_1 | PUBLISHER (generated) | 2.00 | P2 gateway integration | [0x148de42152…](https://sepolia.basescan.org/tx/0x148de421521a12ffc5f2507fe41eaac0a0a15f3a06a85a9ddf2beb17ccf2df77) |
| 10-18 00:03 | 48256747 | BUYER_1 | PUBLISHER (generated) | 0.10 | P2 gateway integration | [0x2185e54ad0…](https://sepolia.basescan.org/tx/0x2185e54ad0a5644acf94fd04b8142595eccabae6055fd9a3fb64052486bb2a6f) |
| 10-18 00:03 | 48256752 | BUYER_2 | PUBLISHER (generated) | 2.00 | P2 gateway integration | [0x8a6aaff8c3…](https://sepolia.basescan.org/tx/0x8a6aaff8c3255108dee5cdcf8bafa22282bd778307013fbb8fccb6b04e554401) |
| 10-18 00:03 | 48256764 | BUYER_2 | PUBLISHER (generated) | 0.10 | P2 gateway integration | [0xf670b64b6a…](https://sepolia.basescan.org/tx/0xf670b64b6abaa6bdb207c03f4b05a0855bc290511307b87c2b0f460091fb7f51) |
| 10-18 00:04 | 48256778 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xaba4e932ed…](https://sepolia.basescan.org/tx/0xaba4e932edffea470997569ec92cdf399ead68deace835d5853b66cde877ce29) |
| 10-18 00:13 | 48257049 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xd535df3e46…](https://sepolia.basescan.org/tx/0xd535df3e464c81917e28149aa16d2abbccd584f37f576feae3dde0269736bc16) |
| 10-18 00:13 | 48257053 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xd031d0b6c0…](https://sepolia.basescan.org/tx/0xd031d0b6c006a9b4004dbb5b3d9f843a31cdbcad7b3aeced11493fa1c4411f26) |
| 10-18 00:14 | 48257083 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0xaa9484ee4e…](https://sepolia.basescan.org/tx/0xaa9484ee4e77ca3d57d3c33084b9982f54e8aebe8c6e36c5b845c1e2b9308db1) |
| 10-18 00:14 | 48257085 | BUYER_2 | PUBLISHER (generated) | 2.00 | P3 standalone (mocked P2) | [0xfddab60e48…](https://sepolia.basescan.org/tx/0xfddab60e4869f7de79ebd1f0a2d814330fc70d0d4b7870ab546ed29527a2dc69) |
| 10-18 00:16 | 48257142 | BUYER_1 | PUBLISHER (generated) | 0.10 | P1+P2+P3 integration | [0x010654b9f1…](https://sepolia.basescan.org/tx/0x010654b9f196a7edf5fb382f3b840a8e1bf2b749756f811f8e2a132eaab830c4) |
| 10-18 00:16 | 48257146 | BUYER_2 | PUBLISHER (generated) | 2.00 | P1+P2+P3 integration | [0xb59df8f649…](https://sepolia.basescan.org/tx/0xb59df8f6496f54d360c487d052cc10fa888a9cb6b97664d1fe2a8552050d80ea) |
| 10-18 00:16 | 48257158 | BUYER_2 | PUBLISHER (generated) | 0.10 | P1+P2+P3 integration | [0x19b127c498…](https://sepolia.basescan.org/tx/0x19b127c498238247cc09aacbdd7f6f6079fbf06a9a3cc1b980788d0d9fc4e13f) |
| 10-18 00:21 | 48257288 | BUYER_1 | PUBLISHER (generated) | 0.10 | P3 standalone (mocked P2) | [0x2d13583ea8…](https://sepolia.basescan.org/tx/0x2d13583ea8023a21181886119378228541752c295d6556ae903eb60982f13378) |
| 10-18 00:21 | 48257290 | BUYER_2 | PUBLISHER (generated) | 2.00 | P3 standalone (mocked P2) | [0xf6d3d2e759…](https://sepolia.basescan.org/tx/0xf6d3d2e7593fe841c5138580c299c6ee01e868377e959593e3e6720944479938) |
| 10-18 00:26 | 48257445 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xc583136a78…](https://sepolia.basescan.org/tx/0xc583136a78c2e9627b5a1a4d3b1eea34b6d66e5b3ced827207552ee62a217a4f) |
| 10-18 00:26 | 48257447 | BUYER_2 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0xdbda2bbed4…](https://sepolia.basescan.org/tx/0xdbda2bbed44cbc3608a6397452872daf8e0803c9b456292d47512896c2b348f8) |
| 10-18 00:35 | 48257710 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xdf2f1df572…](https://sepolia.basescan.org/tx/0xdf2f1df57292023e6aed2aa758d21c1cacce786c188694979855724bb3551271) |
| 10-18 00:36 | 48257740 | BUYER_1 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0x5588c49116…](https://sepolia.basescan.org/tx/0x5588c49116c1f738b613a7840d1894bcfbd70f83af3c9596524e2c91786cdf20) |
| 10-18 00:37 | 48257771 | BUYER_2 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x8d3d8ceb8b…](https://sepolia.basescan.org/tx/0x8d3d8ceb8b9f18160196bc78ecb877f3068b54c4f648f343a1c7853a004e6fd6) |
| 10-18 00:37 | 48257780 | BUYER_2 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0xfec8fd30fe…](https://sepolia.basescan.org/tx/0xfec8fd30febefad4debde4fd76669d5e44429f1f17c162234a743916e307e75c) |
| 10-18 00:38 | 48257798 | BUYER_1 | PUBLISHER (generated) | 0.50 | Integration and demo runs | [0x6fc62a13d9…](https://sepolia.basescan.org/tx/0x6fc62a13d9713c69251a2bb9ec2ed3976a738331eb5176b4519edd719d332de5) |
| 10-18 00:54 | 48258299 | BUYER_3 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x0a9b5c53dd…](https://sepolia.basescan.org/tx/0x0a9b5c53dded742c4cc16a6fd6d67a4fb5dd026796458c778295bf01320f930a) |
| 10-18 00:59 | 48258451 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x29fc58f9b8…](https://sepolia.basescan.org/tx/0x29fc58f9b8ccd7687866858f5d747f8ff2facbdbcd1aef38bbbbb0991651fb50) |
| 10-18 01:01 | 48258499 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xf811ff9969…](https://sepolia.basescan.org/tx/0xf811ff996949be20168e6ace93186574e45358ecea00fb223c491f021061ffe8) |
| 10-18 01:02 | 48258526 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xd48e933285…](https://sepolia.basescan.org/tx/0xd48e9332853716b15286ec47fdba6402f30716fde712307a95e3b5fd5b558138) |
| 10-18 01:03 | 48258569 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xe627a69716…](https://sepolia.basescan.org/tx/0xe627a69716832025d7f19c79305c3e550b3d658cfdd48facf79a03649dca33b6) |
| 10-18 01:05 | 48258629 | BUYER_2 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0x7825ac6039…](https://sepolia.basescan.org/tx/0x7825ac603944cb40384f7e616617a03b3cf3741e1f6792726b6dc2b2c1327df2) |
| 10-18 02:48 | 48261710 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x986a14e0c3…](https://sepolia.basescan.org/tx/0x986a14e0c3ffaa23330db69f712b7209f4204c71bcb87193be137f55a9e18805) |
| 10-18 02:48 | 48261712 | BUYER_2 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0x316a111b58…](https://sepolia.basescan.org/tx/0x316a111b5871bd8cf02c8118b6e68eca6e350888de06b1240f3ce3e64f80c042) |
| 10-18 02:48 | 48261718 | BUYER_4 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xf3f6569ad3…](https://sepolia.basescan.org/tx/0xf3f6569ad3a4d2deac1b7e748072185b7cc3e950a4eb93cee42eeaa367265120) |
| 10-18 02:49 | 48261731 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x231ce217db…](https://sepolia.basescan.org/tx/0x231ce217db87877c66e2cfa73564d1541c5b2249c1d46a1bfb75b663534a9f55) |
| 10-18 20:45 | 48294007 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0x96aa119711…](https://sepolia.basescan.org/tx/0x96aa1197116092415b46ef496c9279b3b73365c92265d26b9de1d12f6f2985aa) |
| 10-18 20:50 | 48294182 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xd837c64a53…](https://sepolia.basescan.org/tx/0xd837c64a53c3ff303964d7e47b9c082b83a162e006188709fb82f8029ffbd929) |
| 10-18 20:50 | 48294185 | BUYER_1 | PUBLISHER (generated) | 2.00 | Integration and demo runs | [0x6bbd0fe074…](https://sepolia.basescan.org/tx/0x6bbd0fe0748d9a283859efb6b0d825831b87d554e3037a0e0b98753f3853aa66) |
| 10-18 20:51 | 48294209 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xfc25c594b2…](https://sepolia.basescan.org/tx/0xfc25c594b24606e4723a630472733d1caff4fac4e6ffb401408a194a34cb430a) |
| 10-18 21:10 | 48294776 | BUYER_1 | PUBLISHER (generated) | 0.10 | Integration and demo runs | [0xb6004ff1eb…](https://sepolia.basescan.org/tx/0xb6004ff1eb5d54ddbd2a671464cef1c4e5d9d7d50bd5038218f4a4301f166649) |
| 10-18 21:23 | 48295164 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x817af4497a…](https://sepolia.basescan.org/tx/0x817af4497aad8a081f06c7236db8513ab3bf529a6dd94f3cda020079fe40dbcc) |
| 10-18 21:49 | 48295946 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Test agent, live demo gateway | [0x80956c6398…](https://sepolia.basescan.org/tx/0x80956c6398725f6abcfcf923494d319db55f95ed18b5e15f8fdd520b7b3dfcc0) |
| 10-18 21:55 | 48296131 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0xe08541a606…](https://sepolia.basescan.org/tx/0xe08541a60658678c1e6b1c9cd944c8d5576878f918400ece75ac4fb20aa5d488) |
| 10-18 22:10 | 48296562 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0xd24aa8a3bc…](https://sepolia.basescan.org/tx/0xd24aa8a3bc3d4a432a34a28a21e14aad7c36234f7d4c9d0cfdc830ce0aa634f8) |
| 10-18 22:14 | 48296690 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x87ce7bf4e9…](https://sepolia.basescan.org/tx/0x87ce7bf4e962f27ccd08e4c0561e8a358a76d2e3a9bcdf8f5b70c8e0b14dc109) |
| 10-18 22:14 | 48296702 | BUYER_1 | PUBLISHER (MetaMask) | 2.00 | Claude connector (MCP), live demo gateway | [0x1898ff8cf3…](https://sepolia.basescan.org/tx/0x1898ff8cf3f05dd9dcaf57775a1dc0304b1b3242c838d3a32818d112a0200029) |
| 10-18 22:27 | 48297079 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0xe5291bbdb5…](https://sepolia.basescan.org/tx/0xe5291bbdb55c42f6e1550e7622c9443302eaeec6d52bdc16c373f832c3097057) |
| 10-18 22:36 | 48297339 | BUYER_1 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x7813567716…](https://sepolia.basescan.org/tx/0x7813567716718c451242a8673938c44051e1851429c73e70252100c30c5b7544) |
| 10-18 22:36 | 48297343 | BUYER_1 | PUBLISHER (MetaMask) | 2.00 | Claude connector (MCP), live demo gateway | [0xdf7f970c85…](https://sepolia.basescan.org/tx/0xdf7f970c8523ae565feb60afb66b1ef221e651bda941ae047da24e8486c76647) |
| 10-18 22:55 | 48297922 | BUYER_3 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x69bfd705c8…](https://sepolia.basescan.org/tx/0x69bfd705c86021e87ae5300f1c7ed7f4204a58dc1d8d00a39a3d9dbe8905f421) |
| 10-18 22:55 | 48297925 | BUYER_3 | PUBLISHER (MetaMask) | 2.00 | Claude connector (MCP), live demo gateway | [0x38849309b3…](https://sepolia.basescan.org/tx/0x38849309b36935ddd2d2132b7a66dd02ad2f6b7218ab3b5edf118fb179e2b844) |
| 10-18 23:00 | 48298082 | BUYER_3 | PUBLISHER (MetaMask) | 0.50 | Claude connector (MCP), live demo gateway | [0xf61f941138…](https://sepolia.basescan.org/tx/0xf61f94113837bba20df1bd068c38f0cfe3d3f0df5ebc8c0e4233524bf7fd8483) |
| 10-18 23:01 | 48298094 | BUYER_4 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x48b4cc08ca…](https://sepolia.basescan.org/tx/0x48b4cc08ca8bc1f1c170585dc75946e62b182a2a3128b08a263ac98d34f0662e) |
| 10-18 23:01 | 48298096 | BUYER_4 | PUBLISHER (MetaMask) | 2.00 | Claude connector (MCP), live demo gateway | [0x6bda96d41d…](https://sepolia.basescan.org/tx/0x6bda96d41d04897e8364ea2f14a1004a52eea6060278370594af3235cbfe8d2e) |
| 10-19 16:11 | 48328987 | BUYER_4 | PUBLISHER (MetaMask) | 0.10 | Claude connector (MCP), live demo gateway | [0x4c575209b8…](https://sepolia.basescan.org/tx/0x4c575209b8fef54dd751bf36c95485fbcc611bcc4c481563c619de472bccfeb0) |

Buyer wallets: BUYER_1 `0xe7f91fc3a65ae959944570de56201920d2bdcba1`, BUYER_2 `0x2c63a1c827ca4a4df34e034270904c4bbb012151`, BUYER_3 `0x563ec68802b450691cda28638a280834e5742f7e`, BUYER_4 `0xefb5cbb9c658774bf1e4b9f9cfb77466bee2b671`

Regenerate: `.venv/bin/python scripts/onchain_evidence.py --write` (`eth_getLogs` on the USDC contract, topic `Transfer`, `to` = a publisher wallet, `from` = one of our buyer wallets).
