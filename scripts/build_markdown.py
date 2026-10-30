#!/usr/bin/env python3
"""Generate Markdown twins (index.md, bots/<slug>.md) from the HTML pages and catalog.json.

Usage:
  python3 scripts/build_markdown.py          # (re)write the .md files; idempotent
  python3 scripts/build_markdown.py --check  # exit 1 if any .md is missing or stale
"""
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://coinloader.com"
SKIP_TAGS = {"script", "style", "svg", "button", "pre", "nav", "form", "noscript", "head"}
SKIP_CLASSES = {"product-cta-row", "dual-runtime-pill", "card-actions", "price-badge", "breadcrumb-nav"}
BOT_SECTIONS = {"capabilities", "refusal-boundaries", "licensing-flow", "product-faq"}
INDEX_SECTIONS = {"featured-bot", "catalog", "bundles", "architecture", "faq"}
VOID = {"br", "img", "hr", "meta", "link", "input"}


class Converter(HTMLParser):
    """Convert the allowed <section>s of a page into Markdown."""

    def __init__(self, allowed_ids, first_section_ok):
        super().__init__(convert_charrefs=True)
        self.allowed = allowed_ids
        self.first_ok = first_section_ok
        self.out = []
        self.stack = []        # (tag, skipping)
        self.skip_depth = 0
        self.sec_depth = 0     # >0 while inside an included section
        self.sec_seen = 0
        self.links = []        # open <a> hrefs (None if dropped)
        self.list_stack = []

    def _emit(self, s):
        if self.sec_depth and not self.skip_depth:
            self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in VOID:
            if tag == "br":
                self._emit("  \n")
            return
        classes = set((a.get("class") or "").split())
        skipping = tag in SKIP_TAGS or bool(classes & SKIP_CLASSES) or "hidden" in a
        if tag == "section" and not self.sec_depth:
            self.sec_seen += 1
            ok = (a.get("id") in self.allowed) or (self.sec_seen == 1 and self.first_ok)
            self.stack.append((tag, False, ok))
            if ok:
                self.sec_depth = 1
            return
        self.stack.append((tag, skipping, False))
        if skipping:
            self.skip_depth += 1
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self._emit("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "section", "details", "table", "tr"):
            self._emit("\n\n")
        elif tag == "summary":
            self._emit("\n\n**")
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
            self._emit("\n")
        elif tag == "li":
            lt = self.list_stack[-1] if self.list_stack else ["ul", 0]
            lt[1] += 1
            self._emit("\n" + ("  " * max(len(self.list_stack) - 1, 0)) + (f"{lt[1]}. " if lt[0] == "ol" else "- "))
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "a":
            href = a.get("href") or ""
            if href.startswith("mailto:") or "x.ai/" in href or href.startswith("javascript:"):
                href = None
            elif href.startswith("#") or href.startswith("/"):
                href = SITE + (href if href.startswith("/") else "/" + href) if not href.startswith("#") else None
            self.links.append(href)
            self._emit("[" if href else "")
        elif tag in ("td", "th"):
            self._emit(" ")

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack:
            return
        while self.stack and self.stack[-1][0] != tag:
            self.stack.pop()
        if not self.stack:
            return
        _, skipping, opened = self.stack.pop()
        if tag == "section" and opened:
            self.sec_depth = 0
            self.out.append("\n\n")
            return
        if skipping:
            self.skip_depth -= 1
            return
        if tag == "summary":
            self._emit("**")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self._emit("\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "a":
            href = self.links.pop() if self.links else None
            self._emit(f"]({href})" if href else "")
        elif tag in ("h1", "h2", "h3", "h4", "p", "details"):
            self._emit("\n")

    def handle_data(self, data):
        self._emit(re.sub(r"\s+", " ", data))

    def markdown(self):
        text = "".join(self.out)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\*\*\s*\*\*", "", text)
        text = re.sub(r"`?(?:https?://)?x\.ai/bot/[^\s`)]*`?(?:\s*↗)?", "<template link>", text)
        text = re.sub(r"(<template link>)(\s*<template link>)+", r"\1", text)
        text = re.sub(r"(?m)^(#+) +", r"\1 ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def meta(src, pattern):
    m = re.search(pattern, src, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def convert(src, allowed, first_ok):
    c = Converter(allowed, first_ok)
    c.feed(src)
    return c.markdown()


def price_of(p):
    return "Free" if not p["price_usd"] else f"${p['price_usd']:g} USD (one-time)"


def checkout_block(cat, product=None):
    card = cat["checkout"]["card"]
    sol = cat["checkout"]["sol"]
    sku = product["sku"] if product else "<sku>"
    lines = ["## How an agent buys", ""]
    if product and not product["price_usd"]:
        lines += ["This product is free; no purchase is required.", ""]
    else:
        lines += [
            f"- Price: {price_of(product)}" if product else "- Prices: see the catalog.",
            f"- Card (default): `{card['method']} {card['url']}` with body `{{\"sku\": \"{sku}\", \"storefront\": \"coinloader\"}}` "
            f"returns a `checkout_url` (hosted page; a human completes payment). "
            f"After payment: `{card['license_lookup']}` returns the license code.",
            f"- SOL: `{sol['quote']}` then `{sol['confirm']}`. {sol['note']}",
        ]
        lines.append("")
    lines += [f"Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): {SITE}/catalog.json",
              f"Plain-text catalog: {SITE}/llms.txt"]
    return "\n".join(lines)


def build_bot(path, cat, by_slug):
    src = path.read_text(encoding="utf-8")
    slug = path.stem
    p = by_slug[slug]
    title = meta(src, r"<title>(.*?)</title>")
    desc = meta(src, r'<meta name="description" content="(.*?)"')
    body = convert(src, BOT_SECTIONS, True)
    parts = [f"# {title}", "", f"> {desc}", "",
             f"- SKU: `{p['sku']}`", f"- Price: {price_of(p)}", f"- Page: {SITE}/bots/{slug}.html",
             f"- Markdown: {SITE}/bots/{slug}.md", "",
             "## When to use", "", p["when_to_use"], ""]
    if p.get("inputs"):
        parts += ["Inputs: " + "; ".join(p["inputs"]), ""]
    if p.get("outputs"):
        parts += ["Outputs: " + "; ".join(p["outputs"]), ""]
    parts += [checkout_block(cat, p), "", "---", "", body, ""]
    return "\n".join(parts)


def build_index(cat):
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    title = meta(src, r"<title>(.*?)</title>")
    desc = meta(src, r'<meta name="description" content="(.*?)"')
    parts = [f"# {title}", "", f"> {desc}", "", f"- Page: {SITE}/", f"- Markdown: {SITE}/index.md", "",
             "## Catalog", ""]
    for p in cat["products"]:
        parts.append(f"- [{p['name']}]({SITE}/bots/{Path(p['url']).stem}.md) — {price_of(p)} — `{p['sku']}` — {p['when_to_use']}")
    if cat.get("bundles"):
        parts += ["", "## Bundles", ""]
        for b in cat["bundles"]:
            parts.append(f"- {b['name']} — ${b['price_usd']:g} USD — `{b['sku']}` — includes: {', '.join(b['includes'])}")
    parts += ["", checkout_block(cat), "", "---", "", convert(src, INDEX_SECTIONS, False), ""]
    return "\n".join(parts)


TRUST_PAGES = ("about", "contact", "privacy")

# The HTML talks about a button; in Markdown there is no button, so point at the page instead.
# The address itself is never printed here.
MD_REWRITES = [
    ("Reveal the support email with one click.",
     "The support address is not printed in this file."),
    ("The address is hidden from automated scrapers to cut down on spam. Click the button to reveal it.",
     f"The support address is not printed here to limit spam. Open {SITE}/contact in a browser and use the Show support email button."),
]


def build_trust(slug):
    src = (ROOT / f"{slug}.html").read_text(encoding="utf-8")
    title = meta(src, r"<title>(.*?)</title>")
    desc = meta(src, r'<meta name="description" content="(.*?)"')
    main = re.search(r"<main[^>]*>(.*?)</main>", src, re.S).group(1)
    c = Converter(set(), False)
    c.sec_depth = 1
    c.feed(main)
    text = "\n".join([f"# {title}", "", f"> {desc}", "", f"- Page: {SITE}/{slug}",
                      f"- Markdown: {SITE}/{slug}.md", "", "---", "", c.markdown(), ""])
    for old, new in MD_REWRITES:
        text = text.replace(old, new)
    return text


def targets():
    cat = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    by_slug = {Path(p["url"]).stem: p for p in cat["products"]}
    out = {ROOT / "index.md": build_index(cat)}
    for page in sorted((ROOT / "bots").glob("*.html")):
        out[ROOT / "bots" / f"{page.stem}.md"] = build_bot(page, cat, by_slug)
    for slug in TRUST_PAGES:
        out[ROOT / f"{slug}.md"] = build_trust(slug)
    return out


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for path, text in targets().items():
        text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
        cur = path.read_text(encoding="utf-8") if path.exists() else None
        if cur != text:
            stale.append(path.relative_to(ROOT))
            if not check:
                path.write_text(text, encoding="utf-8")
    if check:
        if stale:
            print("STALE or missing:", *map(str, stale), sep="\n  ")
            return 1
        print(f"OK: {len(targets())} markdown twins up to date")
        return 0
    print(f"wrote {len(stale)} file(s); {len(targets()) - len(stale)} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
