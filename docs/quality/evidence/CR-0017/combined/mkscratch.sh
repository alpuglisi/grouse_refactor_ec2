#!/bin/bash
# CR-0017 deliverable 4 combined check: build the scratch tree.
# data/pipeline and data/negatives COPIED as regular files (cp -a; no
# symlink exists in either live dir); every other data/ directory recreated
# with symlinked FILES (cp -rs: real directories, symlinked files).
set -euo pipefail
LIVE=/home/ec2-user/grouse2/data
S=/tmp/claude-1000/cr0017-combined-scratch
rm -rf "$S"
mkdir -p "$S/data"
for d in "$LIVE"/*; do
  n=$(basename "$d")
  case "$n" in
    pipeline|negatives) cp -a "$d" "$S/data/$n" ;;
    *) cp -rs "$d" "$S/data/$n" ;;
  esac
done
bad=0
# No symlink at all inside the copied dirs.
if find "$S/data/pipeline" "$S/data/negatives" -type l | grep -q .; then echo "BAD symlink inside copied dir"; bad=1; fi
# No symlinked directories anywhere in the tree.
if find "$S" -type l -xtype d | grep -q .; then echo "BAD symlinked dir found"; bad=1; fi
# Every output path of generate_negatives, the manifest and the record is
# a regular file, not a symlink.
for f in candidate_pool.csv negatives_{ME,NH,VT}.csv train_negatives_{ME,NH,VT}.csv val_negatives_{ME,NH,VT}.csv; do
  p="$S/data/negatives/$f"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
done
for f in split_manifest.json acceptance_record.json; do
  p="$S/data/pipeline/$f"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
done
# Directories written to: none a symlink.
for p in "$S" "$S/data" "$S/data/negatives" "$S/data/pipeline"; do
  if [ -L "$p" ]; then echo "BAD dir $p"; bad=1; fi
done
[ "$bad" = 0 ] || exit 1
echo "output-path check: PASS (10 generator outputs + split_manifest.json + acceptance_record.json regular files; written dirs not symlinks; no symlink in copied dirs; no symlinked dir)"
echo "symlinked files: $(find "$S" -type l | wc -l); regular files: $(find "$S" -type f | wc -l)"
