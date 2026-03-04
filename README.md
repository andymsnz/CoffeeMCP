# CoffeeMCP

Skill-focused toolkit for discovering NZ roasters, normalizing catalog data, learning preferences, and generating one-click cart links.

## Included skill

- `nz-coffee-roast-monitor/`
  - `scripts/discover_roasters.py` — discover candidate NZ roasters (with stable fallback seeds)
  - `scripts/fetch_roasts.py` — fetch and normalize catalogs via Shopify, WooCommerce, or JSON-LD fallback
  - `scripts/scaa_notes.py` — map tasting notes to flavor families
  - `scripts/profile_memory.py` — store preferences, orders, watchlist, and monthly spend summaries
  - `scripts/add_to_cart.py` — build one-click cart URLs using in-stock variants

## Quick test workflow

```bash
python nz-coffee-roast-monitor/scripts/discover_roasters.py --out /tmp/nz_roasters.csv
python nz-coffee-roast-monitor/scripts/fetch_roasts.py --roasters /tmp/nz_roasters.csv --out /tmp/catalog.jsonl
python nz-coffee-roast-monitor/scripts/scaa_notes.py --input /tmp/catalog.jsonl --output /tmp/catalog_tagged.jsonl

python nz-coffee-roast-monitor/scripts/add_to_cart.py \
  --input /tmp/catalog_tagged.jsonl \
  --roaster "Grey Roasting Co" \
  --items "Sipi Falls" "Ruera" "Java Halu" \
  --grind "WHOLE BEANS" --qty 1
```

## Notes

- Recommendations prioritize **in-stock** options by default.
- Default grind selection is **WHOLE BEANS** unless the user explicitly asks for pre-ground.
- Use watchlist flow for specific out-of-stock beans.

## Recommended persistent DB path

Use a stable DB file for long-term history:

```bash
~/.openclaw/workspace/memory/coffee-memory.db
```

Day-one/reset helpers for sharable multi-user flow:

```bash
python nz-coffee-roast-monitor/scripts/profile_memory.py bootstrap-user --db ~/.openclaw/workspace/memory/coffee-memory.db --user andy
python nz-coffee-roast-monitor/scripts/profile_memory.py reset-user --db ~/.openclaw/workspace/memory/coffee-memory.db --user andy
```
