#!/bin/bash
# Full run of the combined worktree's acceptance_split.py on the scratch
# tree (may write data/pipeline/acceptance_record.json inside scratch only).
# No --calibrate. $1 = log path
W=/home/ec2-user/grouse2/.claude/worktrees/cr0017-combined
S=/tmp/claude-1000/cr0017-combined-scratch
cd $S || exit 2
start=$(date +%s)
nice -n 10 python "$W/acceptance_split.py" --data-root "$S" > "$1" 2>&1
rc=$?
echo "exit $rc, $(( $(date +%s) - start )) s" >> "$1"
exit $rc
