# CoinLoader — Crypto Agent Templates for Grok Bot

> 12 Grok Bot crypto-agent templates: Solana rent reclaim, rug-pull and honeypot scans, EVM Permit2 audits, Bitcoin UTXO hygiene, Hyperliquid and Pump.fun tools.

- Page: https://coinloader.com/
- Markdown: https://coinloader.com/index.md

## Catalog

- [Web & API Text Extractor](https://coinloader.com/bots/web-text-extractor.md) — Free — `web-extractor` — Use when an agent needs readable text from a public web page or API response.
- [Bot & Skill Security Auditor](https://coinloader.com/bots/bot-skill-auditor.md) — $29 USD (one-time) — `bot-skill-auditor` — Use when an agent needs a static security review of a third-party skill or bot before running it.
- [Solana Wallet Hygiene & Approval Revoker](https://coinloader.com/bots/solana-wallet-hygiene.md) — $19 USD (one-time) — `solana-wallet-hygiene` — Use when an agent needs to find reclaimable rent and stale delegations on a Solana wallet.
- [Solana Token Launch & Rug Risk Scanner](https://coinloader.com/bots/solana-token-scanner.md) — $29 USD (one-time) — `solana-token-scanner` — Use when an agent needs verifiable on-chain facts about a Solana mint.
- [Token Launch Command Center](https://coinloader.com/bots/token-launch-command-center.md) — $49 USD (one-time) — `token-launch-command-center` — Use when an agent needs a launch audit plus gated, approval-checked social drafting.
- [Pump.fun Coin & Community Manager](https://coinloader.com/bots/pumpfun-coin-manager.md) — $29 USD (one-time) — `pumpfun-coin-manager` — Use when an agent needs a read-only audit and change monitor for a Pump.fun coin.
- [EVM Smart Contract & Proxy Inspector](https://coinloader.com/bots/evm-contract-inspector.md) — $29 USD (one-time) — `evm-contract-inspector` — Use when an agent needs proxy upgradeability, admin and source-verification facts for an EVM contract.
- [EVM Wallet Approval & Permit2 Risk Auditor](https://coinloader.com/bots/evm-approval-auditor.md) — $19 USD (one-time) — `evm-approval-auditor` — Use when an agent needs to list risky token approvals and Permit2 allowances for a wallet.
- [Bitcoin Wallet & UTXO Privacy/Fee Hygiene Auditor](https://coinloader.com/bots/btc-utxo-hygiene.md) — $19 USD (one-time) — `btc-utxo-hygiene` — Use when an agent needs a privacy and fee review of a Bitcoin address.
- [Hyperliquid Perps, Funding & Liquidation Risk Monitor](https://coinloader.com/bots/hyperliquid-monitor.md) — $29 USD (one-time) — `hyperliquid-monitor` — Use when an agent needs liquidation distance, stop coverage and funding checks for Hyperliquid perps.
- [Cross-Chain Token RugScore & Honeypot Scanner](https://coinloader.com/bots/token-rugscore.md) — $29 USD (one-time) — `token-rugscore` — Use when an agent needs a deterministic rug/honeypot score for a token.
- [Multi-Chain Cost-Basis, Wash-Sale & Tax Lot Auditor](https://coinloader.com/bots/cost-basis-ledger.md) — $29 USD (one-time) — `cost-basis-ledger` — Use when an agent needs a cost-basis and wash-sale audit. Not tax advice.

## Bundles

- DeFi & Multi-Chain Wallet Security Pack — $59 USD — `defi-wallet-security-pack` — includes: solana-wallet-hygiene, solana-token-scanner, evm-approval-auditor, evm-contract-inspector, token-rugscore
- Pro Trader & Perps Risk Suite — $69 USD — `pro-trader-perps-suite` — includes: hyperliquid-monitor, solana-token-scanner, btc-utxo-hygiene, solana-wallet-hygiene, token-rugscore

## How an agent buys

- Prices: see the catalog.
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "<sku>", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

⚡ CRYPTO, SOLANA & SECURITY AGENT TEMPLATES FOR GROK BOT

# Solana Rent Reclaim, Token Due-Diligence & Skill Security Bots. Runs on Your Linux Box.

 CoinLoader is a store of Grok Bot crypto-agent templates. Import pre-engineered Grok Bot templates in one click—settled once in SOL or free via the WattCoin Agent Registry. Check a token for rug pull and honeypot traps, mint authority and freeze authority; reclaim SOL rent; revoke approval exposure to a wallet drainer; and watch your Hyperliquid liquidation price. Every template runs inside your own isolated Grok Bot Linux environment with strict read-only and non-custodial guardrails.

 ✓ 12 Live Agents Now (Free + $19–$49 SOL) ✓ No Monthly Subscriptions ✓ Zero Custodial Private Keys ✓ Local `/workspace` Execution (`0600`)

**Every license key unlocks both:**

1. **1-Click Grok Bot Template** (<template link>)
2. **Standalone Single-File Python 3 CLI** (`/runtime/<script>.py`) — Python 3.10+ standard library only, zero `pip install` dependencies; runs locally in Cursor, Claude Code, Windsurf, GitHub Actions CI/CD, or any macOS/Linux/Windows terminal, with `--json` / `--markdown` output.

 ● AVAILABLE NOW — FREE Template ID: `k1oyHmw4iS4VBW1U8_3Ol` · Verified on Grok Bot

 Skills: `getting-started` + `web-extractor`

## Web & API Text Extractor

Published by AIguy · Powered by the WattCoin `/api/v1/scrape` Endpoint · 10 Free/Day + 100 WATT On-Chain Modes

 FREE +100 WATT GRANT

 Self-onboarding web & JSON endpoint scraper for Grok Bot. Registers its own `wck_...` identity on Turn 1, activates your 100 WATT starter balance, and unlocks 10 free plain-text scrapes per UTC day.

-  01 **Zero-Wallet Turn-1 Onboarding:** Automatically calls `POST /api/v1/agents/register`, stores `WATTCOIN_AGENT_KEY` in `/workspace/.wattcoin_env` (`chmod 600`), and completes `onboarding_v1` (25 WATT) + `starter_v1` (75 WATT) for **100 WATT** total.
-  02 **10 Free `text` Scrapes / UTC Day:** Calls `POST https://www.wattcoin.org/api/v1/scrape` with `X-Agent-Key: wck_...` using server-side static HTTP fetch + BeautifulSoup plain-text extraction (no false headless-JS claims) and tracks `X-Quota-Remaining`.
-  03 **Paid `html` / `json` Modes + Local Box Fallback:** Supports on-chain 100 WATT/call `html` and `json` extraction (always asks before spending) plus automatic local `curl` + Python HTML-to-text fallback (`bs4` or stdlib `html.parser`) in `/workspace` when daily quota resets at UTC midnight.

  Get Free Bot →

 Direct Share URL: <template link>

 STEP 1 · IMPORT TEMPLATE INTO GROK BOT ONE CLICK

 Click <template link> to add **Web & API Text Extractor** to your Grok Bot sidebar.

 STEP 2 · SEND YOUR FIRST PROMPT TURN 1

 Paste this starter prompt in chat:

 `"Set up my scraper key and scrape https://www.wattcoin.org/llms.txt"`

 STEP 3 · AUTOMATIC PROVISIONING & VERIFIED OUTPUT 100 WATT + 10/DAY

 Bot provisions `/workspace/.wattcoin_env` (`0600`), completes `onboarding_v1` + `starter_v1` (**100 WATT**), runs its `example.com` check, and writes `/workspace/wattcoin_llms.txt` (`X-Quota-Remaining: 8`).

 Credentials stored locally: `/workspace/.wattcoin_env` (`-rw-------`) Zero JS-rendering claims · Static HTTP + BS4

VERIFIED GROK BOT SKILL CATALOG

## Crypto, Solana & Security Agent Templates

 12 live agents available now: 1 free utility and 11 one-time SOL licenses ($19–$49) covering Solana, EVM, Bitcoin, Hyperliquid perps, and AI skill security. Every template ships with deterministic, fail-closed `SKILL.md` rules: read-only by default, zero seed-phrase prompts, and zero speculative investment or trading verdicts.

### Available Now (12)

 ● LIVE NOW · FREE getting-started + web-extractor

### Web & API Text Extractor

FREE / 100 WATT

 **Powered by the WattCoin `/api/v1/scrape` Endpoint · 10 Free/Day + 100 WATT On-Chain Modes.** Self-registers a `wck_...` Agent Registry identity on Turn 1, earns 100 WATT via `onboarding_v1` + `starter_v1`, and unlocks 10 free plain-text scrapes per UTC day.

- **10/day Free Tier:** `POST /api/v1/scrape` with `format: "text"` (static HTTP + BeautifulSoup text extraction).
- **Paid Modes:** `html` & `json` extraction (100 WATT/call) with mandatory user confirmation before spending.
- **Fail-Safe Quota Fallback:** Branches on error `reason` field and falls back to local `curl` + Python HTML-to-text (`bs4` or stdlib `html.parser`) in `/workspace`.

 **Guardrail:** Never prints `WATTCOIN_AGENT_KEY` in chat; writes `/workspace/.wattcoin_env` with `0600` permissions.

 ● LIVE · $29 IN SOL auditor-setup + bot-skill-auditor

### Bot & Skill Security Auditor

$29 in SOL · One-Time

 **See every network call, credential read, and shell command in a third-party skill, with line numbers, before you run it.** Static, read-only inspector for Grok Bot templates, `SKILL.md` files & GitHub repos via `.wattcoin_audit_prep.py`.

- **Line-Cited 5-Bucket Audit:** Quotes verbatim prompt-bypass strings (`L14`), SSH/`.env` secret reads & cron persistence (`L29`), outbound webhooks/MCPs (`L31`), obfuscation, and local machine escalation.
- **Deterministic Prep Helper:** Wraps untrusted files in random `<untrusted_artifact_<16-hex>>` tags, enforces 50-file / 100 KB / 250 KB caps, pins GitHub refs to 40-char SHAs, and logs `Files Audited` & `Files Skipped`.
- **Transparent Scope Limits:** Flags only what exists in the files at audit time—never claims a skill is "safe" and explicitly states what static analysis cannot catch (runtime-fetched payloads, delayed API responses, time-bombs).

 **Guardrail:** Never executes audited code, never curls embedded URLs, never reads `/workspace/.wattcoin_env` into context, and never issues a "safe/pass" badge or numeric grade.

 ● LIVE · $19 IN SOL solana-wallet-hygiene

### Solana Wallet Hygiene Bot

$19 in SOL · One-Time

 **Find the rent locked in your empty token accounts and the stale delegations still attached to your wallet—then reclaim it yourself, non-custodially.** Each empty standard SPL account holds exactly `0.00203928 SOL` (`2,039,280 lamports`) of reclaimable rent.

- **Dual Program Scan:** Queries `getParsedTokenAccountsByOwner` for both legacy SPL (`Tokenkeg...`) and Token-2022 (`TokenzQd...`).
- **3-Bucket Report:** Strictly separates `SAFE_TO_RECLAIM`, `NEEDS_CONFIRMATION` (active delegates), and `DO_NOT_TOUCH` (active balances).
- **You Sign, We Never Do:** Outputs Phantom / Solflare steps and `spl-token` CLI commands—never asks for a seed phrase or private key.

**Preview sample Wallet Hygiene ReportGuardrail:** Read-only audit first, always. Never asks for seed phrases, never holds keys, and never signs or broadcasts transactions.

 ● LIVE · $29 IN SOL solana-token-scanner

### Retail Token Due-Diligence Bot

$29 in SOL · One-Time

 **Verifiable, timestamped on-chain facts for any Solana mint—mechanics, not motives.** A 5-section report covering identity, authorities, holder concentration, DEX liquidity, and a mandatory non-advice scope note.

- **Authorities & Token-2022 Extensions:** Mint, freeze, and update authorities (present vs. revoked) plus `PermanentDelegate`, `TransferFeeConfig`, `TransferHook`, and `DefaultAccountState`.
- **Top-20 Holder Concentration:** Separates known pools/exchanges from individual wallets via `getTokenLargestAccounts`.
- **DEX Liquidity Snapshot:** Primary pairs, USD liquidity depth, and 24h volume from DexScreener.

**Preview sample Token Due-Diligence ReportGuardrail:** Mechanics, not motives. Never outputs "safe/unsafe" verdicts, "rug/scam" labels, or numerical safety scores.

 ● AVAILABLE NOW · $29 in SOL pumpfun-coin-manager-setup + pumpfun-coin-manager

### [Pump.fun Coin & Community Manager](https://coinloader.com/bots/pumpfun-coin-manager.html)

$29 in SOL · 3 Rebinds

**Know what holders see before they ask.** Audit your Pump.fun coin the way a skeptical holder would see it: which official links are missing from the immutable metadata, whether the creator profile and Callout tab point people to the right place, and whether DexScreener, GeckoTerminal and RugCheck agree.

- 16-key delta monitor (`--state` + `--delta`): authority reinstated, metadata URI changed, supply increased, ban or hidden coin, new Callouts and replies, fee-sharing and creator-profile edits, large new holders, creator sells, liquidity drops, pair dormant/active, closed link gaps, new bot followers.
- Point-in-time audit: missing website/Discord/Telegram in IPFS metadata, creator bio vs `--expected-website`, `--expected-discord`, `--expected-x`, empty Callout tab, GeckoTerminal link gaps, dormant DexScreener pairs, RugCheck risks.
- IPFS metadata read through two hash-verified gateways; Token-2022 authorities and extensions read from public Solana RPC.

 ● AVAILABLE NOW · $49 in SOL token-launch-command-center-setup + token-launch-command-center

### [Token Launch Command Center](https://coinloader.com/bots/token-launch-command-center.html)

$49 in SOL · 3 Rebinds

**Audit, draft, gate, send.** One bundle for the launch week: audit the coin, turn the verified facts (authorities, supply, mint, your official links) into announcement drafts for four channels, lint them, sign them, and send only what you approve.

- `command_center.py init` writes a config from `crypto_launch_preset.json` (banned-term list, link allowlist, X in free Web Intent mode).
- `command_center.py audit MINT --queue` runs the read-only audit and queues fact-only drafts; Gate 1 lint runs on each draft.
- Gate 2 re-verifies an HMAC over the exact approved text, expiry and lint before any send; edited text is refused. Dispatcher is a dry run unless `--live`.

 ● AVAILABLE NOW · $29 in SOL evm-contract-inspector-setup + evm-contract-inspector

### [EVM Smart Contract & Proxy Inspector](https://coinloader.com/bots/evm-contract-inspector.html)

$29 in SOL · 3 Rebinds

**Know who can upgrade the contract before you deposit.** Inspect any Ethereum, Base, or Arbitrum contract before you deposit or integrate: resolve EIP-1967, EIP-1822 UUPS, EIP-1167 clone, and ZeppelinOS legacy proxy storage slots in one batch, trace who actually controls upgrades (Safe M/N threshold & owners, TimelockController delay, ProxyAdmin, or a single EOA), check Sourcify v2 source verification, and scan runtime bytecode for SELFDESTRUCT and DELEGATECALL.

- Batched JSON-RPC slot resolution across **Ethereum (`eth`, 1)**, **Base (`base`, 8453)**, and **Arbitrum One (`arb`, 42161)**: EIP-1967 (`implementation`, `admin`, `beacon`), EIP-1822 UUPS, ZeppelinOS legacy (`0x7050c9e0...` / `0x10d6a54a...`), and EIP-1167 minimal proxy clones.
- Governance & controller chain probing (`--deep`, `--max-depth 2`): classifies Safe multisigs (`getThreshold()` / `getOwners()`), Timelocks (`getMinDelay()` / `delay()`), ProxyAdmin contracts, or single-key EOAs (`EOA_ADMIN`).
- Source verification via **Sourcify v2** (`fields=abi,proxyResolution,compilation`) with Blockscout v2 fallback, plus CBOR-stripped opcode scanning that skips `PUSH1..PUSH32` immediate bytes before flagging `SELFDESTRUCT` (`0xff`) or unexpected `DELEGATECALL` (`0xf4`).

 ● AVAILABLE NOW · $19 in SOL evm-approval-auditor-setup + evm-approval-auditor

### [EVM Wallet Approval & Permit2 Risk Auditor](https://coinloader.com/bots/evm-approval-auditor.html)

$19 in SOL · 3 Rebinds

**Find the unlimited approvals that can still pull your tokens.** Audit any Ethereum, Base, or Arbitrum wallet you own: read the live ERC-20 `allowance()` and Permit2 sub-allowance for every curated and discovered token/spender pair, see the balance actually at risk behind each one, classify the spender (EOA, unverified contract, unlabeled contract, or curated protocol), and get exact `approve(spender, 0)` revoke and Permit2 `lockdown` call-data to sign in your own wallet.

- Live allowance reads across **Ethereum (`eth`, 1)**, **Base (`base`, 8453)**, and **Arbitrum One (`arb`, 42161)**: ERC-20 `allowance(owner, spender)` plus Permit2 `allowance(owner, token, spender)` (amount, expiration, nonce) over curated stablecoins, WETH, WBTC and LSTs, Blockscout-discovered holdings, and bounded `eth_getLogs` Approval-event discovery (`--lookback-blocks`, default 20000).
- Spender classification with balance-at-risk per pair: `EOA_SPENDER` and unverified unlabeled contracts (`UNVERIFIED_SPENDER`) are CRITICAL, unlimited allowances to unlabeled verified contracts (`UNKNOWN_VERIFIED_SPENDER`) are HIGH, unlimited allowances to curated spenders (Uniswap Permit2 & routers, 1inch, CoW Protocol, 0x, ParaSwap, Morpho Blue, Aave V3) are MEDIUM, plus `PERMIT2_ACTIVE_SUBALLOWANCE` / `PERMIT2_EXPIRED_SUBALLOWANCE`.
- Non-custodial remediation call-data: exact `to` + `data` for `approve(spender, 0)` on each flagged token and a single batched Permit2 `lockdown((token, spender)[])` transaction, displayed for you to submit from your own wallet (Rabby, MetaMask, Safe, or hardware signer).

 ● AVAILABLE NOW · $19 in SOL btc-utxo-hygiene-setup + btc-utxo-hygiene

### [Bitcoin Wallet & UTXO Privacy/Fee Hygiene Auditor](https://coinloader.com/bots/btc-utxo-hygiene.html)

$19 in SOL · 3 Rebinds

**Find the dust, address reuse and fee waste hiding in your UTXO set.** Audit any Bitcoin address you own: bucket every UTXO, flag stranded inputs, address reuse, dusting attacks and Ordinals-inscription UTXOs, measure common-input-ownership privacy leaks, and get a consolidation cost-vs-savings matrix plus copy-paste `bitcoin-cli`, Sparrow and Electrum coin-control commands to run in your own wallet.

- Reads public state from **Mempool.space** (Blockstream Esplora fallback): address stats, full UTXO set, recent transactions, fee estimates and BTC/USD price for legacy P2PKH, nested SegWit, native SegWit and Taproot addresses.
- Findings with a 0–100 hygiene score: `ADDRESS_REUSE`, `UTXO_FRAGMENTATION`, `STRANDED_UTXOS`, `DUSTING_ATTACK_SUSPECT`, `INSCRIPTION_PROTECTED`, `CIOH_COSPEND_EXPOSURE`, `ROUND_NUMBER_CHANGE_LEAK` and `CONSOLIDATION_WINDOW_OPEN`.
- Non-custodial remediation: `bitcoin-cli lockunspent` freeze commands and an unsigned-PSBT `sendall` consolidation plan, displayed for you to run yourself. Strictly read-only: never accepts keys, seeds or PSBTs.

 ● AVAILABLE NOW · $29 in SOL hyperliquid-monitor-setup + hyperliquid-monitor

### [Hyperliquid Perps, Funding & Liquidation Risk Monitor](https://coinloader.com/bots/hyperliquid-monitor.html)

$29 in SOL · 3 Rebinds

**Know how far every perp is from liquidation.** Monitor any Hyperliquid wallet or subaccount you own from its public `0x` address: liquidation distance per position, cross/isolated margin utilisation, missing reduceOnly stop-losses and the funding you pay per day. Scan every perp for extreme funding APR, mark-oracle basis and Hyperliquid vs Binance / Bybit predicted funding, and inspect HLP across its child sub-vaults.

- Wallet risk via the public `POST https://api.hyperliquid.xyz/info`: `LIQ_DISTANCE_CRITICAL` / `HIGH` / `MEDIUM`, `MARGIN_UTIL_*`, `HIGH_EFFECTIVE_LEVERAGE`, `UNPROTECTED_POSITION_NO_SL`, `NON_REDUCE_ONLY_STOP` and `ADVERSE_FUNDING_BLEED`.
- Market scanner: funding APR, basis bps, OI and volume for 179+ perps, funding extremes, and `CROSS_VENUE_FUNDING_DIVERGENCE` against Binance and Bybit predicted funding. HLP and vault posture across 354+ open positions.
- Stateful delta routine (`--state --delta`): `LIQ_DISTANCE_TIGHTENED`, `MARGIN_UTIL_SPIKE`, `FUNDING_REGIME_SHIFT`. Keyless: never accepts keys, never calls `/exchange`, never places orders.

 ● AVAILABLE NOW · $29 in SOL token-rugscore-setup + token-rugscore

### [Cross-Chain Token RugScore & Honeypot Scanner](https://coinloader.com/bots/token-rugscore.html)

$29 in SOL · 3 Rebinds

**Get one 0–100 rug-risk number before you buy the token.** Audit a Solana SPL / Token-2022 mint or an Ethereum, Base or Arbitrum contract and get a deterministic RugScore with a risk tier, the exact rule IDs that fired (`RS-SOL-01..05`, `RS-EVM-01..04`) and an `audit_sha256` you can re-run and compare.

- Solana: mint and freeze authority, Token-2022 extension traps (permanent delegate, transfer hook, transfer fee), holder concentration and DEX liquidity.
- EVM (`eth` / `base` / `arb`): upgradeable-proxy admin, honeypot-style opcode traps, unverified source and thin liquidity.
- Runs in Grok Bot or as a zero-dependency Python 3 CLI (`token_rugscore.py`) in Cursor, Claude Code or CI/CD. Read-only: never asks for keys and never calls a token “safe”.

 ● AVAILABLE NOW · $29 in SOL cost-basis-ledger-setup + cost-basis-ledger

### [Multi-Chain Cost-Basis, Wash-Sale & Tax Lot Auditor](https://coinloader.com/bots/cost-basis-ledger.html)

$29 in SOL · 3 Rebinds

**Know your gains, lots and wash-sale risk before tax season.** Match every disposal to a lot with FIFO, LIFO or HIFO across Solana, EVM and Bitcoin and get IRS Form 8949 / Schedule D compatible rows, a short-term vs long-term split, the exact rule IDs that fired (`CB-WASH-01`, `CB-FEE-01`, `CB-LOT-01`, `CB-HIFO-01`, `CB-STLT-01`) and an `audit_sha256` you can re-run and compare.

- Wash-sale 30-day rebuy flags, gas-fee basis adjustments, zero-basis airdrop warnings and 330–364 day holding-period alerts.
- Input a `.json` / `.csv` export or a wallet address; export Form 8949 rows with `--csv-out`.
- Runs in Grok Bot or as a zero-dependency Python 3 CLI (`cost_basis_ledger.py`) in Cursor, Claude Code or CI/CD. Read-only: never asks for keys. Not tax advice.

VALUE BUNDLES

## Value Bundles — Multi-Bot Packs (One License Key Unlocks All Included Bots)

 Buy a pack once in SOL and receive a single `wcl_...` license code plus an unlisted Grok Bot template link for every bot in the bundle. The same code activates each included bot (up to 3 rebinds).

 ● 5-BOT BUNDLE · $59 IN SOL SAVE $66 vs $125 list

### DeFi & Multi-Chain Wallet Security Pack

$59 / one-time

Read-only Solana + EVM wallet, approval, token and contract due-diligence in one pack. **One `wcl_...` license key unlocks every included bot.**

- [Solana Wallet Hygiene Bot](https://coinloader.com/bots/solana-wallet-hygiene.html) ($19 list)
- [Retail Token Due-Diligence Bot](https://coinloader.com/bots/solana-token-scanner.html) ($29 list)
- [EVM Wallet Approval & Permit2 Auditor](https://coinloader.com/bots/evm-approval-auditor.html) ($19 list)
- [EVM Smart Contract & Proxy Inspector](https://coinloader.com/bots/evm-contract-inspector.html) ($29 list)
- [Cross-Chain Token RugScore & Honeypot Scanner](https://coinloader.com/bots/token-rugscore.html) ($29 list · now included at no extra cost)

**SKU:** `defi-wallet-security-pack` · non-custodial SOL checkout · up to 3 rebinds

 ● 5-BOT BUNDLE · $69 IN SOL SAVE $56 vs $125 list

### Pro Trader & Perps Risk Suite

$69 / one-time

Perps funding/liquidation monitoring plus token, Bitcoin UTXO and wallet hygiene checks. **One `wcl_...` license key unlocks every included bot.**

- [Hyperliquid Perps Risk Monitor](https://coinloader.com/bots/hyperliquid-monitor.html) ($29 list)
- [Retail Token Due-Diligence Bot](https://coinloader.com/bots/solana-token-scanner.html) ($29 list)
- [Bitcoin Wallet & UTXO Hygiene Auditor](https://coinloader.com/bots/btc-utxo-hygiene.html) ($19 list)
- [Solana Wallet Hygiene Bot](https://coinloader.com/bots/solana-wallet-hygiene.html) ($19 list)
- [Cross-Chain Token RugScore & Honeypot Scanner](https://coinloader.com/bots/token-rugscore.html) ($29 list · now included at no extra cost)

**SKU:** `pro-trader-perps-suite` · non-custodial SOL checkout · up to 3 rebinds

 ● FLAGSHIP · $49 IN SOL FLAGSHIP · ALL-IN-ONE

### Token Launch Command Center

$49 / one-time

Flagship all-in-one launch workflow: Pump.fun coin manager, social hub, dispatcher and crypto launch preset in a single license. **One `wcl_...` license key unlocks the Command Center.**

- [Token Launch Command Center detail page →](https://coinloader.com/bots/token-launch-command-center.html)
- [Pump.fun Coin & Community Manager](https://coinloader.com/bots/pumpfun-coin-manager.html) runtime included

**SKU:** `token-launch-command-center` · non-custodial SOL checkout · up to 3 rebinds

VERIFIED SYSTEM ARCHITECTURE

## How CoinLoader Templates Work

 Built for sovereign execution inside Grok Bot: no custodial backend, no browser plugins, and transparent license verification through the WattCoin Agent Registry.

**Dual runtime, one license:** each `wcl_...` key activates the Grok Bot template and the standalone CLI.

1. **1-Click Grok Bot Template** (<template link>)
2. **Standalone Single-File Python 3 CLI** (`/runtime/<script>.py`) — Python 3.10+ standard library only, zero `pip install` dependencies; runs locally in Cursor, Claude Code, Windsurf, GitHub Actions CI/CD, or any macOS/Linux/Windows terminal, with `--json` / `--markdown` output.

 STEP 01 · ONE-CLICK IMPORT

### Import Directly Into Grok Bot

 Every template link (<template link>) opens natively inside Grok Bot with inspectable, plain-text `SKILL.md` instructions and zero hidden binaries.

 <template link>

 STEP 02 · ISOLATED LINUX BOX

### Runs Locally in Your `/workspace`

 Wallet RPC audits, unsigned transaction staging, and static security inspections execute directly on your own isolated Grok Bot Linux container. Credentials stay in `/workspace/.wattcoin_env` with `0600` permissions.

 chmod 600 /workspace/.wattcoin_env # -rw-------

 STEP 03 · WATTCOIN REGISTRY

### Powered by WattCoin API v1

 Agents self-register a `wck_...` key via `POST /api/v1/agents/register`, earn **100 WATT** via `onboarding_v1` + `starter_v1`, and bind paid SKU licenses (`wcl_...`) via `POST /api/v1/agents/license/claim`.

 GET https://www.wattcoin.org/api/v1/agents/license?sku=bot-skill-auditor

#### Agent-Readable Documentation & Live Endpoints (`wattcoin.org/llms.txt`)

 Building your own custom agent or verifying our backend endpoints? Inspect the full machine-readable API specification for Agent Registry, Paid SKU Licensing, Tasks, SwarmSolve, and Web Scraper.

 [ Read wattcoin.org/llms.txt ↗ ](https://www.wattcoin.org/llms.txt) [ Visit WattCoin.org ↗ ](https://www.wattcoin.org)

NON-CUSTODIAL EXECUTION, SOL LICENSING & ON-CHAIN VERIFICATION

## Frequently Asked Questions

 How one-time SOL checkout, non-custodial local `/workspace` execution, 3-rebind license recovery, and verifiable on-chain refusal boundaries work on CoinLoader.com.

**How does one-time SOL licensing work—are there any monthly subscriptions?**

Every paid CoinLoader template ($19 or $29 USD equivalent in SOL) is a one-time on-chain purchase with zero recurring subscriptions. Clicking Buy License requests a 15-minute locked SOL/USD quote from POST https://www.wattcoin.org/api/v1/agents/license/quote, and pasting your confirmed Solana transaction signature issues your wcl_... bearer license code immediately.

**Is CoinLoader non-custodial? Does any bot ever touch my private keys or seed phrase?**

Yes—100% non-custodial. Every CoinLoader template executes locally inside your isolated Grok Bot Linux container (/workspace) in read-only mode using public Solana wallet or mint addresses. Our templates never ask for private keys or seed phrases (and immediately refuse if one is pasted) and never sign or broadcast transactions on your behalf.

**How do wcl_... license claiming and the 3 workspace-reset rebinds work?**

On Turn 1, the setup skill provisions your workspace agent key (wck_...) in /workspace/.wattcoin_env (chmod 600) and calls POST https://www.wattcoin.org/api/v1/agents/license/claim to bind your wcl_... license code. Each license includes up to 3 workspace-reset rebinds so you can re-activate if your /workspace container is ever recreated.

**What are CoinLoader's on-chain citation rules and refusal boundaries?**

CoinLoader templates report verifiable mechanics, not motives. The Solana Wallet Hygiene Bot separates accounts into SAFE_TO_RECLAIM (0.00203928 SOL / 2,039,280 lamports per empty SPL account), NEEDS_CONFIRMATION (active delegates), and DO_NOT_TOUCH. The Retail Token Due-Diligence Bot cites RPC slots and DexScreener timestamps and never outputs 'safe/rug/scam' verdicts or investment advice.

**How does the free Web & API Text Extractor work?**

The Web & API Text Extractor (<template link>) is free forever. On Turn 1, it registers a wck_... key in /workspace/.wattcoin_env (0600), completes onboarding_v1 (25 WATT) + starter_v1 (75 WATT) for 100 WATT total, and provides 10 free plain-text extractions per UTC day via POST https://www.wattcoin.org/api/v1/scrape plus automatic local curl fallback.

**How do I check a Solana token for rug pull and honeypot risk, mint authority and freeze authority?**

Use the Retail Token Due-Diligence Bot ($29 in SOL). It reads the mint account of any SPL or Token-2022 token and reports whether the mint authority and freeze authority are still active (an active freeze authority can lock your tokens, and an active mint authority can inflate supply), plus Token-2022 extensions that can behave like a honeypot or rug pull such as PermanentDelegate, TransferHook, TransferFeeConfig and DefaultAccountState, top-20 holder concentration and DEX liquidity depth. It reports verifiable mechanics and never labels a token 'safe' or 'rug'.

**How do I revoke approval exposure and reduce wallet drainer risk on EVM chains?**

Use the EVM Wallet Approval & Permit2 Risk Auditor ($19 in SOL). It lists unlimited ERC-20 allowances and Uniswap Permit2 sub-allowances on Ethereum, Base and Arbitrum, classifies each spender, and prints exact approve(spender, 0) revoke call-data that you submit yourself. It never asks for a private key or seed phrase and never signs a transaction. For the Solana equivalent, the Solana Wallet Hygiene Bot ($19 in SOL) revokes token delegates and can reclaim SOL rent, 0.00203928 SOL per closed empty token account, without sharing keys.

**Can CoinLoader show my Hyperliquid liquidation price and funding drag?**

Yes. The Hyperliquid Perps, Funding & Liquidation Risk Monitor ($29 in SOL) takes only a public 0x address and reports the distance between mark price and liquidation price for every position, margin utilisation, missing stop-losses and the funding you pay per day. Run it on a schedule with --state and --delta to be alerted only when your liquidation price distance tightens. It is read-only and keyless, with no trading permissions. Pair it with the Bitcoin UTXO auditor and Solana tools in the Pro Trader & Perps Risk Suite bundle ($69 in SOL).

**Does one license key unlock both the Grok Bot template and a standalone CLI I can run in Cursor or Claude Code?**

Yes. Every wcl_... license key unlocks both: (1) the 1-Click Grok Bot template (<template link>) and (2) the standalone single-file Python 3 CLI (/runtime/<script>.py). The CLI needs only Python 3.10+ and the standard library, with zero pip install dependencies, and runs locally in Cursor, Claude Code, Windsurf, GitHub Actions CI/CD, or any macOS, Linux or Windows terminal, emitting deterministic --json or --markdown output.
