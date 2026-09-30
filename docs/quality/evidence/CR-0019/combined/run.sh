#!/bin/bash
# CR-0019 deliverable 4 combined check: run one tool of the combined
# worktree with cwd = scratch (nice -n 10). $1 = tool (prepare|gn|acc),
# $2 = log path. The acceptance run is a full run (no --calibrate) with
# --data-root scratch, so its record is written inside scratch only.
W=/home/ec2-user/grouse2/.claude/worktrees/cr0019-combined
S=/tmp/claude-1000/cr0019-combined-scratch
cd "$S" || exit 2
start=$(date +%s)
case "$1" in
  prepare) nice -n 10 python "$W/prepare_training_data.py" > "$2" 2>&1 ;;
  gn)      nice -n 10 python "$W/generate_negatives.py" > "$2" 2>&1 ;;
  acc)     nice -n 10 python "$W/acceptance_split.py" --data-root "$S" > "$2" 2>&1 ;;
  *) echo "unknown tool $1"; exit 2 ;;
esac
rc=$?
echo "exit $rc, $(( $(date +%s) - start )) s" >> "$2"
exit $rc
