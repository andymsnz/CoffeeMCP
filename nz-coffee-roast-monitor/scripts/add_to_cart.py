#!/usr/bin/env python3
"""Build Shopify cart URL(s) from catalog snapshots.

Defaults to in-stock variants and attempts to match requested grind first.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Catalog JSONL from fetch_roasts.py")
    p.add_argument("--roaster", required=True, help='Roaster name, e.g. "Grey Roasting Co"')
    p.add_argument("--items", required=True, nargs="+", help="Item name keywords (3 recommended)")
    p.add_argument("--qty", type=int, default=1, help="Quantity per selected item")
    p.add_argument(
        "--grind",
        default="FILTER",
        help="Preferred variant title keyword, e.g. FILTER, WHOLE BEANS",
    )
    p.add_argument(
        "--allow-oos",
        action="store_true",
        help="Allow out-of-stock items (not recommended; use watchlist flow instead)",
    )
    return p.parse_args()


def load_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if "sku" in row:
                rows.append(row)
    return rows


def pick_variant(row: dict, grind_pref: str, allow_oos: bool = False) -> dict | None:
    variants = row.get("variants") or []
    if not variants:
        return None

    candidates = variants if allow_oos else [v for v in variants if v.get("available")]
    if not candidates:
        return None

    grind_upper = grind_pref.upper()
    for variant in candidates:
        if grind_upper in (variant.get("title") or "").upper():
            return variant
    return candidates[0]


def main() -> None:
    args = parse_args()
    rows = [
        row
        for row in load_rows(args.input)
        if (row.get("roaster") or "").lower() == args.roaster.lower()
    ]

    chosen: list[tuple[dict, dict]] = []
    for token in args.items:
        token_l = token.lower()
        candidates = [
            row
            for row in rows
            if token_l in (row.get("name") or "").lower() and (args.allow_oos or row.get("in_stock"))
        ]
        if not candidates:
            print(f"NOT_FOUND_OR_OOS: {token}")
            continue

        row = candidates[0]
        variant = pick_variant(row, args.grind, allow_oos=args.allow_oos)
        if not variant:
            print(f"NO_AVAILABLE_VARIANT: {row.get('name')}")
            continue
        chosen.append((row, variant))

    if not chosen:
        print("No matching items could be added to cart.")
        return

    # Build one cart URL per supplier domain.
    by_domain: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for row, variant in chosen:
        domain = urlparse(row.get("url", "")).netloc
        by_domain[domain].append((row, variant))

    for domain, items in by_domain.items():
        parts = [f"{variant['id']}:{args.qty}" for _, variant in items if variant.get("id")]
        cart_url = f"https://{domain}/cart/" + ",".join(parts)
        print("\nCART_URL:", cart_url)
        for row, variant in items:
            print(f"- {row.get('name')} [{variant.get('title')}] ${variant.get('price')}")


if __name__ == "__main__":
    main()
