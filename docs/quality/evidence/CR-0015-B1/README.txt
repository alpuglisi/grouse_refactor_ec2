CR-0015 B1 (deliverable 5): the to_5070 / block_split refactor is byte-identical.

Date: 2026-09-30. Code: commit 2c23d7d (deliverables 5 and 6; the manifest
records it, dirty False). Reference: /home/ec2-user/grouse2/data/pipeline/
split_manifest.json, the latest CR-0012 deliverable 6 run (commit df83c27).

Scratch tree /tmp/claude-1000/cr0015-b1 built by mk_scratch.py: CSV/JSON
copied from the main tree's data/{pipeline,negatives,sightings}; rasters and
the TIGER county zip symlinked; the script asserts no output directory or
file is a symlink. The main tree's data/ was only read.

run_b1.py (cwd = scratch tree): prepare_training_data.py (195 s), then
generate_negatives.py (125 s), then sha256 of every output listed in the
reference manifest's positives and negatives sections, then
acceptance_split.py --data-root <scratch> (56 s).

Result (b1_compare.txt, run_b1.out, acceptance.log):
- 20/20 outputs IDENTICAL: candidate_pool.csv, every negatives_* file
  (the B1 gate), plus block_assignments.csv and every *_positives_* file
  (prepare_training_data.to_5070 also delegates to regions.to_5070).
- new manifest outputs sections equal to the reference's.
- acceptance_split.py: SUMMARY 18/18 GATEs pass; ACCEPTED (record written
  inside the scratch tree only).
B1: PASS.
