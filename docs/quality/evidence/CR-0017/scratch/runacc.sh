#!/bin/bash
# Run the UNAMENDED (CR-0015 head) acceptance_split.py on the scratch tree.
W=/home/ec2-user/grouse2/.claude/worktrees/agent-aa9cd9861e95c4aaf
P=/tmp/claude-1000/-home-ec2-user-grouse2/491a150a-d26d-456d-b9b4-036cd4a6478b/scratchpad
S=/tmp/claude-1000/cr0017-scratch
sha256sum $S/data/pipeline/acceptance_record.json > $P/acc_record_before.sha
cd $S || exit 2
start=$(date +%s)
nice -n 10 python "$W/acceptance_split.py" --data-root "$S" > "$P/acc_unamended.log" 2>&1
rc=$?
echo "exit $rc, $(( $(date +%s) - start )) s" >> "$P/acc_unamended.log"
sha256sum -c $P/acc_record_before.sha >> "$P/acc_unamended.log" 2>&1
