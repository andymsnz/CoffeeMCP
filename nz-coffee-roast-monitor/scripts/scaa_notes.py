#!/usr/bin/env python3
"""Normalize tasting notes into SCA-style flavor wheel families."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAPPING = {
    "fruity": r"berries|berry|stonefruit|citrus|apple|grape|tropical|melon",
    "sour_fermented": r"winey|ferment|yoghurt|sour",
    "green_vegetative": r"herbal|fresh|green|pea|vegetal",
    "other": r"papery|musty|chemical",
    "roasted": r"smoky|tobacco|burnt|roast",
    "spices": r"clove|cinnamon|pepper|spice",
    "nut_cocoa": r"cocoa|chocolate|nut|almond|hazelnut",
    "sweet": r"caramel|honey|sugar|molasses|maple|vanilla",
    "floral": r"jasmine|rose|lavender|floral",
}
COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in MAPPING.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def tags_for(note_text: str) -> list[str]:
    return [family for family, pattern in COMPILED.items() if pattern.search(note_text or "")]


def main() -> None:
    args = parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(args.input, encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            row = json.loads(line)
            if "tasting_notes_raw" in row:
                row["flavor_tags"] = tags_for(row.get("tasting_notes_raw", ""))
            dst.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    print(f"Tagged {count} rows -> {out}")


if __name__ == "__main__":
    main()
