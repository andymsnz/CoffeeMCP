# Flavor Wheel Mapping (SCA-aligned)

Use these top-level families for normalized tagging:

- fruity
- sour_fermented
- green_vegetative
- other
- roasted
- spices
- nut_cocoa
- sweet
- floral

Keyword heuristics used by `scripts/scaa_notes.py`:

- `berries|berry|stonefruit|citrus|apple|grape|tropical|melon` -> `fruity`
- `winey|ferment|yoghurt|sour` -> `sour_fermented`
- `herbal|fresh|green|pea|vegetal` -> `green_vegetative`
- `papery|musty|chemical` -> `other`
- `smoky|tobacco|burnt|roast` -> `roasted`
- `clove|cinnamon|pepper|spice` -> `spices`
- `cocoa|chocolate|nut|almond|hazelnut` -> `nut_cocoa`
- `caramel|honey|sugar|molasses|maple|vanilla` -> `sweet`
- `jasmine|rose|lavender|floral` -> `floral`

Keep raw tasting notes unchanged. This mapping only adds machine-actionable tags.
