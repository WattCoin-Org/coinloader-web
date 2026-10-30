# Web & API Text Extractor for Grok Bot (Free) | CoinLoader

> Free self-onboarding web & JSON endpoint text scraper for Grok Bot. Provisions a 0600 wck_ key on Turn 1, grants 100 WATT, and runs 10 free scrapes/UTC day.

- SKU: `web-extractor`
- Price: Free
- Page: https://coinloader.com/bots/web-text-extractor.html
- Markdown: https://coinloader.com/bots/web-text-extractor.md

## When to use

Use when an agent needs readable text from a public web page or API response.

Inputs: a public URL

Outputs: clean text (html/json modes are paid per call in WATT)

## How an agent buys

This product is free; no purchase is required.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Web & API Text Extractor — Free Grok Bot Web Scraper & 100 WATT Starter Kit

Self-onboarding readable text and documentation extractor for Grok Bot (skills: getting-started + web-extractor). Provisions its own wck_... key into /workspace/.wattcoin_env (chmod 600) on Turn 1, activates a 100 WATT starter grant, and provides 10 free static-HTTP + BeautifulSoup text scrapes per UTC day with automatic local curl fallback.

 Skills: `getting-started + web-extractor` · Template ID: `k1oyHmw4iS4VBW1U8_3Ol`

## Architecture, Data Sources & Execution Capabilities

- Turn-1 Auto-Provisioning (getting-started): Calls POST https://www.wattcoin.org/api/v1/agents/register, writes WATTCOIN_AGENT_KEY to /workspace/.wattcoin_env (0600 permissions), and completes onboarding_v1 (25 WATT) + starter_v1 (75 WATT) for 100 WATT total.
- 10 Free Cloud Text Scrapes / UTC Day (web-extractor): Calls POST https://www.wattcoin.org/api/v1/scrape with format: 'text' (static HTTP + BeautifulSoup readable text extraction) and reports X-Quota-Limit: 10 and X-Quota-Remaining headers.
- Paid On-Chain Modes & Automatic Local Fallback: Supports 100 WATT/call html and json modes (never spends WATT without explicit user confirmation) and falls back to local curl -sL + Python HTML-to-text in /workspace when daily quota resets at UTC midnight.
- SSRF & Secret Protection: Rejects loopback (127.0.0.0/8, ::1), RFC1918 private IPs, link-local, and cloud metadata (169.254.169.254) with HTTP 400, and never echoes secret wck_... keys in chat.

## What This Bot Does Not Do (Mandatory Refusal Boundaries)

- Never claims headless-browser or client-side JavaScript SPA rendering on the static HTTP cloud endpoint (requests.get + BeautifulSoup, 15s timeout, 2 MB response cap).
- Never prints or echoes WATTCOIN_AGENT_KEY (wck_...) in chat output.
- Never invokes paid 100 WATT/call html or json modes without explicit per-call user confirmation.
- Rejects loopback, private RFC1918, and cloud metadata SSRF targets with HTTP 400.

## Turn-1 `/workspace` Onboarding & Non-Custodial Licensing

 Every template on CoinLoader.com executes locally inside your isolated Grok Bot Linux sandbox (`/workspace`). Credentials are stored in `/workspace/.wattcoin_env` with `0600` permissions (`-rw-------`) and never echoed in chat. Paid licenses are settled once on-chain in SOL via `POST https://www.wattcoin.org/api/v1/agents/license/quote` and `/purchase`, issue a private `wcl_...` bearer code, and support up to **3 automatic workspace-reset rebinds** via `POST https://www.wattcoin.org/api/v1/agents/license/claim`.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Web & API Text Extractor

**Is the Web & API Text Extractor really free forever?**

Yes. The template is 100% free ($0) and includes 10 free cloud text extractions per UTC day on POST https://www.wattcoin.org/api/v1/scrape plus a one-time 100 WATT starter grant (25 WATT from onboarding_v1 + 75 WATT from starter_v1) and unlimited local curl + Python fallback in /workspace.

**Where is my wck_... agent key stored?**

Your agent key is written to /workspace/.wattcoin_env with chmod 600 (-rw-------) permissions inside your isolated Grok Bot Linux sandbox and is never printed in chat.

**Does it render client-side JavaScript SPAs?**

No. Both the cloud /api/v1/scrape endpoint and the local /workspace fallback use deterministic static HTTP fetches + BeautifulSoup HTML-to-text parsing (15-second timeout, 2 MB cap) and never make false headless-browser claims.
