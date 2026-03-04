#!/usr/bin/env python3
"""Fetch NZ roaster catalog snapshots into normalized JSONL records."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
import tempfile
import sys
from typing import Iterable
from urllib.parse import urljoin

from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BREW_METHOD_HINTS = {
    "espresso": "espresso",
    "filter": "filter",
    "plunger": "plunger",
    "aeropress": "aeropress",
    "cold brew": "cold_brew",
    "omni": "omni",
}

ROAST_LEVEL_HINTS = {
    "light": "light",
    "medium light": "medium_light",
    "medium": "medium",
    "medium dark": "medium_dark",
    "dark": "dark",
}


@dataclass
class Roaster:
    name: str
    base_url: str
    platform: str
    catalog_hint: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roasters", help="CSV roaster file (optional; auto-discover if omitted)")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--discover-max", type=int, default=20)
    return parser.parse_args()


def resolve_roaster_csv(roaster_csv: str | None, discover_max: int) -> str:
    if roaster_csv:
        return roaster_csv

    from discover_roasters import discover, write_csv

    tmp = tempfile.NamedTemporaryFile(prefix="nz_roasters_", suffix=".csv", delete=False)
    tmp.close()
    discovered = discover("new zealand coffee roasters online shop", discover_max)
    write_csv(tmp.name, discovered)
    return tmp.name

def load_roasters(path: str) -> list[Roaster]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [Roaster(**row) for row in reader]


def infer_brew_methods(text: str) -> list[str]:
    lowered = text.lower()
    methods = [normalized for key, normalized in BREW_METHOD_HINTS.items() if key in lowered]
    return methods or ["unknown"]


def infer_roast_level(text: str) -> str:
    lowered = text.lower()
    for key, normalized in sorted(ROAST_LEVEL_HINTS.items(), key=lambda x: -len(x[0])):
        if key in lowered:
            return normalized
    return "unknown"


def extract_notes(text: str) -> str:
    pattern = re.compile(r"(?:notes?|tasting notes?)\s*[:\-]\s*(.+)", re.IGNORECASE)
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def fetch_shopify_products(roaster: Roaster, timeout: int) -> Iterable[dict]:
    endpoint = urljoin(roaster.base_url, "/products.json?limit=250")
    with urlopen(endpoint, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("products", [])


def product_to_record(roaster: Roaster, product: dict, snapshot_at: str) -> dict:
    body = re.sub(r"<[^>]+>", " ", product.get("body_html", ""))
    title = product.get("title", "")
    joined = f"{title} {body}"
    variants = product.get("variants") or []
    variant = variants[0] if variants else {}
    in_stock = any(v.get("available") is True for v in variants)
    return {
        "snapshot_at": snapshot_at,
        "roaster": roaster.name,
        "url": urljoin(roaster.base_url, f"/products/{product.get('handle', '')}"),
        "name": title,
        "sku": variant.get("sku") or f"{roaster.name}:{product.get('id')}",
        "brew_methods": infer_brew_methods(joined),
        "roast_level": infer_roast_level(joined),
        "origin": "",
        "process": "",
        "tasting_notes_raw": extract_notes(joined),
        "flavor_tags": [],
        "roast_date": None,
        "price_nzd": float(variant["price"]) if variant.get("price") else None,
        "in_stock": in_stock,
        "variant_titles_available": [v.get("title") for v in variants if v.get("available") is True],
        "variant_ids_available": [v.get("id") for v in variants if v.get("available") is True],
        "variants": [
            {
                "id": v.get("id"),
                "title": v.get("title"),
                "price": v.get("price"),
                "available": bool(v.get("available")),
                "grams": v.get("grams"),
            }
            for v in variants
        ],
    }


def main() -> None:
    args = parse_args()
    roaster_csv = resolve_roaster_csv(args.roasters, args.discover_max)
    roasters = load_roasters(roaster_csv)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_at = dt.datetime.now(dt.timezone.utc).isoformat()

    records: list[dict] = []
    for roaster in roasters:
        if roaster.platform != "shopify":
            continue
        try:
            products = fetch_shopify_products(roaster, args.timeout)
            records.extend(product_to_record(roaster, product, snapshot_at) for product in products)
        except Exception as exc:  # noqa: BLE001
            records.append(
                {
                    "snapshot_at": snapshot_at,
                    "roaster": roaster.name,
                    "error": str(exc),
                    "url": roaster.base_url,
                }
            )

    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {output_path}")


if __name__ == "__main__":
    main()
