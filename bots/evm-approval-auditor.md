# EVM Wallet Approval & Permit2 Risk Auditor

> Read-only EVM approval auditor for Grok Bot ($19 SOL). Finds unlimited ERC-20 and Permit2 allowances on Ethereum, Base & Arbitrum and prints revoke call-data.

- SKU: `evm-approval-auditor`
- Price: $19 USD (one-time)
- Page: https://coinloader.com/bots/evm-approval-auditor.html
- Markdown: https://coinloader.com/bots/evm-approval-auditor.md

## When to use

Use when an agent needs to list risky token approvals and Permit2 allowances for a wallet.

Inputs: a wallet address on Ethereum, Base or Arbitrum

Outputs: spenders classified by risk with revoke call-data you submit yourself

## How an agent buys

- Price: $19 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "evm-approval-auditor", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# EVM Wallet Approval & Permit2 Risk Auditor — Find the unlimited approvals that can still pull your tokens.

Audit any Ethereum, Base, or Arbitrum wallet you own: read the live ERC-20 `allowance()` and Permit2 sub-allowance for every curated and discovered token/spender pair, see the balance actually at risk behind each one, classify the spender (EOA, unverified contract, unlabeled contract, or curated protocol), and get exact `approve(spender, 0)` revoke and Permit2 `lockdown` call-data to sign in your own wallet.

 SKU: `evm-approval-auditor` · Skills: `evm-approval-auditor-setup + evm-approval-auditor` · Tested: 1,181 lines stdlib Python, 87 unit tests

## What It Does

- Live allowance reads across **Ethereum (`eth`, 1)**, **Base (`base`, 8453)**, and **Arbitrum One (`arb`, 42161)**: ERC-20 `allowance(owner, spender)` plus Permit2 `allowance(owner, token, spender)` (amount, expiration, nonce) over curated stablecoins, WETH, WBTC and LSTs, Blockscout-discovered holdings, and bounded `eth_getLogs` Approval-event discovery (`--lookback-blocks`, default 20000).
- Spender classification with balance-at-risk per pair: `EOA_SPENDER` and unverified unlabeled contracts (`UNVERIFIED_SPENDER`) are CRITICAL, unlimited allowances to unlabeled verified contracts (`UNKNOWN_VERIFIED_SPENDER`) are HIGH, unlimited allowances to curated spenders (Uniswap Permit2 & routers, 1inch, CoW Protocol, 0x, ParaSwap, Morpho Blue, Aave V3) are MEDIUM, plus `PERMIT2_ACTIVE_SUBALLOWANCE` / `PERMIT2_EXPIRED_SUBALLOWANCE`.
- Non-custodial remediation call-data: exact `to` + `data` for `approve(spender, 0)` on each flagged token and a single batched Permit2 `lockdown((token, spender)[])` transaction, displayed for you to submit from your own wallet (Rabby, MetaMask, Safe, or hardware signer).
- Stateful delta monitor (`--state PATH --delta`): emits `NEW_APPROVAL`, `ALLOWANCE_INCREASED`, and `APPROVAL_REVOKED` events between runs, with `--json` output and exit codes 0 clean / 1 MEDIUM / 2 HIGH / 3 CRITICAL / 10 bad input / 11 degraded sources. 1,181 lines stdlib Python, 87 passing unit tests.

## What It Does Not Do

- Strictly read-only (`eth_blockNumber`, `eth_call`, `eth_getCode`, `eth_getStorageAt`, `eth_getLogs`): never asks for private keys or seed phrases, and never signs, builds for submission, or broadcasts a transaction.
- “No findings” never means “no approvals exist”: coverage is the stated tokens, spenders, and log window. NFT `setApprovalForAll` and unlisted tokens/spenders are outside v1 unless supplied with `--tokens` / `--spenders`.
- An unlabeled spender is unknown, not malicious; refuses to scan third-party wallets for exploitation, rank wallets by balance, or build phishing/drainer lists. Not financial, legal, or tax advice.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `evm-approval-auditor-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and installs the SHA-256-pinned `bot_common.py` and `evm_approval_auditor.py` runtime. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (`/runtime/evm_approval_auditor.py`) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — EVM Wallet Approval & Permit2 Risk Auditor

**How do I audit and revoke unlimited ERC-20 token approvals and Uniswap Permit2 sub-allowances to prevent wallet drainer risk?**

Give the auditor a wallet address you own. It reads live ERC-20 allowance(owner, spender) and Permit2 allowance(owner, token, spender) values (amount, expiration, nonce), shows the balance actually at risk behind each pair, and classifies each spender as EOA, unverified contract, unlabeled contract or curated protocol. For every flagged token it prints exact approve(spender, 0) revoke call-data and a batched Permit2 lockdown call that you review and submit yourself from your own wallet.

**Which EVM chains are supported for ERC-20 allowance and Permit2 expiration auditing?**

Ethereum (eth, chain 1), Base (base, 8453) and Arbitrum One (arb, 42161). Coverage is the curated stablecoins, WETH, WBTC and LSTs, Blockscout-discovered holdings and a bounded eth_getLogs Approval-event window (--lookback-blocks, default 20000). Permit2 sub-allowances are reported as active or expired using their expiration timestamps.

**How does the auditor inspect spender risk without connecting a wallet or signing transactions?**

It needs only your public 0x address. All calls are read-only (eth_blockNumber, eth_call, eth_getCode, eth_getStorageAt, eth_getLogs), and eth_getCode tells it whether a spender is an EOA or a contract. Unlimited allowances to EOAs or unverified contracts rank CRITICAL, unlabeled verified contracts HIGH and curated spenders MEDIUM. Remediation call-data is displayed for you, never signed or broadcast by the bot.

**What safety and refusal boundaries does the EVM Wallet Approval & Permit2 Risk Auditor enforce?**

It never asks for private keys or seed phrases and never signs or broadcasts a transaction. 'No findings' never means 'no approvals exist', since coverage is limited to the stated tokens, spenders and log window, and an unlabeled spender is unknown, not malicious. It refuses to scan third-party wallets for exploitation, rank wallets by balance or build phishing or drainer lists. It is not financial, legal or tax advice.
