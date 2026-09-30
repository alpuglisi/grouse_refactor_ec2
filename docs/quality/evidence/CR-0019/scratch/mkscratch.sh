#!/bin/bash
# CR-0019 deliverable 4 (pipeline part): build the scratch tree.
# data/pipeline and data/negatives copied as regular files (cp -a); every
# other data/ directory recreated with symlinked FILES (cp -rs), so a
# write could only replace a link, never a live file.
set -euo pipefail
LIVE=/home/ec2-user/grouse2/data
S=/tmp/claude-1000/cr0019-scratch
rm -rf "$S"
mkdir -p "$S/data"
for d in "$LIVE"/*; do
  n=$(basename "$d")
  case "$n" in
    pipeline|negatives) cp -a "$d" "$S/data/$n" ;;
    *) cp -rs "$d" "$S/data/$n" ;;
  esac
done
if find "$S" -type l -xtype d | grep -q .; then echo "symlinked dir found"; exit 1; fi
if find "$S/data/pipeline" "$S/data/negatives" -type l | grep -q .; then
  echo "symlink under pipeline/negatives"; exit 1; fi
bad=0
# Every output path of prepare_training_data.py and generate_negatives.py,
# the manifest and the record: a regular file, not a symlink.
for r in ME NH VT; do
  for f in thinned_positives train_positives val_positives; do
    p="$S/data/pipeline/${f}_$r.csv"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
  done
  for f in negatives train_negatives val_negatives; do
    p="$S/data/negatives/${f}_$r.csv"; if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
  done
done
for p in "$S/data/pipeline/block_assignments.csv" "$S/data/negatives/candidate_pool.csv" \
         "$S/data/pipeline/split_manifest.json" "$S/data/pipeline/acceptance_record.json"; do
  if [ -L "$p" ] || [ ! -f "$p" ]; then echo "BAD $p"; bad=1; fi
done
for p in "$S" "$S/data" "$S/data/negatives" "$S/data/pipeline"; do
  if [ -L "$p" ]; then echo "BAD dir $p"; bad=1; fi
done
[ "$bad" = 0 ] || exit 1
echo "output-path check: no output path is a symlink (20 outputs + manifest + record checked)"
echo "symlinked files: $(find "$S" -type l | wc -l); regular files: $(find "$S" -type f | wc -l)"
