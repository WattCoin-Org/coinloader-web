# Changelog

## 2026-11-05 — solana-token-scanner display name renamed to Retail Token Due-Diligence Bot

Renamed the `solana-token-scanner` display name to Retail Token Due-Diligence Bot (catalog + after-buy button). Approved by owner AIguy. No price, sku or URL changes.

## 2026-11-04 — Bot-page checkout/fulfilled panel copy-paste leftovers corrected

Scope: checkout modal only (`#checkout-price-usd` placeholder, sku line, fulfilled Step A template name, CTA text). Prices checked against the backend price table and `catalog.json`; no backend, template URL, nav or cross-sell changes.

### Changes
- `bots/btc-utxo-hygiene.html`: placeholder `$29.00` -> `$19.00`; sku line, Step A name and CTA were Bot & Skill Security Auditor.
- `bots/evm-approval-auditor.html`: placeholder `$29.00` -> `$19.00`; sku line, Step A name and CTA were Auditor.
- `bots/solana-wallet-hygiene.html`: placeholder `$29.00` -> `$19.00`; sku line, Step A name and CTA were Auditor.
- `bots/cost-basis-ledger.html`, `bots/evm-contract-inspector.html`, `bots/hyperliquid-monitor.html`, `bots/pumpfun-coin-manager.html`, `bots/solana-token-scanner.html`, `bots/token-launch-command-center.html`, `bots/token-rugscore.html`: sku line, Step A name and CTA were Auditor (price $29/$49 placeholders were correct).
- `bots/web-text-extractor.html`: free bot (catalog price 0, sku `web-extractor`) with a leftover paid Auditor panel; placeholder `$29.00` -> `$0.00`, sku line, Step A name and CTA corrected.

### Checks
- `bots/bot-skill-auditor.html` already correct.

## 2026-11-04 — TLCC checkout placeholder price corrected

### Changes
- `bots/token-launch-command-center.html`: checkout modal placeholder `#checkout-price-usd` changed from `$29.00 USD` to `$49.00 USD`, matching the canonical $49 price (backend price table, JSON-LD, badge and buy buttons).

### Checks
- No other `bots/*.html` page with a 49.00 JSON-LD price carried a stale `$29.00` placeholder.

## 2026-11-01 — bot-skill-auditor canonical moved to coinloader.com

Approved by owner AIguy. Status: merged to main; production deploy verification pending.

### Changes
- `bots/bot-skill-auditor.html`: `<link rel="canonical">` and `og:url` now point at `https://coinloader.com/bots/bot-skill-auditor.html` (were botappstore.com). All other og: / twitter: / JSON-LD URLs on the page already pointed at coinloader.com.
- `sitemap.xml`: new entry for the page (lastmod 2026-11-01, weekly, priority 0.9), placed after web-text-extractor, so `check_sitemap.py` sees sitemap == self-canonical pages (16 listed).
- No script, `.md` twin or llms changes were needed (`build_markdown.py --check` reports twins up to date).

### Kept on purpose
- Footer "sister storefront" links to botappstore.com are unchanged.

### Checks
- check_analytics OK (16), check_catalog OK (12), check_nav OK (12), check_sitemap OK (16 self-canonical, 0 cross-canonical excluded), build_markdown --check OK (16 twins up to date).
- `rg -n 'botappstore\.com' --glob '*.html' . | rg -i 'canonical|og:|twitter:'` returns nothing.

Commit: `85e56c1` (changelog lands in a follow-up commit)

## 2026-11-01 — web-text-extractor canonical moved to coinloader.com

Approved by owner AIguy. Status: merged to main; production deploy verification pending.

### Changes
- `bots/web-text-extractor.html`: `<link rel="canonical">` and `og:url` now point at `https://coinloader.com/bots/web-text-extractor.html` (were botappstore.com). All other og: / twitter: / JSON-LD URLs on the page already pointed at coinloader.com.
- `sitemap.xml`: new entry for the page (lastmod 2026-11-01, weekly, priority 0.9), so `check_sitemap.py` sees sitemap == self-canonical pages (15 listed).
- No `.md` twin or llms changes were needed (`build_markdown.py` wrote 0 files; llms files never claimed a botappstore.com canonical).

### Kept on purpose
- `bots/bot-skill-auditor.html` keeps its cross-canonical to botappstore.com (not approved for change) and stays out of the sitemap.
- No WattCoin sweep here; CoinLoader may mention it.

### Checks
- check_analytics OK (16), check_catalog OK (12), check_nav OK (12), check_sitemap OK (15 self-canonical, 1 cross-canonical excluded), build_markdown --check OK (16). No test suite in this repo.
- `rg 'canonical|og:url' bots/ *.html | rg botappstore` shows only `bots/bot-skill-auditor.html` (lines 8 and 16).
- check_sitemap OK (15 self-canonical, 1 cross-canonical excluded); rollout QA 54 renders, 0 failing.

### Commit
- `8bd432a` page + sitemap (changelog commit follows)

## 2026-11-01 — After You Buy strip on all 12 listing pages

Approved by owner AIguy. Status: merged to main and live in production. Page commit `24b1652`, changelog commit `0515205`. Production deploy `dpl_HSDJpwMzgKmv5kbo2NptZcKx6NPp` READY. Live check on coinloader.com (`token-rugscore`, `hyperliquid-monitor`, `token-launch-command-center`, `web-text-extractor`, `bot-skill-auditor`): the strip appears exactly once on each.

### Changes (`bots/*.html` only, 12 pages)
- New "After You Buy" section directly above "Licensing & Setup" on every listing: 1) check out, 2) add the bot to the Grok Bot sidebar, 3) run setup with the activation prompt, 4) first report. Payment step reads "Pay by card or SOL", as the pages and `app.js` offer both.
- Steps 3 and 4 are written per bot from its setup skill (runtime download vs read-only helpers, multi-file toolkit for `token-launch-command-center`). `token-rugscore` uses the approved text.
- `web-text-extractor` is free, so it gets "After You Install": no checkout, no license code, 10 free text scrapes per UTC day.
- Scoped `<style>` block using existing page variables (`--accent-cyan` for the step numbers); steps stack on phones. No JS, checkout logic, prices, SKUs, catalog, sitemap, llms files or `.md` twins were touched (`build_markdown.py` ignores the new section).

### Checks
- Playwright at 1280 and 390 px on all 12 pages (local server, external requests blocked): strip present once, directly before `#licensing-flow`, strip does not overflow, text at least body size. The 1280 px header button overflow that already exists on the pages is unchanged.
- Greps on the strip blocks: none of safe, guarantee, profit, human review, Stripe, MoonPay, BotAppStore, or time units.
- Checkout modal and mocked receipt on `token-rugscore`: names, price and steps follow the clicked bot after `app.js` runs; no Auditor text.
- Guards: check_analytics OK (16), check_catalog OK (12), check_nav OK (12), check_sitemap OK (14), build_markdown --check OK (16 up to date).

### Commit
- 24b1652 (12 listing pages)

## 2026-10-31 — Mobile optimization (CSS only)

Approved by owner AIguy. Status: merged to main and live in production. Merge commit `07576c5` (`feat/mobile-optimization` @ `1dfc1e3` into main). Production deploy `dpl_3eFziNYYAGECf7Ftdg4GMZkH55VQ` READY. Rollback deploy (previous production, `e87bc3a`): `dpl_8kacdfpZ5s25dXRsHNrdn6cEaTRQ`.

### Changes (`styles.css` only)
- Removed the root causes of horizontal overflow at 360/390/414 px: status bar and ticker no longer force one line, hero card, architecture cards, FAQ list and nav button group can shrink and wrap, grids collapse to one column, long inline code wraps, code blocks and tables scroll inside their own box.
- `body{overflow-x:hidden}` is kept; a base `img,svg,video{max-width:100%}` rule was added.
- Tap targets on phones (max-width 680px): buttons, filter pills, copy buttons, modal close, nav links, menu items, footer links and card titles are at least 44px tall. Inline links inside paragraphs are unchanged.
- Checkout modal: fits inside the viewport at 360 px (8px margin, scrolls inside, tighter padding, full-width action buttons, long values wrap, inputs 44px tall and 16px text).
- Type floor of 12px for small labels and badges on phones.
- Buy and install buttons share one row, full width below 480px.
- No HTML, JS, checkout logic, prices, SKUs, analytics, nav labels or links, sitemap, meta tags, catalog, llms files or `.md` twins were touched.
- Follow-up: header and bot-page buttons can no longer clip their text at 360/390/414 px. Buy and install buttons now stack one per row (full width, at least 44px tall) at 480px and below, and button text wraps and centers instead of staying on one line at 680px and below. Verified on every page, including the checkout modal (0 clipped or out-of-viewport buttons, no horizontal overflow).

### Checks (local static server of the branch, 360/390/414 px)
- scrollWidth equals the viewport width on every audited page (before: 500-558 px).
- Checkout modal: before 514 px wide, clipped; after fully inside the viewport at all widths.
- Remaining small tap targets: inline paragraph links only (73-80 per home page; now 1-5 per page).
- Guards and tests: all pass.

### Production
- Guards pass on main: check_nav 12, check_sitemap 14, check_analytics 16, check_catalog 12.
- Live check (playwright, 360/390/414 px, home + `/bots/cost-basis-ledger.html`): document and body scrollWidth equal the viewport width on all 6 runs, buy/checkout buttons render (15 on home, 2 on bot page), 0 clipped, minimum height 44px.
- Live `styles.css` sha256 matches repo main.

### Commit
- 8a70193 (styles.css)
