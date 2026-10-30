# Bitcoin Wallet & UTXO Privacy/Fee Hygiene Auditor

> Read-only Bitcoin UTXO auditor for Grok Bot ($19 SOL). Flags address reuse, dust and stranded UTXOs, protects Ordinals, and plans consolidation by sats/vB fee.

- SKU: `btc-utxo-hygiene`
- Price: $19 USD (one-time)
- Page: https://coinloader.com/bots/btc-utxo-hygiene.html
- Markdown: https://coinloader.com/bots/btc-utxo-hygiene.md

## When to use

Use when an agent needs a privacy and fee review of a Bitcoin address.

Inputs: a mainnet address

Outputs: UTXO and address-reuse findings, consolidation cost matrix, coin-control commands

## How an agent buys

- Price: $19 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "btc-utxo-hygiene", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Bitcoin Wallet & UTXO Privacy/Fee Hygiene Auditor — Find the dust, address reuse and fee waste hiding in your UTXO set.

Audit any Bitcoin mainnet address you own (legacy P2PKH, nested SegWit, native SegWit, Taproot): count and bucket every UTXO, find stranded inputs that cost more to spend than they are worth, detect address reuse, dusting attacks and Ordinals-inscription UTXOs you must not sweep, measure common-input-ownership privacy leaks, and get a consolidation cost-vs-savings matrix plus copy-paste `bitcoin-cli` / Sparrow / Electrum coin-control commands to run in your own wallet.

 SKU: `btc-utxo-hygiene` · Skills: `btc-utxo-hygiene-setup + btc-utxo-hygiene` · Tested: 1,242 lines stdlib Python, 157 unit tests · Category: Bitcoin / Wallet Hygiene

## What It Does

- Validates one or more Bitcoin mainnet addresses (Base58Check, Bech32 BIP-173, Bech32m BIP-350) and reads public state from the **Mempool.space** REST API with **Blockstream Esplora** fallback, or from an `--offline` fixture: address stats, the full UTXO set, recent transactions, fee estimates, mempool blocks and BTC/USD price.
- UTXO hygiene: value buckets, `UTXO_FRAGMENTATION`, `STRANDED_UTXOS` (strict `value ≤ input vB × rate` and a conservative margin via `--min-value-multiple`), `LEGACY_SCRIPT_TYPE`, `DUSTING_ATTACK_SUSPECT`, and a creating-transaction witness scan that marks Ordinals-inscription UTXOs as `INSCRIPTION_PROTECTED` so they are never swept.
- Fee planning: a consolidation plan and cost-vs-savings matrix for P2WPKH or P2TR outputs (`--consolidate-to`) at current and window fee rates, with break-even future fee rate and a `CONSOLIDATION_WINDOW_OPEN` signal (`--window-rate`, `--target-fee`).
- Privacy exposure from recent transactions: `ADDRESS_REUSE`, `CIOH_COSPEND_EXPOSURE`, `CIOH_CROSS_ADDRESS_LINK`, `ROUND_NUMBER_CHANGE_LEAK` and `SCRIPT_TYPE_MISMATCH_CHANGE`, plus a 0–100 hygiene score per address and per wallet.
- Non-custodial coin control: freeze/do-not-spend outpoints (`bitcoin-cli lockunspent`, Sparrow “Freeze UTXO”, Electrum “Freeze Coin”) and an unsigned-PSBT `bitcoin-cli sendall ... psbt=true` consolidation command, displayed for you to run yourself.
- Stateful delta monitor (`--state PATH --delta`): emits `NEW_DUST`, `UTXO_COUNT_CHANGED` and `CONSOLIDATION_WINDOW_OPEN` events between runs, with `--format text|markdown|json` output and exit codes 0 clean / 1 MEDIUM / 2 HIGH / 3 CRITICAL / 10 bad input / 11 degraded sources. 1,242 lines stdlib Python, 157 passing unit tests.

## What It Does Not Do

- Strictly read-only (public Mempool.space / Blockstream Esplora `GET` endpoints only): never accepts or asks for private keys, WIF, `xprv`/`yprv`/`zprv`, seed phrases or PSBTs, and never builds, signs, or broadcasts a transaction. Coin-control commands are displayed for you to run in your own wallet.
- Heuristics (CIOH, change detection, dusting, inscription envelopes) are probabilistic and cover only the recent transactions and small UTXOs it states it checked. “No findings” never means “private” or “safe to sweep”. Addresses starting with `3` are assumed to be nested SegWit (P2SH-P2WPKH).
- Refuses to target third-party wallets for exploitation or deanonymisation, rank wallets by balance, or build dust-attack target lists. Not financial, legal, or tax advice.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `btc-utxo-hygiene-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and installs the SHA-256-pinned `bot_common.py` and `btc_utxo_hygiene.py` runtime. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (`/runtime/btc_utxo_hygiene.py`) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Bitcoin Wallet & UTXO Privacy/Fee Hygiene Auditor

**When and how should I consolidate fragmented Bitcoin UTXOs without overpaying in sats/vB fees?**

Run the auditor on an address you own. It buckets your UTXO set, flags UTXO_FRAGMENTATION and STRANDED_UTXOS (inputs that cost more to spend than they are worth at the current sats/vB rate), and builds a cost-vs-savings matrix for consolidating into P2WPKH or P2TR outputs at current and window fee rates. It shows the break-even future fee rate and raises CONSOLIDATION_WINDOW_OPEN when fees fall below your --window-rate, then prints an unsigned-PSBT bitcoin-cli sendall command for you to run yourself.

**How does the auditor protect Ordinals inscriptions and Runes dust outputs from accidental spend during UTXO consolidation?**

It scans the creating transaction's witness data and marks Ordinals-inscription UTXOs as INSCRIPTION_PROTECTED so they are excluded from consolidation, and it prints freeze commands (bitcoin-cli lockunspent, Sparrow Freeze UTXO, Electrum Freeze Coin) for outpoints you want to keep untouched. v1 does not decode Runes balances, so freeze any small output you know carries Runes before sweeping; 'no findings' never means 'safe to sweep'.

**How is Bitcoin address reuse privacy risk scored across a wallet or UTXO set?**

From recent transactions it flags ADDRESS_REUSE, CIOH_COSPEND_EXPOSURE and CIOH_CROSS_ADDRESS_LINK (common-input-ownership links), ROUND_NUMBER_CHANGE_LEAK and SCRIPT_TYPE_MISMATCH_CHANGE, plus DUSTING_ATTACK_SUSPECT for small unsolicited outputs. These roll up into a 0-100 hygiene score per address and per wallet. The heuristics are probabilistic and cover only the recent transactions the report states it checked.

**Does the Bitcoin UTXO auditor ever ask for xpubs, seed phrases, or private keys?**

No. It takes plain Bitcoin addresses only and reads public Mempool.space or Blockstream Esplora GET endpoints. It never accepts or asks for private keys, WIF, xprv/yprv/zprv, seed phrases or PSBTs, and it never builds, signs or broadcasts a transaction. It also refuses to target third-party wallets for exploitation or deanonymisation.
