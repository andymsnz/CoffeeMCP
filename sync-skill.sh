#!/usr/bin/env bash
set -euo pipefail
SRC="/Users/andy/openclaw/CoffeeMCP/nz-coffee-roast-monitor/"
DST="/Users/andy/.openclaw/workspace/skills/nz-coffee-roast-monitor/"

mkdir -p "$DST"
rsync -a --delete "$SRC" "$DST"
echo "Synced skill to $DST"
