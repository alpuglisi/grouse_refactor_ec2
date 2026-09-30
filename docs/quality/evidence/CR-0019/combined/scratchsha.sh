#!/bin/bash
# sha256 of every file in the SCRATCH data/pipeline + data/negatives.
cd /tmp/claude-1000/cr0019-combined-scratch && find data/pipeline data/negatives -type f -print0 | sort -z | xargs -0 sha256sum
