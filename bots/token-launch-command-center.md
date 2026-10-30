# Pump.fun Token Launch Command Center ($49 SOL) | CoinLoader

> Pump.fun launch bundle for Grok Bot ($49 SOL): coin audit and delta monitor plus a gated X, Discord, Telegram & Bluesky publisher with lint and HMAC approval.

- SKU: `token-launch-command-center`
- Price: $49 USD (one-time)
- Page: https://coinloader.com/bots/token-launch-command-center.html
- Markdown: https://coinloader.com/bots/token-launch-command-center.md

## When to use

Use when an agent needs a launch audit plus gated, approval-checked social drafting.

Inputs: a mint address; a launch config

Outputs: audit, queued fact-only drafts, dry-run dispatch

## How an agent buys

- Price: $49 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "token-launch-command-center", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Token Launch Command Center — Audit, draft, gate, send.

One bundle for the launch week: audit the coin, turn the verified facts (authorities, supply, mint, your official links) into announcement drafts for four channels, lint them, sign them, and send only what you approve. Includes the Pump.fun Coin & Community Manager, the Social Hub Publisher engine, and a crypto launch preset.

 SKU: `token-launch-command-center` · Skills: `token-launch-command-center-setup + token-launch-command-center` · Tested: 13 bundle tests plus both component suites

## What It Does

- `command_center.py init` writes a config from `crypto_launch_preset.json` (banned-term list, link allowlist, X in free Web Intent mode).
- `command_center.py audit MINT --queue` runs the read-only audit and queues fact-only drafts; Gate 1 lint runs on each draft.
- Gate 2 re-verifies an HMAC over the exact approved text, expiry and lint before any send; edited text is refused. Dispatcher is a dry run unless `--live`.
- X: free 1-click Web Intents by default; paid API (2026 pay-per-use, $0.015 plain post, $0.20 with a link) only with explicit opt-in.
- Bundled modules are tested byte-identical to the standalone products.

## What It Does Not Do

- No wallet keys, signing, or auto-posting; `--live` is explicit and per item.
- No price, return or ‘next X’ claims; no safe/scam/rug verdicts.
- No wash-trading advice, no unsolicited DMs or holder tags.
- An ambiguous send is marked unknown and never retried automatically.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `token-launch-command-center-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and confirms the bot files are installed. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Token Launch Command Center

**What is included in the Token Launch Command Center bundle for Pump.fun and Solana launches?**

One license covers the Pump.fun Coin & Community Manager, the Social Hub Publisher engine (with its dispatcher) and a crypto launch preset containing a banned-term list and a link allowlist. Together they audit your coin, turn verified facts into drafts for X, Discord, Telegram and Bluesky, lint and sign them, and send only what you approve.

**How does the 4-stage Pump.fun audit, Token-2022 authority check, and Social Hub launch workflow operate?**

command_center.py init writes a config from the preset, then command_center.py audit MINT --queue runs the read-only coin audit (including Token-2022 authority and extension reads) and queues fact-only drafts. Gate 1 lints each draft, Gate 2 re-verifies an HMAC over the exact approved text, expiry and lint before sending, and the dispatcher is a dry run unless --live is passed per item.

**How does one wcl_... bundle license key unlock all included bot templates and runtimes?**

On Turn 1 the token-launch-command-center-setup skill verifies your agent key and binds your wcl_... code through the read-only license helper. That single code covers every included module, with up to 3 workspace-reset rebinds, and the license code is never printed in chat. The bundled modules are tested byte-identical to the standalone products.

**What pre-flight linting and refusal guardrails protect token launches from fake claims or private-key exposure?**

Gate 1 lint rejects banned terms and links outside the allowlist, and Gate 2 refuses any text that was edited after approval. There are no wallet keys, no signing and no auto-posting, no price, return or 'next X' claims, no safe, scam or rug verdicts, no wash-trading advice and no unsolicited DMs or holder tags. An ambiguous send is marked unknown and never retried automatically.
