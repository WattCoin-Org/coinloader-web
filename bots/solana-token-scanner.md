# Retail Token Due-Diligence Bot — Solana SPL Scanner

> Solana SPL & Token-2022 due-diligence scanner for Grok Bot ($29 SOL). Audits mint/freeze authorities, extensions, top-20 holders and DEX liquidity.

- SKU: `solana-token-scanner`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/solana-token-scanner.html
- Markdown: https://coinloader.com/bots/solana-token-scanner.md

## When to use

Use when an agent needs verifiable on-chain facts about a Solana mint.

Inputs: a mint address

Outputs: 5-section report: authorities, Token-2022 extensions, top-20 holders, DEX liquidity, scope note

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "solana-token-scanner", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Retail Token Due-Diligence Bot — Verifiable Solana SPL & Token-2022 Mint Inspector

Get verifiable, timestamped on-chain facts for any Solana SPL or Token-2022 mint address—mechanics, not motives. Generates a 5-section report covering program identity, mint/freeze/update authorities, Token-2022 extension controls, top-20 holder concentration, and DexScreener liquidity.

 SKU: `solana-token-scanner` · Skills: `solana-token-scanner-setup + solana-token-scanner` · Registry Name: *Solana Token & Mint Due-Diligence Scanner*

## Architecture, Data Sources & Execution Capabilities

- Section 1 & Section 2 — Mint Authorities & Token-2022 Extension Controls: Inspects getAccountInfo and getTokenSupply to report whether mint authority and freeze authority are PRESENT (with exact address) or REVOKED (null), and parses Token-2022 extensions including PermanentDelegate, TransferFeeConfig (bps and max fee), TransferHook, MintCloseAuthority, and DefaultAccountState.
- Section 3 — Top-20 Holder Concentration (getTokenLargestAccounts): Calculates exact top-10 and top-20 holder supply percentages and separates known program/AMM pool vaults from individual wallet token accounts.
- Section 4 — DEX Liquidity & Pair Snapshot (DexScreener): Queries primary DEX pairs, USD liquidity depth, 24-hour volume, FDV, and pair creation timestamps with exact UTC retrieval timestamps.
- Section 5 — Mandatory Non-Advice Scope Note: Prepends and appends SCOPE_NOTE.txt stating what on-chain state shows at retrieval time and what it cannot see (off-chain conduct, future authority actions, or post-retrieval liquidity changes).

## What This Bot Does Not Do (Mandatory Refusal Boundaries)

- Mechanics, not motives: Never outputs 'safe', 'unsafe', 'legit', 'scam', or 'rug' verdicts, and never assigns a numerical safety score or letter grade.
- Never issues buy, sell, hold, or price-target investment advice.
- Every metric cites its exact Solana RPC method, slot/timestamp, or DexScreener endpoint.

## Turn-1 `/workspace` Onboarding & Non-Custodial Licensing

 Every template on CoinLoader.com executes locally inside your isolated Grok Bot Linux sandbox (`/workspace`). Credentials are stored in `/workspace/.wattcoin_env` with `0600` permissions (`-rw-------`) and never echoed in chat. Paid licenses are settled once on-chain in SOL via `POST https://www.wattcoin.org/api/v1/agents/license/quote` and `/purchase`, issue a private `wcl_...` bearer code, and support up to **3 automatic workspace-reset rebinds** via `POST https://www.wattcoin.org/api/v1/agents/license/claim`.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Retail Token Due-Diligence Bot

**Which Token-2022 extensions does the Retail Token Due-Diligence Bot detect?**

It inspects the mint account's parsed Token-2022 extension data for PermanentDelegate, TransferFeeConfig (fee basis points and maximum fee), TransferHook (custom program hook on every transfer), DefaultAccountState (e.g., Frozen by default), InterestBearingConfig, and MintCloseAuthority.

**Why doesn't the bot label a token 'Safe' or 'Rug'?**

A token with revoked mint and freeze authorities can still lose liquidity off-chain, and a token with an active authority may be a legitimate regulated asset. The bot reports exact, verifiable on-chain mechanics (authorities, extensions, holder concentration, DEX liquidity depth) so you see the raw facts without black-box scores.

**Does it work for both standard SPL (Tokenkeg) and Token-2022 (TokenzQd) mints?**

Yes. The read-only /workspace/.wattcoin_token_scan.py helper automatically detects the owner program (TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA or TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb) and parses all applicable fields.
