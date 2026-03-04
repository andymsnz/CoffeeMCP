---
name: nz-coffee-roast-monitor
description: Track and analyze New Zealand coffee roaster offerings for filter/espresso and other brew methods, normalize roast metadata, map tasting notes to SCA Coffee Taster's Flavor Wheel categories, and maintain user preference memory with purchase history, consumption rate, coffee aging, and feedback loops. Use when building or operating a coffee discovery, monitoring, or order-assistance workflow.
---

# NZ Coffee Roast Monitor

## Overview
Use this skill to build and operate a repeatable coffee-roast monitoring pipeline focused on New Zealand roasters. Auto-discover roaster candidates from the web, capture inventory snapshots, standardize brew method and roast level metadata, index tasting notes against SCA flavor-wheel style categories, and personalize recommendations with long-term user memory.

## Workflow

1. **Discover roasters online** using `scripts/discover_roasters.py` (no manual seed file required).
2. **Collect catalog snapshots** using `scripts/fetch_roasts.py`.
3. **Normalize flavor notes** with `scripts/scaa_notes.py` to map free text into flavor-wheel categories.
4. **Persist user memory** and order history with `scripts/profile_memory.py` (stock-aware recommendations default to in-stock items).
5. **Run preference feedback loop** after each order or rating update to improve recommendations.
6. **Build one-click carts** for in-stock products with `scripts/add_to_cart.py`.

## Quick Start

```bash
python nz-coffee-roast-monitor/scripts/discover_roasters.py --out data/nz_roasters.csv

python nz-coffee-roast-monitor/scripts/fetch_roasts.py \
  --roasters data/nz_roasters.csv \
  --out data/catalog_snapshot.jsonl

# Or skip --roasters and fetch_roasts will auto-discover roasters itself.
python nz-coffee-roast-monitor/scripts/fetch_roasts.py --out data/catalog_snapshot.jsonl

python nz-coffee-roast-monitor/scripts/scaa_notes.py \
  --input data/catalog_snapshot.jsonl \
  --output data/catalog_snapshot_tagged.jsonl

python nz-coffee-roast-monitor/scripts/profile_memory.py init --db data/coffee_memory.db
python nz-coffee-roast-monitor/scripts/profile_memory.py ingest-catalog \
  --db data/coffee_memory.db --input data/catalog_snapshot_tagged.jsonl
```

## Data Conventions

- Use brew methods as lower-case enums: `espresso`, `filter`, `omni`, `plunger`, `aeropress`, `cold_brew`, `capsule`, `unknown`.
- Use roast levels as lower-case enums: `light`, `medium_light`, `medium`, `medium_dark`, `dark`, `unknown`.
- Preserve original tasting note text and store normalized flavor-wheel tags in `flavor_tags`.
- Keep snapshot records append-only to support “new roast” detection by `sku` or `(roaster, name, process, origin)` composite key.

## Recommendation Loop

After each purchase or rating event:

1. Update `orders` and `feedback` tables.
2. Recompute rolling daily consumption (g/day) from purchase sizes and inter-order intervals.
3. Apply age penalty to coffees older than user-configured freshness window (default 30 days post-roast-date).
4. Score candidate roasts:
   - +2 for preferred brew method match.
   - +2 for preferred roast level match.
   - +1 for each matching top-level flavor-wheel family.
   - -1 to -3 aging penalty depending on days from roast date.
5. Return top-N candidates with explanation fields (`why_recommended`).

## Resource Guide

- Read `references/flavor_wheel_mapping.md` when extending note normalization rules.
- Read `references/data_model.md` when integrating with MCP tools or order-assistance systems.
- Use `scripts/discover_roasters.py` to refresh candidate NZ roaster sources over time.


## Stock + Watchlist Rules

- Prioritize **in-stock** items by default in recommendations and shortlists.
- Only surface out-of-stock coffees when explicitly requested, or when adding to watchlist.
- Use `profile_memory.py watchlist-add` to track specific beans the user wants despite stock status.

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py watchlist-add \
  --db data/coffee_memory.db --user andy --sku <sku> --reason "notify on restock"

python nz-coffee-roast-monitor/scripts/profile_memory.py watchlist-list \
  --db data/coffee_memory.db --user andy
```

## Add-to-Cart (Shopify)

Generate a cart URL for a single supplier using in-stock variants only:

```bash
python nz-coffee-roast-monitor/scripts/add_to_cart.py \
  --input data/catalog_snapshot_tagged.jsonl \
  --roaster "Grey Roasting Co" \
  --items "Sipi Falls" "Ruera" "Java Halu" \
  --grind FILTER --qty 1
```


## Order Logging + Feedback Loop

Log purchases so recommendations can adapt over time:

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py order-add \
  --db data/coffee_memory.db --user andy --sku <sku> --grams 250

python nz-coffee-roast-monitor/scripts/profile_memory.py order-list \
  --db data/coffee_memory.db --user andy --limit 20

python nz-coffee-roast-monitor/scripts/profile_memory.py feedback \
  --db data/coffee_memory.db --user andy --sku <sku> --rating 5 --note "juicy and clean"
```

Use order+feedback history to adjust roast/method/flavor preferences over time.


## Cost Tracking + Monthly Summary

Track spend per order so monthly coffee dashboards can report consumption and cost.

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py order-add \
  --db data/coffee_memory.db --user andy --sku <sku> --grams 250 --price-nzd 26.50

python nz-coffee-roast-monitor/scripts/profile_memory.py monthly-summary \
  --db data/coffee_memory.db --user andy --month 2026-03
```

`monthly-summary` returns orders, total grams, total NZD spend, average bag cost, and normalized cost per 250g.
