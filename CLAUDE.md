# coinloader-web

Public storefront for CoinLoader: a static site of Grok Bot templates, focused on crypto/on-chain agent tools.

## Live site and domain

- Production: https://coinloader.com
- Vercel project: `coinloader-web` (`prj_gt9g6btLKGFhDgxUsux5DXPCsrAI`), team `team_LdUED0dxFkZpHgDDRWJ2s9Xl`
- `/runtime/:script` is rewritten to the Railway license server at `https://wattcoin-production-81a7.up.railway.app/api/v1/agents/license/runtime/:script?format=raw`

## Build and deploy

- No bundler: static HTML, CSS, JS, and Markdown at the repo root. Vercel serves the repository as a static site.
- Push to `main` auto-deploys to Vercel production. Do not force-push.
- This `CLAUDE.md` stays at the repo root so Claude Code can read it. Because the root *is* the deploy output, the file would be public at `/CLAUDE.md` unless excluded. `.vercelignore` keeps it out of the Vercel upload, and `vercel.json` rewrites `/CLAUDE.md` so it is not served. Never move it into a served directory.

## Key files and directories

- `index.html`, `about.html`, `contact.html`, `privacy.html` — plus Markdown twins (`index.md`, `about.md`, …)
- `bots/` — listing pages (HTML + Markdown twins)
- `app.js`, `styles.css`, `catalog.json` — checkout UI, styles, catalog
- `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`
- `middleware.js` — Markdown `Accept` negotiation for page URLs
- `vercel.json`, `scripts/` — deploy config and check scripts

## Storefront rules

- CoinLoader checkout is SOL-only. Do not add Stripe or card checkout.
- WATT is optional and must stay off this storefront's checkout and payment framing.
- Product pages include the Grok Bot plan requirement and per-store refund terms; keep those accurate, do not invent policy text.
- Runtime/license API calls still go through the shared WattCoin license server (that is infrastructure, not a storefront brand change).

## Standing rules

- Identify the owner only as AIguy. Never write a legal name into files, commit messages, or site copy.
- Never put secrets in files (no API keys, tokens, webhook URLs, private credentials, or Stripe secret values). Live IDs that are already public (site URLs, Vercel project ids recorded in HANDOFF) are fine.
- CoinLoader is SOL-only: no Stripe or card checkout. Card payments are only on BotAppStore.
- WATT is optional and must be kept separate from BotAppStore and CoinLoader (no WATT/Solana/wallet checkout framing on BotAppStore; do not mix WATT into CoinLoader checkout).
- No unbacked test-count claims in public copy.
- Show diffs and get review before pushing to main.
- Note which bot made the change in the commit message (commits land as WattCoin-Org).
- Keep the Decisions log below short; append new decisions instead of rewriting history.

## Live context

For current IDs, deploys, SKUs, and infrastructure state, read `/workspace/GROKBOTHANDOFF.md` on this box. Do not invent facts that are not in this file, the repo, or GROKBOTHANDOFF.

## Decisions log

- 2026-11-12 (America/New_York): Added this CLAUDE.md so Claude Code sessions keep project context across bots. Public deploy must not serve this file. Per-repo session helper: `/workspace/claude-sessions/claude-repo`. (Programmer bot)

