# Hyperliquid Perps, Funding & Liquidation Risk Monitor

> Keyless Hyperliquid perps monitor for Grok Bot ($29 SOL). Tracks liquidation distance, margin utilisation, stop-loss coverage and funding drag with alerts.

- SKU: `hyperliquid-monitor`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/hyperliquid-monitor.html
- Markdown: https://coinloader.com/bots/hyperliquid-monitor.md

## When to use

Use when an agent needs liquidation distance, stop coverage and funding checks for Hyperliquid perps.

Inputs: a public account address

Outputs: position risk report, funding APR, mark-oracle basis, alerts

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "hyperliquid-monitor", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Hyperliquid Perps, Funding & Liquidation Risk Monitor — Know how far every perp is from liquidation before the market decides for you.

Monitor any Hyperliquid wallet or subaccount you own using only its public `0x` address: exact liquidation distance per position, cross and isolated margin utilisation, effective leverage, missing reduceOnly stop-losses, and the funding you are bleeding per day. Scan all 179+ perp markets for extreme funding APR, mark-oracle basis dislocation and Hyperliquid vs Binance / Bybit predicted funding spreads, inspect HLP and its child sub-vaults position by position, and run it as a stateful routine that alerts only when something changed.

 SKU: `hyperliquid-monitor` · Skills: `hyperliquid-monitor-setup + hyperliquid-monitor` · Tested: 1,312 lines stdlib Python, 252 unit tests · Category: Perps & DeFi / Risk Monitoring

## What It Does

- **Wallet & subaccount liquidation distance + TP/SL hygiene** (`clearinghouseState`, `spotClearinghouseState`, `frontendOpenOrders`): per-position mark vs liquidation price in % and $, with `LIQ_DISTANCE_CRITICAL` / `HIGH` / `MEDIUM` (defaults 5% / 10% / 20%), cross or isolated `MARGIN_UTIL_*`, `HIGH_EFFECTIVE_LEVERAGE`, `SINGLE_POSITION_CONCENTRATION`, `UNPROTECTED_POSITION_NO_SL` when no reduceOnly stop trigger covers the position, and `NON_REDUCE_ONLY_STOP` when a closing-side trigger could flip it. `ADVERSE_FUNDING_BLEED` estimates the $/day carry you pay.
- **Market-wide funding APR & cross-venue arbitrage scanner** (`metaAndAssetCtxs`, `predictedFundings`): mark, oracle, 1h / 8h funding, APR, basis and mid bps, open interest, 24h volume and vol/OI for every live perp, a funding-extremes table (OI ≥ $1M), and Hyperliquid vs **Binance** / **Bybit** predicted funding annualised per venue interval. Flags `MARKET_EXTREME_FUNDING`, `MARKET_BASIS_DISLOCATION` and `CROSS_VENUE_FUNDING_DIVERGENCE` (≥ 50% APR spread or a sign flip).
- **HLP & child sub-vault posture inspection** (`vaultDetails`): APR, TVL across the vault and its 7 child sub-vaults, total notional, `maxDistributable` / `maxWithdrawable`, leader fraction and commission, month and all-time peak-to-current drawdown, a per-account margin table and the top positions by notional across **354+ open positions**, each with liquidation distance and funding paid. `VAULT_CLOSED_OR_DEPOSITS_DISABLED` and `VAULT_LOW_LEADER_SKIN` for any vault.
- **Stateful delta routine monitoring** (`--state PATH --delta`): `LIQ_DISTANCE_TIGHTENED`, `MARGIN_UTIL_SPIKE`, `POSITION_OPENED` / `CLOSED` / `FLIPPED` / `SIZE_CHANGED`, `FUNDING_REGIME_SHIFT` and `BASIS_DISLOCATED` events between runs, ready for an hourly Grok Bot `UpdateRoutine`. The first run is a baseline; degraded runs never overwrite state. 1,312 lines stdlib Python, 252 passing unit tests.

## What It Does Not Do

- Strictly read-only, keyless and non-custodial: the only network call is the public, unauthenticated `POST https://api.hyperliquid.xyz/info`. It never calls `/exchange`, never places, cancels or modifies orders, never sets TP/SL or leverage, and never signs or broadcasts orders, withdrawals or transfers.
- Never accepts private keys, Hyperliquid API wallet (agent) keys, seed phrases, WIF / `xprv` or API tokens: such input (or flags like `--private-key`, `--api-wallet`, `--sign`, `--order`) is refused with exit `10` and never stored or echoed.
- Liquidation prices are point-in-time clearinghouse estimates that shift with mark price, funding and cross-margin PnL; funding, basis and predicted cross-venue rates change every hour. “No findings” never means “safe”.
- Refuses to target third-party accounts for liquidation hunting or exploitation. Not financial, trading, leverage or investment advice.

## Licensing & Setup

One-time $29 license paid in SOL, up to 3 workspace-reset rebinds. On Turn 1 the `hyperliquid-monitor-setup` skill verifies and activates your workspace agent key, binds your `wcl_...` code through the read-only license helper (`POST /api/v1/agents/license/claim`), installs the SHA-256-pinned `bot_common.py` and `hyperliquid_monitor.py` runtime, runs a public market smoke test and offers an optional watchlist routine. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (`/runtime/hyperliquid_monitor.py`) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Hyperliquid Perps, Funding & Liquidation Risk Monitor

**How do I monitor my Hyperliquid perpetual liquidation price distance, isolated margin buffer, and hourly funding rate drag?**

Pass your public 0x wallet or subaccount address. For every position the monitor reports mark vs liquidation price in percent and dollars (LIQ_DISTANCE_CRITICAL / HIGH / MEDIUM at 5% / 10% / 20% by default), cross or isolated margin utilisation, effective leverage, and ADVERSE_FUNDING_BLEED, the estimated dollars per day you pay in funding. The market scan also lists 1h and 8h funding and APR for every live perp.

**How does the monitor audit Hyperliquid sub-accounts, HLP vaults, and mark-oracle basis bps?**

Sub-accounts are audited by passing each subaccount's 0x address with --wallet (repeatable), and the monitor can also expand HLP and its child sub-vaults. Alongside position liquidation distance, it calculates live mark-oracle basis spreads in bps and flags BASIS_DISLOCATED when perpetual mark prices diverge sharply from oracle spot.

**How do scheduled delta alerts work for Hyperliquid liquidation and funding rate spikes?**

Run it as a routine with --state PATH --delta. The first run saves a snapshot and later runs print only what changed: LIQ_DISTANCE_TIGHTENED, MARGIN_UTIL_SPIKE, POSITION_OPENED / CLOSED / FLIPPED / SIZE_CHANGED, FUNDING_REGIME_SHIFT and BASIS_DISLOCATED. Exit codes 0 / 1 / 2 / 3 map to clean / MEDIUM / HIGH / CRITICAL, so a quiet run stays quiet.

**Does the Hyperliquid Perps Monitor require API keys, private keys, or trading permissions?**

No. It is keyless and read-only: the only network call is the public, unauthenticated POST https://api.hyperliquid.xyz/info. It never calls /exchange, never places, cancels or modifies orders, and refuses private keys, API wallet keys, seed phrases and flags such as --private-key or --order with exit code 10. Liquidation prices are point-in-time estimates, not trading advice.
