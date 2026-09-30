#!/bin/bash
# Run the worktree's generate_negatives.py with cwd = the scratch tree.
# $1 = log name
W=/home/ec2-user/grouse2/.claude/worktrees/agent-aa9cd9861e95c4aaf
P=/tmp/claude-1000/-home-ec2-user-grouse2/491a150a-d26d-456d-b9b4-036cd4a6478b/scratchpad
cd /tmp/claude-1000/cr0017-scratch || exit 2
start=$(date +%s)
nice -n 10 python "$W/generate_negatives.py" > "$P/$1" 2>&1
rc=$?
echo "exit $rc, $(( $(date +%s) - start )) s" >> "$P/$1"
tail -12 "$P/$1"
