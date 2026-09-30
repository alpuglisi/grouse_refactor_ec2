#!/bin/bash
# Before the acceptance run: the record path (absent after
# prepare_training_data, CR-0012 step 6) and every other data/pipeline and
# data/negatives path are not symlinks; the written dirs are not symlinks.
S=/tmp/claude-1000/cr0019-combined-scratch
bad=0
for p in "$S" "$S/data" "$S/data/pipeline" "$S/data/negatives"; do [ -L "$p" ] && { echo "BAD dir $p"; bad=1; }; done
[ -L "$S/data/pipeline/acceptance_record.json" ] && { echo "BAD record symlink"; bad=1; }
[ -L "$S/data/pipeline/split_manifest.json" ] && { echo "BAD manifest symlink"; bad=1; }
n=$(find "$S/data/pipeline" "$S/data/negatives" -type l | wc -l); [ "$n" = 0 ] || { echo "BAD $n symlinks in copied dirs"; bad=1; }
echo "record path: $( [ -e "$S/data/pipeline/acceptance_record.json" ] && echo exists-regular || echo absent)"
[ "$bad" = 0 ] && echo "pre-acceptance output-path check: PASS" || exit 1
