#!/bin/bash
# Build the CR-0017 deliverable 4 scratch tree: CSV/JSON copied, everything
# else symlinked file by file (cp -rs: real directories, symlinked files).
set -euo pipefail
LIVE=/home/ec2-user/grouse2/data
S=/tmp/claude-1000/cr0017-scratch
rm -rf "$S"
mkdir -p "$S/data"
for d in "$LIVE"/*; do
  n=$(basename "$d")
  case "$n" in
    pipeline|negatives) cp -a "$d" "$S/data/$n" ;;
    *) cp -rs "$d" "$S/data/$n" ;;
  esac
done
# No symlinked directories anywhere in the tree.
if find "$S" -type l -xtype d | grep -q .; then echo "symlinked dir found"; exit 1; fi
# Every output path of generate_negatives (and the manifest) is a regular
# file, not a symlink.
bad=0
for f in candidate_pool.csv negatives_{ME,NH,VT}.csv train_negatives_{ME,NH,VT}.csv val_negatives_{ME,NH,VT}.csv; do
  p="$S/data/negatives/$f"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
done
for f in split_manifest.json acceptance_record.json; do
  p="$S/data/pipeline/$f"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
done
# Directories written to: none a symlink.
for p in "$S" "$S/data" "$S/data/negatives" "$S/data/pipeline"; do
  [ -L "$p" ] && { echo "BAD dir $p"; bad=1; }
done
[ "$bad" = 0 ] && echo "output-path check: no output path is a symlink (11 outputs + record checked)"
echo "symlinked files: $(find "$S" -type l | wc -l); regular files: $(find "$S" -type f | wc -l)"
