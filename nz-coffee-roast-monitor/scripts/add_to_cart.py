#!/usr/bin/env python3
"""Build Shopify cart URL(s) from catalog snapshot for in-stock coffee items."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True, help='Catalog JSONL from fetch_roasts.py')
    p.add_argument('--roaster', required=True, help='Roaster name, e.g. "Grey Roasting Co"')
    p.add_argument('--items', required=True, nargs='+', help='Item name keywords (3 recommended)')
    p.add_argument('--qty', type=int, default=1)
    p.add_argument('--grind', default='FILTER', help='Variant title keyword preference (e.g. FILTER, WHOLE BEANS)')
    return p.parse_args()


def load_rows(path: str):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            o = json.loads(line)
            if 'sku' in o:
                rows.append(o)
    return rows


def pick_variant(row: dict, grind_pref: str):
    variants = row.get('variants') or []
    available = [v for v in variants if v.get('available')]
    if not available:
        return None
    gp = grind_pref.upper()
    for v in available:
        if gp in (v.get('title') or '').upper():
            return v
    return available[0]


def main() -> None:
    args = parse_args()
    rows = [r for r in load_rows(args.input) if (r.get('roaster') or '').lower() == args.roaster.lower()]

    chosen = []
    for token in args.items:
        token_l = token.lower()
        candidates = [r for r in rows if token_l in (r.get('name') or '').lower() and r.get('in_stock')]
        if not candidates:
            print(f'NOT_FOUND_OR_OOS: {token}')
            continue
        row = candidates[0]
        variant = pick_variant(row, args.grind)
        if not variant:
            print(f'NO_AVAILABLE_VARIANT: {row.get("name")}')
            continue
        chosen.append((row, variant))

    if not chosen:
        print('No in-stock items matched.')
        return

    # group by domain for one cart per supplier domain
    by_domain = defaultdict(list)
    for row, variant in chosen:
        domain = urlparse(row.get('url')).netloc
        by_domain[domain].append((row, variant))

    for domain, items in by_domain.items():
        parts = [f"{v['id']}:{args.qty}" for _, v in items if v.get('id')]
        cart_url = f"https://{domain}/cart/" + ','.join(parts)
        print('\nCART_URL:', cart_url)
        for row, variant in items:
            print(f"- {row.get('name')} [{variant.get('title')}] ${variant.get('price')}")


if __name__ == '__main__':
    main()
