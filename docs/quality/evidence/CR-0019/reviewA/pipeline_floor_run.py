"""Reviewer A (CR-0019): run the REAL pipeline (prepare_training_data.build /
generate_negatives.build, not acceptance_split.Replay) on a scratch copy of
the live CSVs with the proposed floor applied at positives step 2
(year >= 2020 before thinning), and write outputs into the scratch tree.
Usage: PYTHONPATH=. python .../pipeline_floor_run.py SCRATCH_ROOT [nofloor]
The floor is injected by filtering the evaluated_sightings rows as
prepare_training_data reads them (the set after step 2 is identical: both
conditions are row filters)."""
import os, sys
import pandas as pd
import prepare_training_data as ptd
import generate_negatives as gn

root = os.path.abspath(sys.argv[1])
floor = not (len(sys.argv) > 2 and sys.argv[2] == "nofloor")
for dp, dn, fn in os.walk(os.path.join(root, "data")):
    for f in fn:
        p = os.path.join(dp, f)
        assert not os.path.islink(p) or "tl_2023_us_county" in f, p
_orig = ptd.read_csv
def read_csv(path):
    df = _orig(path)
    if floor and "evaluated_sightings_" in os.path.basename(path):
        assert df["year"].notna().all()
        df = df[df["year"] >= 2020].copy()
    return df
ptd.read_csv = read_csv          # prepare_training_data.build only
assert gn.read_csv is _orig      # negatives buffer still reads every year
ptd.run(root)
gn.run(root)
