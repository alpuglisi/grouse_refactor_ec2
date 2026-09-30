#!/bin/bash
# Run the combined worktree's generate_negatives.py with cwd = scratch. $1 = log path
W=/home/ec2-user/grouse2/.claude/worktrees/cr0017-combined
cd /tmp/claude-1000/cr0017-combined-scratch || exit 2
start=$(date +%s)
nice -n 10 python "$W/generate_negatives.py" > "$1" 2>&1
rc=$?
echo "exit $rc, $(( $(date +%s) - start )) s" >> "$1"
exit $rc
