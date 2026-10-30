# Cross-Chain Token RugScore & Honeypot Scanner

> Audit Solana SPL/Token-2022 mints and Ethereum, Base & Arbitrum contracts with a deterministic 0-100 RugScore, proxy checks, and DEX liquidity depth.

- SKU: `token-rugscore`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/token-rugscore.html
- Markdown: https://coinloader.com/bots/token-rugscore.md

## When to use

Use when an agent needs a deterministic rug/honeypot score for a token.

Inputs: a Solana mint or an Ethereum/Base/Arbitrum token contract

Outputs: RugScore, risk tier, rule IDs and an audit_sha256

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "token-rugscore", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Cross-Chain Token RugScore & Honeypot Scanner — One 0–100 number before you buy the token.

Audit any Solana SPL / Token-2022 mint or Ethereum, Base, or Arbitrum token contract and get a deterministic RugScore from 0 to 100 with a risk tier and the exact rules that fired: mint and freeze authority, dangerous Token-2022 extensions, holder concentration, upgradeable-proxy admins, SELFDESTRUCT and DELEGATECALL opcode traps, source verification and DEX liquidity depth. Every run ends with an `audit_sha256` so you can re-run and compare.

 SKU: `token-rugscore` · Skills: `token-rugscore-setup + token-rugscore` · Runtime: `/runtime/token_rugscore.py` · Also included in `defi-wallet-security-pack` ($59) and `pro-trader-perps-suite` ($69)

## What It Does

- **Solana rules `RS-SOL-01..05`:** active mint authority (`RS-SOL-01`), active freeze authority (`RS-SOL-02`), Token-2022 extension traps such as `PermanentDelegate`, `TransferHook`, `TransferFeeConfig` and frozen `DefaultAccountState` (`RS-SOL-03`), top-holder concentration (`RS-SOL-04`) and DEX liquidity depth and pair age (`RS-SOL-05`).
- **EVM rules `RS-EVM-01..04` on Ethereum (`eth`), Base (`base`) and Arbitrum One (`arb`):** upgradeable-proxy admin and EOA control over EIP-1967 / EIP-1822 / EIP-1167 slots (`RS-EVM-01`), `SELFDESTRUCT` and unexpected `DELEGATECALL` opcode traps (`RS-EVM-02`), unverified source via Sourcify (`RS-EVM-03`) and thin liquidity (`RS-EVM-04`).
- **Deterministic scoring:** fixed rule weights are summed and capped at 100, then mapped to `LOW` / `MODERATE` / `HIGH` / `CRITICAL`. Same input and same chain data give the same score and the same `audit_sha256`.
- **Built for pipelines:** `--json` / `--markdown` output, risk-tier exit codes for CI/CD gating, and 1200x675 PNG audit receipts. 100% Python stdlib.

## What It Does Not Do

- Strictly read-only: never asks for private keys or seed phrases, and never builds, signs, or broadcasts transactions.
- Never labels a token 'safe', 'audited', or 'rug-proof'; a low RugScore only means none of the listed rules fired.
- No price prediction and no buy or sell advice. Opcode and extension checks are heuristics, not formal verification or a substitute for a source audit.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `token-rugscore-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and confirms the bot files are installed. The license code is never printed in chat. Also included at no extra cost in the [DeFi & Multi-Chain Wallet Security Pack](https://coinloader.com/#bundle-defi-wallet-security-pack) ($59) and the [Pro Trader & Perps Risk Suite](https://coinloader.com/#bundle-pro-trader-perps-suite) ($69).

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Cross-Chain Token RugScore & Honeypot Scanner

**How does the Cross-Chain Token RugScore calculate a 0–100 risk score for Solana and EVM tokens?**

Each rule is a fixed-weight check, and the weights of the rules that fire are summed and capped at 100. Solana mints are scored by RS-SOL-01..05 (active mint authority, active freeze authority, dangerous Token-2022 extensions, top-holder concentration, DEX liquidity depth); Ethereum, Base and Arbitrum contracts by RS-EVM-01..04 (upgradeable-proxy admin, honeypot-style opcode traps, unverified source, liquidity). The score maps to a risk tier (0–24 LOW, 25–49 MODERATE, 50–74 HIGH, 75–100 CRITICAL). There is no model and no randomness: the same input and the same chain data produce the same score and the same audit_sha256, so you can re-run an audit and compare.

**Which Solana Token-2022 extensions and EVM proxy or opcode traps does RugScore flag?**

On Solana it reads the mint account and flags an active mint authority and freeze authority, plus the Token-2022 extensions that let an issuer move or tax your balance: PermanentDelegate, TransferHook, TransferFeeConfig, DefaultAccountState (frozen) and a mutable metadata pointer. On Ethereum, Base and Arbitrum it resolves EIP-1967, EIP-1822 UUPS and EIP-1167 proxy slots, reports whether the upgrade admin is a single EOA, and scans runtime bytecode (CBOR metadata stripped, PUSH immediates skipped) for SELFDESTRUCT and unexpected DELEGATECALL, then checks Sourcify for verified source. These are byte-level and account-level heuristics with cited evidence, not a formal audit.

**Can I run token_rugscore.py locally in Cursor, Claude Code, or CI/CD and generate 1200x675 PNG audit receipts?**

Yes. One wcl_... license unlocks both the 1-Click Grok Bot and the standalone single-file token_rugscore.py CLI from /runtime/token_rugscore.py. It needs Python 3.10+ and the standard library only, with no pip install, and it runs in Cursor, Claude Code, Windsurf, any terminal or a CI/CD job. It emits text, --json or --markdown, returns a non-zero exit code by risk tier so a pipeline can gate on it, and can render a 1200x675 PNG audit receipt showing the score, tier, fired rule IDs and audit_sha256.

**What safety and refusal boundaries does the Cross-Chain Token RugScore scanner enforce?**

It is strictly read-only: it never asks for private keys or seed phrases and never builds, signs or broadcasts a transaction. It never labels a token 'safe', 'audited' or 'rug-proof', because a low RugScore only means none of the listed rules fired, not that the token is trustworthy. It does not predict price, give buy or sell advice, or certify a contract; output is factual, with evidence for every rule, and is not financial or security-certification advice.
