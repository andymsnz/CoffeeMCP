#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="/Users/andy/openclaw/CoffeeMCP"
SYNC_SCRIPT="$REPO_DIR/sync-skill.sh"
MSG="${1:-update nz-coffee-roast-monitor}"

"$SYNC_SCRIPT"
cd "$REPO_DIR"
git add nz-coffee-roast-monitor sync-skill.sh publish-skill.sh
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi
git commit -m "$MSG"
git push
