#!/bin/bash
# sha256 of every file in the LIVE data/pipeline + data/negatives (read-only).
cd /home/ec2-user/grouse2 && find data/pipeline data/negatives -type f -print0 | sort -z | xargs -0 sha256sum
