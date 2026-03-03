# Data Model

## Catalog record (JSONL)

- `snapshot_at` (ISO timestamp)
- `roaster`
- `url`
- `name`
- `sku`
- `brew_methods` (array)
- `roast_level`
- `origin`
- `process`
- `tasting_notes_raw`
- `flavor_tags` (array)
- `roast_date` (optional ISO date)
- `price_nzd` (optional float)
- `discovery_source` (optional string, e.g. `duckduckgo`, `fallback_seed`)

## SQLite tables (`profile_memory.py`)

- `catalog` stores latest known coffee metadata.
- `orders` stores order events (`user_id`, `sku`, `grams`, `ordered_at`).
- `feedback` stores explicit ratings and free-text notes.
- `preferences` stores inferred affinity for brew method, roast level, and flavor tags.

## MCP integration notes

Expose these operations as tools in a future MCP server:

1. `catalog.refresh`
2. `catalog.detect_new`
3. `user.record_order`
4. `user.record_feedback`
5. `user.recommend`

Return deterministic JSON payloads suitable for order-assistance agents.

## Discovery

Use `scripts/discover_roasters.py` to generate roaster CSV from online search results.
`fetch_roasts.py` can auto-discover when `--roasters` is omitted.
