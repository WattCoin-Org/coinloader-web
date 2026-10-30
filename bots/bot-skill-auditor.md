# Bot & Skill Security Auditor — Prompt Injection Scan

> AI skill security auditor for Grok Bot ($29 SOL). Line-cited 5-bucket static SKILL.md inspector for prompt injection, secret reads, webhooks & escalation.

- SKU: `bot-skill-auditor`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/bot-skill-auditor.html
- Markdown: https://coinloader.com/bots/bot-skill-auditor.md

## When to use

Use when an agent needs a static security review of a third-party skill or bot before running it.

Inputs: skill or bot files, or a repo

Outputs: line-cited findings in 5 buckets with a Files Audited / Skipped scope note

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "bot-skill-auditor", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# Bot & Skill Security Auditor — Line-Cited 5-Bucket Static Inspector for AI Skills & Repos

See every network call, credential read, prompt-bypass instruction, and shell command in a third-party SKILL.md or GitHub repository—with exact file paths and line numbers—before you run it. Executes read-only inside /workspace via .wattcoin_audit_prep.py.

 SKU: `bot-skill-auditor` · Skills: `auditor-setup + bot-skill-auditor` · Registry Name: *AI Skill & SKILL.md Static Security Auditor*

## Architecture, Data Sources & Execution Capabilities

- Bucket 1 — Prompt, Confirmation & Auditor Bypass: Flags hidden HTML comments, invisible/bidirectional Unicode characters, and instructions that attempt to override user confirmation rules or suppress scanner findings.
- Bucket 2 — Secret, Filesystem, Self-Modification & Persistence Access: Cites every read of ~/.ssh, ~/.aws, .env, .wattcoin_env, credential stores, crontab/systemd persistence, or modifications to SKILL.md and shell profiles.
- Bucket 3 — Outbound Network, Exfiltration & MCP Connectors: Catalogs every curl/wget/fetch URL, webhook endpoint, and MCP tool call—and explicitly traces combined data-path flows where secret reads (Bucket 2) feed outbound network calls (Bucket 3).
- Bucket 4 & Bucket 5 — Unverifiable Runtime Execution, Obfuscation & Local Machine Escalation: Flags curl | sh pipes, unpinned npx/pip packages, base64/hex blobs, and any use of ListMachines, machineId, CopyToBox, CopyFromBox, or request_smart_mode_approval.
- Hardened Prep Helper (.wattcoin_audit_prep.py): Runs at chmod 500 with /usr/bin/python3 -I, pins GitHub branches to 40-char commit SHAs, enforces 50-file / 100 KB per-file / 250 KB aggregate caps, and wraps untrusted file contents in random <untrusted_artifact_<16-hex>> tags.

## What This Bot Does Not Do (Mandatory Refusal Boundaries)

- Never executes audited code, scripts, or shell commands found inside target skills or repositories.
- Never curls or fetches URLs embedded inside audited files.
- Never reads /workspace/.wattcoin_env into model context or echoes wck_... / wcl_... credentials in chat.
- Never issues a 'Safe', 'Pass', checkmark certification badge, or numeric security score—always prepends SCOPE_NOTE.txt verbatim and logs exact Files Audited vs. Files Skipped.

## Turn-1 `/workspace` Onboarding & Non-Custodial Licensing

 Every template on CoinLoader.com executes locally inside your isolated Grok Bot Linux sandbox (`/workspace`). Credentials are stored in `/workspace/.wattcoin_env` with `0600` permissions (`-rw-------`) and never echoed in chat. Paid licenses are settled once on-chain in SOL via `POST https://www.wattcoin.org/api/v1/agents/license/quote` and `/purchase`, issue a private `wcl_...` bearer code, and support up to **3 automatic workspace-reset rebinds** via `POST https://www.wattcoin.org/api/v1/agents/license/claim`.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — Bot & Skill Security Auditor

**Does the Bot & Skill Security Auditor execute the code it inspects?**

Never. It is a strictly static, read-only inspector. Target files are normalized and wrapped in random <untrusted_artifact_<16-hex>> tags by /workspace/.wattcoin_audit_prep.py (chmod 500) and never executed.

**Why doesn't the report give a 'Safe' or '100/100 Pass' badge?**

Static analysis can only verify what is present in the files at audit time. It cannot see dynamically fetched remote payloads whose server responses change later, delayed API prompt injections, or off-file maintainer compromise. Every report prepends SCOPE_NOTE.txt and cites exact line numbers instead of issuing false safety guarantees.

**Can I use my $29 SOL license across both BotAppStore and CoinLoader?**

Yes. The SKU identifier (bot-skill-auditor) and WattCoin Registry license endpoints are shared across both storefronts, and every wcl_... license includes up to 3 workspace-reset rebinds.
