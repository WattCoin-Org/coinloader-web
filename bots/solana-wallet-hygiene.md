# Solana Wallet Hygiene Bot — Rent Reclaim

> Non-custodial Solana rent reclaim & token delegate revoke bot for Grok ($19 SOL). Close empty SPL & Token-2022 accounts (0.00203928 SOL each), no keys shared.

- SKU: `solana-wallet-hygiene`
- Price: $19 USD (one-time)
- Page: https://coinloader.com/bots/solana-wallet-hygiene.html
- Markdown: https://coinloader.com/bots/solana-wallet-hygiene.md

## When to use

Use when an agent needs to find reclaimable rent and stale delegations on a Solana wallet.

Inputs: a public wallet address

Outputs: SAFE_TO_RECLAIM / NEEDS_CONFIRMATION / DO_NOT_TOUCH report with exact rent and CLI commands

## How an agent buys

- Price: $19 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "solana-wallet-hygiene", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Solana Wallet Hygiene Bot — Non-Custodial SOL Rent Reclaim & Stale Delegate Auditor

Find the SOL rent locked in your empty SPL & Token-2022 token accounts (0.00203928 SOL / 2,039,280 lamports per standard empty SPL account) and the stale third-party token delegations still attached to your wallet—then reclaim and revoke them yourself, 100% non-custodially.

 SKU: `solana-wallet-hygiene` · Skills: `wallet-hygiene-setup + solana-wallet-hygiene` · Registry Name: *Solana Wallet Hygiene & Rent Reclaim*

## Architecture, Data Sources & Execution Capabilities

- Dual Token Program RPC Scan: Queries getParsedTokenAccountsByOwner across both Legacy SPL Token (TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA) and SPL Token-2022 (TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb) using only your public Base58 wallet address.
- Deterministic 3-Bucket Classification: Strictly separates every token account into SAFE_TO_RECLAIM (zero balance, no delegate, not frozen, no unharvested Token-2022 fees), NEEDS_CONFIRMATION (active third-party delegate or non-zero dust), and DO_NOT_TOUCH (active balances, LP receipts, NFTs, frozen accounts).
- Exact Lamport & SOL Accounting: Calculates exact reclaimable rent (2,039,280 lamports / 0.00203928 SOL per standard 165-byte SPL token account, plus exact lamports for extended Token-2022 accounts).
- Non-Custodial Reclaim & Revoke Commands: Generates copy-pasteable spl-token close and spl-token revoke CLI commands (including --program-id TokenzQd... for Token-2022) and step-by-step Phantom / Solflare UI instructions so you sign every transaction in your own wallet.

## What This Bot Does Not Do (Mandatory Refusal Boundaries)

- Never asks for seed phrases, recovery words, private keys, or keypair JSON files—and immediately halts and refuses if a user pastes secret key material.
- Never signs, submits, or broadcasts transactions on your behalf and never charges a percentage cut of your reclaimed SOL rent.
- Never recommends closing accounts with non-zero balances, frozen states, or unharvested Token-2022 transfer fees.

## Turn-1 `/workspace` Onboarding & Non-Custodial Licensing

 Every template on CoinLoader.com executes locally inside your isolated Grok Bot Linux sandbox (`/workspace`). Credentials are stored in `/workspace/.wattcoin_env` with `0600` permissions (`-rw-------`) and never echoed in chat. Paid licenses are settled once on-chain in SOL via `POST https://www.wattcoin.org/api/v1/agents/license/quote` and `/purchase`, issue a private `wcl_...` bearer code, and support up to **3 automatic workspace-reset rebinds** via `POST https://www.wattcoin.org/api/v1/agents/license/claim`.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Solana Wallet Hygiene Bot

**How much SOL rent is locked in each empty Solana token account?**

Each standard 165-byte SPL token account holds exactly 0.00203928 SOL (2,039,280 lamports) of rent-exempt reserve. Token-2022 accounts with extensions hold slightly more depending on account byte length, and the bot reports the exact lamport balance for every account.

**Does the Solana Wallet Hygiene Bot take a percentage fee of my reclaimed SOL?**

Zero percent. Unlike web-based rent reclaim dApps that ask you to connect your wallet and take a 10%–25% cut of your reclaimed rent, Solana Wallet Hygiene Bot is a one-time $19 SOL license that runs read-only in /workspace and gives you the exact spl-token CLI and wallet UI steps to reclaim 100% of your SOL yourself.

**Does it ever need my private key or wallet connection?**

Never. You only provide a public Base58 wallet address. The bot performs a read-only Solana RPC inspection and never touches private keys or wallet popups.
