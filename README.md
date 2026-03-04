# CoffeeMCP

Skill-focused toolkit for discovering NZ roasters, normalizing catalog data, learning preferences, and generating one-click cart links.

## Included skill

- `nz-coffee-roast-monitor/`
  - `scripts/discover_roasters.py` — discover candidate NZ roasters (with stable fallback seeds)
  - `scripts/fetch_roasts.py` — pull Shopify product catalogs and normalize records
  - `scripts/scaa_notes.py` — map tasting notes to flavor families
  - `scripts/profile_memory.py` — store preferences/feedback and generate stock-aware recommendations
  - `scripts/add_to_cart.py` — build Shopify cart URLs using in-stock variants

## Local workflow

```bash
# 1) Sync skill into OpenClaw runtime skills folder
./sync-skill.sh

# 2) Run a quick pipeline snapshot
python nz-coffee-roast-monitor/scripts/discover_roasters.py --out /tmp/nz_roasters.csv
python nz-coffee-roast-monitor/scripts/fetch_roasts.py --roasters /tmp/nz_roasters.csv --out /tmp/catalog.jsonl
python nz-coffee-roast-monitor/scripts/scaa_notes.py --input /tmp/catalog.jsonl --output /tmp/catalog_tagged.jsonl

# 3) Build a one-click cart (example)
python nz-coffee-roast-monitor/scripts/add_to_cart.py \
  --input /tmp/catalog_tagged.jsonl \
  --roaster "Grey Roasting Co" \
  --items "Sipi Falls" "Ruera" "Java Halu" \
  --grind FILTER --qty 1
```

## GitHub sync

```bash
# commit + push from current branch
./publish-skill.sh "your commit message"
```

## Notes

- Recommendations should prioritize **in-stock** options by default.
- Use watchlist flow when tracking specific out-of-stock beans.


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
