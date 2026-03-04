#!/usr/bin/env python3
"""Fetch NZ roaster catalog snapshots into normalized JSONL records.

Adapters:
- Shopify (`/products.json`)
- WooCommerce Store API (`/wp-json/wc/store/products`)
- Generic JSON-LD Product fallback from catalog pages
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

USER_AGENT = "Mozilla/5.0 (compatible; CoffeeMCP/1.0)"

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


def http_get_text(url: str, timeout: int) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


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


def normalize_record(
    roaster: Roaster,
    snapshot_at: str,
    url: str,
    name: str,
    body_text: str,
    variants: list[dict],
    sku_fallback: str,
) -> dict:
    joined = f"{name} {body_text}"
    variant = variants[0] if variants else {}
    in_stock = any(v.get("available") is True for v in variants)
    return {
        "snapshot_at": snapshot_at,
        "roaster": roaster.name,
        "url": url,
        "name": name,
        "sku": variant.get("sku") or sku_fallback,
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
        "variants": variants,
    }


def fetch_shopify_records(roaster: Roaster, timeout: int, snapshot_at: str) -> list[dict]:
    endpoint = urljoin(roaster.base_url, "/products.json?limit=250")
    data = json.loads(http_get_text(endpoint, timeout))
    products = data.get("products", [])
    records: list[dict] = []
    for product in products:
        body = re.sub(r"<[^>]+>", " ", product.get("body_html", ""))
        variants = [
            {
                "id": v.get("id"),
                "title": v.get("title"),
                "price": v.get("price"),
                "available": bool(v.get("available")),
                "grams": v.get("grams"),
                "sku": v.get("sku"),
            }
            for v in (product.get("variants") or [])
        ]
        records.append(
            normalize_record(
                roaster=roaster,
                snapshot_at=snapshot_at,
                url=urljoin(roaster.base_url, f"/products/{product.get('handle', '')}"),
                name=product.get("title", ""),
                body_text=body,
                variants=variants,
                sku_fallback=f"{roaster.name}:{product.get('id')}",
            )
        )
    return records


def fetch_woocommerce_records(roaster: Roaster, timeout: int, snapshot_at: str) -> list[dict]:
    # WooCommerce Store API is public on many stores.
    endpoint = urljoin(roaster.base_url, "/wp-json/wc/store/products?per_page=100&page=1")
    data = json.loads(http_get_text(endpoint, timeout))
    if not isinstance(data, list):
        raise ValueError("WooCommerce endpoint did not return product list")

    records: list[dict] = []
    for product in data:
        name = product.get("name", "")
        desc = re.sub(r"<[^>]+>", " ", (product.get("description") or ""))
        short_desc = re.sub(r"<[^>]+>", " ", (product.get("short_description") or ""))
        body = f"{desc} {short_desc}".strip()

        prices = product.get("prices") or {}
        price_raw = prices.get("price")
        # Store API prices are often cents as string.
        amount = None
        if price_raw is not None:
            try:
                amount = float(price_raw) / 100.0 if int(float(price_raw)) > 999 else float(price_raw)
            except Exception:
                amount = None

        variants = [
            {
                "id": product.get("id"),
                "title": "Default / WHOLE BEANS",
                "price": f"{amount:.2f}" if amount is not None else None,
                "available": bool(product.get("is_in_stock", True)),
                "grams": None,
                "sku": product.get("sku"),
            }
        ]
        records.append(
            normalize_record(
                roaster=roaster,
                snapshot_at=snapshot_at,
                url=product.get("permalink") or urljoin(roaster.base_url, "/"),
                name=name,
                body_text=body,
                variants=variants,
                sku_fallback=f"{roaster.name}:{product.get('id')}",
            )
        )
    return records


def fetch_jsonld_records(roaster: Roaster, timeout: int, snapshot_at: str) -> list[dict]:
    page_url = urljoin(roaster.base_url, roaster.catalog_hint or "/")
    html_page = http_get_text(page_url, timeout)

    scripts = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html_page,
        flags=re.IGNORECASE | re.DOTALL,
    )

    products: list[dict] = []
    for block in scripts:
        block = block.strip()
        try:
            data = json.loads(block)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Product":
                products.append(node)
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                for g in node["@graph"]:
                    if isinstance(g, dict) and g.get("@type") == "Product":
                        products.append(g)

    records: list[dict] = []
    for idx, product in enumerate(products, start=1):
        name = product.get("name") or f"Product {idx}"
        desc = product.get("description") or ""
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offer = offers[0] if offers else {}
        else:
            offer = offers
        available_flag = str(offer.get("availability", "")).lower()
        in_stock = "instock" in available_flag if available_flag else True
        price = offer.get("price")
        variants = [
            {
                "id": None,
                "title": "Default / WHOLE BEANS",
                "price": str(price) if price is not None else None,
                "available": in_stock,
                "grams": None,
                "sku": product.get("sku"),
            }
        ]
        records.append(
            normalize_record(
                roaster=roaster,
                snapshot_at=snapshot_at,
                url=product.get("url") or page_url,
                name=name,
                body_text=desc,
                variants=variants,
                sku_fallback=f"{roaster.name}:jsonld:{idx}",
            )
        )
    return records


def fetch_records_for_roaster(roaster: Roaster, timeout: int, snapshot_at: str) -> list[dict]:
    # Probe adapters in order. Keep platform hint but allow fallback.
    adapters = []
    hint = (roaster.platform or "").lower()
    if hint == "woocommerce":
        adapters = [fetch_woocommerce_records, fetch_shopify_records, fetch_jsonld_records]
    elif hint == "jsonld":
        adapters = [fetch_jsonld_records, fetch_shopify_records, fetch_woocommerce_records]
    else:
        adapters = [fetch_shopify_records, fetch_woocommerce_records, fetch_jsonld_records]

    last_error: Exception | None = None
    for adapter in adapters:
        try:
            rows = adapter(roaster, timeout, snapshot_at)
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    if last_error:
        raise last_error
    return []


def main() -> None:
    args = parse_args()
    roaster_csv = resolve_roaster_csv(args.roasters, args.discover_max)
    roasters = load_roasters(roaster_csv)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_at = dt.datetime.now(dt.timezone.utc).isoformat()

    records: list[dict] = []
    for roaster in roasters:
        try:
            records.extend(fetch_records_for_roaster(roaster, args.timeout, snapshot_at))
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
