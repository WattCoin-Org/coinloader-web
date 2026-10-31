#!/usr/bin/env python3
"""Assert sitemap.xml lists exactly the self-canonical pages (no cross-canonical or missing pages)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "https://coinloader.com"
CANON_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"')


def self_canonical_urls():
    """Return {canonical_url: relative_path} for pages whose canonical is on this host, plus cross-canonical pages."""
    pages = [ROOT / "index.html"] + sorted(ROOT.glob("*.html")) + sorted((ROOT / "bots").glob("*.html"))
    own, other = {}, {}
    for page in dict.fromkeys(pages):
        m = CANON_RE.search(page.read_text(encoding="utf-8"))
        rel = page.relative_to(ROOT).as_posix()
        if not m:
            other[rel] = None
        elif m.group(1).startswith(HOST):
            own[m.group(1)] = rel
        else:
            other[rel] = m.group(1)
    return own, other


def main():
    errors = []
    locs = set(re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8")))
    own, other = self_canonical_urls()
    for url in sorted(set(own) - locs):
        errors.append(f"{own[url]}: self-canonical but missing from sitemap ({url})")
    for url in sorted(locs - set(own)):
        errors.append(f"sitemap lists {url}, which is not a self-canonical page")
    for rel, canon in sorted(other.items()):
        if canon is None:
            errors.append(f"{rel}: no canonical link")
    for e in errors:
        print("FAIL:", e)
    if errors:
        return 1
    print(f"OK: sitemap lists {len(locs)} self-canonical pages; {len(other)} cross-canonical pages excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
