#!/usr/bin/env bash
# prune_empty.sh - find (and optionally delete) zero-byte files and
# empty directories under a target tree. Pure filesystem checks, no
# rasterio, no opening any file - this is the free/instant version,
# not a content-validity check (that's what generate_treemap_features.py
# now does itself at generation time).
#
# Usage:
#   ./prune_empty.sh                       # dry run on ./data
#   ./prune_empty.sh data/treemap_raw      # dry run on one dir
#   ./prune_empty.sh data/treemap_raw --delete   # actually delete
set -euo pipefail

TARGET="data"
DELETE=0
for a in "$@"; do
  case "$a" in
    --delete) DELETE=1 ;;
    *) TARGET="$a" ;;
  esac
done

if [ ! -d "$TARGET" ]; then
  echo "Not a directory: $TARGET" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"
echo "Scanning $TARGET ..."

echo
echo "== Zero-byte files (can never be a valid GeoTIFF) =="
ZERO_FILES="$(find "$TARGET" -type f -empty || true)"
if [ -z "$ZERO_FILES" ]; then
  echo "  none found"
else
  echo "$ZERO_FILES" | sed 's/^/  /'
fi

echo
echo "== Empty directories =="
EMPTY_DIRS="$(find "$TARGET" -mindepth 1 -depth -type d -empty || true)"
if [ -z "$EMPTY_DIRS" ]; then
  echo "  none found"
else
  echo "$EMPTY_DIRS" | sed 's/^/  /'
fi

if [ "$DELETE" -eq 0 ]; then
  echo
  echo "Dry run - nothing deleted. Re-run with --delete to remove the above."
  exit 0
fi

echo
[ -n "$ZERO_FILES" ] && echo "$ZERO_FILES" | xargs -r rm -v
# Re-scan for empty dirs AFTER removing the zero-byte files above -
# deleting a file can leave its parent directory newly empty, which
# the first scan (taken before any deletion) wouldn't have caught.
find "$TARGET" -mindepth 1 -depth -type d -empty -print -delete
echo "Done."
