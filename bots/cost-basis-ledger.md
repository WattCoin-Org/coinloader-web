# Multi-Chain Cost-Basis, Wash-Sale & Tax Lot Auditor

> FIFO, LIFO & HIFO cost-basis across Solana, EVM and Bitcoin: Form 8949 / Schedule D rows, wash-sale risk, fee basis and a deterministic audit_sha256.

- SKU: `cost-basis-ledger`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/cost-basis-ledger.html
- Markdown: https://coinloader.com/bots/cost-basis-ledger.md

## When to use

Use when an agent needs a cost-basis and wash-sale audit. Not tax advice.

Inputs: a normalized .json/.csv transaction export, or a Solana/EVM/Bitcoin address

Outputs: FIFO/LIFO/HIFO lots, Form 8949-style rows, wash-sale flags, audit_sha256

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "cost-basis-ledger", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Multi-Chain Cost-Basis, Wash-Sale & Tax Lot Auditor — FIFO, LIFO & HIFO lots, Form 8949 rows and wash-sale risk before you file.

Feed it a normalized transaction export (or a Solana, EVM or Bitcoin wallet address) and get a deterministic tax-lot audit: every disposal matched to an acquisition lot, short-term vs long-term gains, IRS Form 8949 / Schedule D compatible rows, and the exact rule IDs that fired (`CB-WASH-01`, `CB-FEE-01`, `CB-LOT-01`, `CB-HIFO-01`, `CB-STLT-01`), sealed with an `audit_sha256` you can re-run and compare.

 SKU: `cost-basis-ledger` · Skills: `cost-basis-ledger-setup + cost-basis-ledger` · Runtime: `/runtime/cost_basis_ledger.py`

## What It Does

- **Lot matching engines:** `--method fifo` (oldest first), `lifo` (newest first) and `hifo` (highest cost first), with a side-by-side method comparison of net P&L and illustrative tax for all three.
- **Short-term vs long-term:** holding period under 365 days is `SHORT`, 365 days or more is `LONG`; the report gives `short_term_gain_usd`, `long_term_gain_usd`, `net_realized_pnl_usd`, `total_proceeds_usd` and `total_cost_basis_usd` for the chosen `--tax-year`.
- **Form 8949 / Schedule D rows:** asset, date acquired, date sold, proceeds, cost basis, fee adjustment, gain or loss, term, wash-sale flag, disallowed amount and lot ID, exportable with `--csv-out`.
- **Wash-sale risk (`CB-WASH-01`):** loss sales with a same-asset rebuy inside the 30-day window, with the disallowed loss scaled by replacement quantity.
- **Fees, orphans and thresholds:** gas / network / priority fees added to basis (`CB-FEE-01`), zero-basis airdrops and sales with no acquisition lot (`CB-LOT-01`), method tax delta (`CB-HIFO-01`) and sales 330–364 days into a holding period (`CB-STLT-01`).
- **Multi-chain input:** Solana SPL, EVM ERC-20 / native and Bitcoin, from a `.json` or `.csv` export; the chain is auto-detected from a `--wallet` address. Built for pipelines: `--json` / `--markdown` output and 1200x675 PNG audit receipts. 100% Python stdlib.

## What It Does Not Do

- Strictly read-only: never asks for private keys or seed phrases, and never signs or broadcasts transactions.
- Not tax, legal or financial advice. Wash-sale treatment of digital assets is unsettled, so `CB-WASH-01` is a risk flag, and the method-comparison tax figures use illustrative flat rates.
- A bare `--wallet` run has no USD price history, so it uses a clearly labelled sample ledger; supply `--lots-file` for a real audit.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `cost-basis-ledger-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and installs the SHA-256 pinned runtime. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (`/runtime/cost_basis_ledger.py`) — standard library only, zero `pip install`.

## Frequently Asked Questions — Multi-Chain Cost-Basis, Wash-Sale & Tax Lot Auditor

**How does the Multi-Chain Cost-Basis Ledger calculate FIFO, LIFO and HIFO capital gains for crypto?**

Every disposal is matched against your acquisition lots in order: FIFO uses the oldest lot first, LIFO the newest, and HIFO the lot with the highest unit cost (acquisition fees included) to minimise the gain. Each match becomes one Form 8949 / Schedule D row with asset, date acquired, date sold, proceeds, cost basis, fee adjustment, gain or loss, SHORT or LONG term, wash-sale flag and lot ID. The same transactions and method always produce the same rows and the same audit_sha256.

**What is the difference between short-term and long-term gains here, and what does CB-STLT-01 warn about?**

A lot held fewer than 365 days is SHORT term; 365 days or more is LONG term. CB-STLT-01 fires when a profitable short-term sale happened 330 to 364 days after acquisition, because waiting a few more days would have changed the holding-period bucket. The alert reports how many days remained to the long-term threshold.

**How does the wash-sale rule CB-WASH-01 work for crypto, and is it a tax ruling?**

CB-WASH-01 flags any loss disposition that has a same-asset purchase from a different lot within 30 days before or after the sale. The disallowed amount is scaled by the replacement quantity and shown as wash_disallowed_usd, which is added back to the reported loss. Wash-sale treatment of digital assets is unsettled, so this is a risk flag for you and your tax professional, not a ruling, and the tool is not tax advice.

**Can I audit a wallet address, and what are CB-LOT-01 and CB-FEE-01?**

Pass --lots-file with a normalized .json or .csv export for a real audit. With --wallet alone the CLI auto-detects Solana, EVM (0x...) or Bitcoin addresses but public RPC history carries no USD prices, so it uses a clearly labelled deterministic sample ledger. CB-LOT-01 flags dispositions that matched a zero-basis airdrop or transfer-in, or that had no acquisition lot at all. CB-FEE-01 flags gas, network and priority fees that were recorded but not added to your cost basis (the default applies them).

**Can I run cost_basis_ledger.py locally in Cursor, Claude Code or CI/CD and generate PNG audit receipts?**

Yes. One wcl_... license unlocks both the Grok Bot and the standalone single-file cost_basis_ledger.py CLI from /runtime/cost_basis_ledger.py. It needs Python 3 and the standard library only, emits --json, --markdown or a Form 8949 --csv-out file, and can render a 1200x675 PNG receipt with --receipt-out. It is read-only: it never asks for private keys or seed phrases and never signs or broadcasts anything.
