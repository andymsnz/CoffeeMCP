# CoffeeMCP

CoffeeMCP gives your agent a practical coffee-ops workflow: discover roasters, find in-stock beans, build cart links, and track spend + preference feedback over time.

## What this skill enables your agent to do

Your agent can:

1. **Discover NZ coffee merchants** (including fallback seeds when search is flaky).
2. **Fetch live catalog data** from Shopify, WooCommerce, and JSON-LD storefronts.
3. **Recommend beans** with stock-first logic and whole-bean default behavior.
4. **Generate one-click cart URLs** for a single supplier with specific bean choices.
5. **Track order history** (grams + cost) and compute monthly consumption/spend summaries.
6. **Maintain user-specific preference memory** with feedback and watchlist controls.

## Getting started (5 minutes)

### 1) Build a fresh catalog snapshot

```bash
python nz-coffee-roast-monitor/scripts/discover_roasters.py --out /tmp/nz_roasters.csv
python nz-coffee-roast-monitor/scripts/fetch_roasts.py --roasters /tmp/nz_roasters.csv --out /tmp/catalog.jsonl
python nz-coffee-roast-monitor/scripts/scaa_notes.py --input /tmp/catalog.jsonl --output /tmp/catalog_tagged.jsonl
```

### 2) Initialize persistent memory DB

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py init   --db ~/.openclaw/workspace/memory/coffee-memory.db

python nz-coffee-roast-monitor/scripts/profile_memory.py ingest-catalog   --db ~/.openclaw/workspace/memory/coffee-memory.db   --input /tmp/catalog_tagged.jsonl
```

### 3) Generate a test cart (whole beans default)

```bash
python nz-coffee-roast-monitor/scripts/add_to_cart.py   --input /tmp/catalog_tagged.jsonl   --roaster "Grey Roasting Co"   --items "Sipi Falls" "Ruera" "Java Halu"   --qty 1
```

### 4) Log an order + check month summary

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py order-add   --db ~/.openclaw/workspace/memory/coffee-memory.db   --user andy --sku <sku> --grams 250 --price-nzd 26.50

python nz-coffee-roast-monitor/scripts/profile_memory.py monthly-summary   --db ~/.openclaw/workspace/memory/coffee-memory.db   --user andy --month 2026-03
```

## Operating defaults

- **Stock-first:** recommendations and carts default to in-stock beans only.
- **Whole-bean default:** pre-ground only when explicitly requested.
- **Suitability semantics:** filter/espresso are bean style labels, not grind instructions.
- **User isolation:** use `bootstrap-user` and `reset-user` for shared deployments.

## Included skill

- `nz-coffee-roast-monitor/`
  - `scripts/discover_roasters.py`
  - `scripts/fetch_roasts.py`
  - `scripts/scaa_notes.py`
  - `scripts/profile_memory.py`
  - `scripts/add_to_cart.py`
