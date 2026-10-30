# Pump.fun Coin & Community Manager ($29 SOL) | CoinLoader

> Read-only Pump.fun launch auditor for Grok Bot ($29 SOL). Finds missing links, creator gaps and holder shifts, and drafts Callout replies you review and post.

- SKU: `pumpfun-coin-manager`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/pumpfun-coin-manager.html
- Markdown: https://coinloader.com/bots/pumpfun-coin-manager.md

## When to use

Use when an agent needs a read-only audit and change monitor for a Pump.fun coin.

Inputs: a mint address; optional expected website/Discord/X links

Outputs: audit findings, delta events, reply drafts for a human to post

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "pumpfun-coin-manager", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Pump.fun Coin & Community Manager — Know what holders see before they ask.

Audit your Pump.fun coin the way a skeptical holder would see it: which official links are missing from the immutable metadata, whether the creator profile and Callout tab point people to the right place, and whether DexScreener, GeckoTerminal and RugCheck agree. Then get copy-paste Callout, reply and bio drafts. Strictly read-only: no wallet, no keys, nothing is posted for you.

 SKU: `pumpfun-coin-manager` · Skills: `pumpfun-coin-manager-setup + pumpfun-coin-manager` · Tested: 48 KB helper, 23 unit tests

## What It Does

- 16-key delta monitor (`--state` + `--delta`): authority reinstated, metadata URI changed, supply increased, ban or hidden coin, new Callouts and replies, fee-sharing and creator-profile edits, large new holders, creator sells, liquidity drops, pair dormant/active, closed link gaps, new bot followers.
- Point-in-time audit: missing website/Discord/Telegram in IPFS metadata, creator bio vs `--expected-website`, `--expected-discord`, `--expected-x`, empty Callout tab, GeckoTerminal link gaps, dormant DexScreener pairs, RugCheck risks.
- IPFS metadata read through two hash-verified gateways; Token-2022 authorities and extensions read from public Solana RPC.
- `--draft-replies` emits a bio, creator anchor Callout, on-chain transparency Callout and per-Callout reply drafts. Exit codes 0/1/2/3 (clean/MEDIUM/HIGH/CRITICAL), 11 when data sources are degraded.

## What It Does Not Do

- Never posts, signs, or holds keys; every Callout, reply and bio is a draft for a human.
- Never suggests wash-trading to wake a dormant aggregator pair.
- Never DMs or tags underwater holders, and never makes price or return claims.
- Findings are heuristics with stated evidence, not verdicts.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `pumpfun-coin-manager-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and confirms the bot files are installed. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Pump.fun Coin & Community Manager

**How do I audit a Pump.fun token launch for bonding-curve graduation progress, creator supply concentration, and missing social links?**

Run the manager on the mint address. It reads Pump.fun and public Solana RPC data to report Token-2022 authorities and extensions, the creator's holdings share, top holders, and whether the coin trades on its bonding curve or a DEX pair (DexScreener, GeckoTerminal and RugCheck are cross-checked). It also lists missing website, Discord and Telegram links in the IPFS metadata and gaps between the creator bio and your --expected-website, --expected-discord and --expected-x values.

**How does scheduled delta monitoring track bonding-curve progress and top-holder shifts on Pump.fun?**

With --state PATH --delta the 16-key monitor compares each run to the last snapshot and reports only changes: authority reinstated, metadata URI changed, supply increased, large new holders, creator sells, liquidity drops, pair dormant or active, new Callouts and replies, and closed link gaps. Exit codes 0 / 1 / 2 / 3 map to clean / MEDIUM / HIGH / CRITICAL, and 11 means a data source was degraded.

**Can the Pump.fun Coin & Community Manager draft launch checklist items and community status updates?**

Yes. --draft-replies emits a creator bio, a creator anchor Callout, an on-chain transparency Callout and per-Callout reply drafts built from verified facts such as supply, authorities and your official links. Every draft is for a human to review and post; the bot never posts for you.

**What refusal boundaries does the Pump.fun Coin & Community Manager enforce (no volume bots, wash trading, or private keys)?**

It is strictly read-only: no wallet, no keys, no signing and nothing posted on your behalf. It never suggests wash trading to wake a dormant aggregator pair, never DMs or tags underwater holders, and never makes price or return claims. Findings are heuristics with stated evidence, not verdicts.
