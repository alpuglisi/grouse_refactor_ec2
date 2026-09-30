#!/bin/bash
# usage: run_pipeline.sh TREE TAG [steps...]   steps: prep neg acc (default all)
# Runs the CR-0012 pipeline with cwd = TREE after checking that no output
# path (or its directory) is a symlink.
T=$1; TAG=$2; shift 2
STEPS=${*:-prep neg acc}
R=/home/ec2-user/grouse2
L=/tmp/claude-1000/-home-ec2-user-grouse2/cr0012-d6/logs; mkdir -p $L
check_no_symlink() {
  for p in "$T" "$T/data" "$T/data/pipeline" "$T/data/negatives" "$T/data/models"; do
    if [ -L "$p" ]; then echo "ABORT: $p is a symlink"; exit 3; fi
  done
  for f in block_assignments thinned_positives_ME thinned_positives_NH thinned_positives_VT \
           train_positives_ME train_positives_NH train_positives_VT val_positives_ME \
           val_positives_NH val_positives_VT; do
    [ -L "$T/data/pipeline/$f.csv" ] && { echo "ABORT: symlink output $f"; exit 3; }
  done
  for f in split_manifest.json acceptance_record.json; do
    [ -L "$T/data/pipeline/$f" ] && { echo "ABORT: symlink output $f"; exit 3; }
  done
  for f in candidate_pool negatives_ME negatives_NH negatives_VT train_negatives_ME \
           train_negatives_NH train_negatives_VT val_negatives_ME val_negatives_NH val_negatives_VT; do
    [ -L "$T/data/negatives/$f.csv" ] && { echo "ABORT: symlink output $f"; exit 3; }
  done
  n=$(find "$T/data/pipeline" "$T/data/negatives" "$T/data/models" -type l | wc -l)
  [ "$n" != 0 ] && { echo "ABORT: $n symlinks in output dirs"; exit 3; }
  echo "symlink check OK ($T)"
}
cd "$T" || exit 4
for s in $STEPS; do
  check_no_symlink
  case $s in
    prep) { time python $R/prepare_training_data.py; } > $L/$TAG.prep.log 2>&1; echo "prep exit $?" | tee -a $L/$TAG.prep.log ;;
    neg)  { time python $R/generate_negatives.py; } > $L/$TAG.neg.log 2>&1; echo "neg exit $?" | tee -a $L/$TAG.neg.log ;;
    acc)  { time python $R/acceptance_split.py --data-root "$T"; } > $L/$TAG.acc.log 2>&1; echo "acc exit $?" | tee -a $L/$TAG.acc.log ;;
  esac
done
