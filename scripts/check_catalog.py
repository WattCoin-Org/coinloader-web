#!/usr/bin/env python3
"""Assert catalog.json is valid, leak-free, and consistent with the bot pages' Offer JSON-LD."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ["x.ai", "@", "$WATT", "mesh-printability", "stl-mesh-preflight",
             "shop-catalog-compiler", "wattcoin2026", "gmail"]
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def offer_price(html):
    """Return the Offer price (float) from the page's JSON-LD, or None."""
    def walk(node):
        if isinstance(node, dict):
            if node.get("@type") == "Offer" and "price" in node:
                return float(node["price"])
            for v in node.values():
                r = walk(v)
                if r is not None:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = walk(v)
                if r is not None:
                    return r
        return None
    for blob in LD_RE.findall(html):
        r = walk(json.loads(blob))
        if r is not None:
            return r
    return None


def main():
    errors = []
    raw = (ROOT / "catalog.json").read_text(encoding="utf-8")
    try:
        cat = json.loads(raw)
    except ValueError as e:
        print(f"FAIL: catalog.json is not valid JSON: {e}")
        return 1
    for bad in FORBIDDEN:
        if bad in raw:
            errors.append(f"forbidden string {bad!r} in catalog.json")

    slugs = {}
    for p in cat["products"]:
        m = re.search(r"/bots/([^/]+)\.html$", p["url"])
        if not m:
            errors.append(f"{p['sku']}: url has no /bots/<slug>.html: {p['url']}")
            continue
        slug = m.group(1)
        slugs[slug] = p["sku"]
        page = ROOT / "bots" / f"{slug}.html"
        if not page.exists():
            errors.append(f"{p['sku']}: missing page bots/{slug}.html")
            continue
        price = offer_price(page.read_text(encoding="utf-8"))
        if price is None:
            errors.append(f"{p['sku']}: no Offer price on bots/{slug}.html")
        elif price != float(p["price_usd"]):
            errors.append(f"{p['sku']}: catalog {p['price_usd']} != page Offer {price}")

    for page in sorted((ROOT / "bots").glob("*.html")):
        if page.stem not in slugs:
            errors.append(f"bots/{page.name} has no catalog product")

    for e in errors:
        print("FAIL:", e)
    if errors:
        return 1
    print(f"OK: {len(slugs)} products match bot pages (SKUs and Offer prices); no forbidden strings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
