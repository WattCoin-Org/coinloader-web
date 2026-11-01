# Changelog

## 2026-11-01 — After You Buy strip on all 12 listing pages

Approved by owner AIguy. Status: committed to main locally, not yet pushed or deployed. Page commit `24b1652`.

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
