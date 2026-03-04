#!/usr/bin/env python3
"""Discover NZ coffee roasters from web search results.

If web discovery is blocked/rate-limited, fall back to a curated seed list.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

DUCKDUCKGO_HTML = "https://duckduckgo.com/html/?q={query}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Stable fallback list so the skill remains useful even when search is blocked.
FALLBACK_ROASTERS = [
    ("Coffee Supreme NZ", "https://coffeesupreme.com"),
    ("Flight Coffee", "https://flightcoffee.co.nz"),
    ("C4 Coffee", "https://c4coffee.co.nz"),
    ("People's Coffee", "https://peoplescoffee.co.nz"),
    ("Havana Coffee Works", "https://havana.co.nz"),
    ("Atomic Coffee Roasters", "https://atomiccoffee.co.nz"),
    ("Raglan Roast", "https://raglanroast.co.nz"),
    ("Red Rabbit Coffee Co", "https://redrabbitcoffee.co.nz"),
    ("Grey Roasting Co", "https://greyroastingco.com"),
]


@dataclass
class RoasterCandidate:
    name: str
    base_url: str
    platform: str = "shopify"
    catalog_hint: str = "/collections/coffee"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output CSV file")
    parser.add_argument(
        "--query",
        default="new zealand coffee roasters online shop",
        help="Search query for candidate discovery",
    )
    parser.add_argument("--max", type=int, default=20, help="Max discovered roasters")
    return parser.parse_args()


def normalize_base(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    return f"https://{host}"


def guess_name(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    stem = host.split(".")[0]
    return stem.replace("-", " ").title()


def is_nz_coffee_candidate(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return ".co.nz" in host or "newzealand" in host or "coffee" in host


def extract_urls_from_ddg(html_page: str) -> list[str]:
    """Extract destination URLs from DDG HTML search result links."""
    hrefs = re.findall(r'href="([^"]+)"', html_page)
    urls: list[str] = []
    for href in hrefs:
        if href.startswith("//duckduckgo.com") or href.startswith("/y.js"):
            continue
        if href.startswith("/l/?"):
            params = parse_qs(urlparse(href).query)
            if "uddg" in params:
                urls.append(html.unescape(params["uddg"][0]))
        elif href.startswith("http"):
            urls.append(html.unescape(href))
    return urls


def discover(query: str, limit: int) -> list[RoasterCandidate]:
    """Discover roasters from search; fall back to curated seeds on failure."""
    url = DUCKDUCKGO_HTML.format(query=query.replace(" ", "+"))
    req = Request(url, headers={"User-Agent": USER_AGENT})

    candidates: dict[str, RoasterCandidate] = {}
    try:
        with urlopen(req, timeout=25) as resp:
            html_page = resp.read().decode("utf-8", errors="replace")
        for candidate_url in extract_urls_from_ddg(html_page):
            if len(candidates) >= limit:
                break
            if not is_nz_coffee_candidate(candidate_url):
                continue
            base = normalize_base(candidate_url)
            host = urlparse(base).netloc
            if host in candidates or "duckduckgo.com" in host:
                continue
            candidates[host] = RoasterCandidate(name=guess_name(base), base_url=base)
    except Exception:
        # Silent fallback keeps cron flows resilient when search intermittently fails.
        pass

    if not candidates:
        for name, base in FALLBACK_ROASTERS[:limit]:
            host = urlparse(base).netloc
            candidates[host] = RoasterCandidate(name=name, base_url=base)

    return list(candidates.values())


def write_csv(path: str, candidates: list[RoasterCandidate]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "base_url", "platform", "catalog_hint"])
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.__dict__)


def main() -> None:
    args = parse_args()
    rows = discover(args.query, args.max)
    write_csv(args.out, rows)
    print(f"Discovered {len(rows)} roaster candidates -> {args.out}")


if __name__ == "__main__":
    main()
