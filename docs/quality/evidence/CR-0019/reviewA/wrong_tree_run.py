"""Reviewer A (CR-0019), PA-0021(a): build WRONG trees with the real
pipeline (prepare_training_data / generate_negatives, monkeypatched) in a
scratch copy, for MC (check_must_change.py) to judge.
Usage: PYTHONPATH=. python .../wrong_tree_run.py ROOT MODE
MODE: after_thin  - floor applied after thinning (before the block split)
      off_by_one  - year > 2020 at step 2
      source      - floor applied to evaluated_sightings for BOTH scripts
                    (so the 300 m buffer shrinks)
      delete      - correct floor, then 10 ME positives deleted post-thin"""
import os, sys
import prepare_training_data as ptd
import generate_negatives as gn

root, mode = os.path.abspath(sys.argv[1]), sys.argv[2]
for dp, dn, fn in os.walk(os.path.join(root, "data")):
    for f in fn:
        p = os.path.join(dp, f)
        assert not os.path.islink(p) or "tl_2023_us_county" in f, p
_orig_read, _orig_thin = ptd.read_csv, ptd.thin_by_min_distance
def is_eval(p): return "evaluated_sightings_" in os.path.basename(p)
def read_floor(p):
    df = _orig_read(p)
    if is_eval(p):
        df = df[df["year"] > 2020] if mode == "off_by_one" else df[df["year"] >= 2020]
    return df.copy()
if mode in ("off_by_one", "source", "delete"):
    ptd.read_csv = read_floor
if mode == "source":
    gn.read_csv = read_floor
if mode == "after_thin":
    def thin(df, *a, **k):
        out = _orig_thin(df, *a, **k)
        return out[out["year"] >= 2020].copy()
    ptd.thin_by_min_distance = thin
if mode == "delete":
    def thin(df, *a, **k):
        out = _orig_thin(df, *a, **k)
        me = out[out["region"] == "ME"].sort_values("longitude").index[:10]
        return out.drop(index=me).copy()
    ptd.thin_by_min_distance = thin
assert gn.thin_by_min_distance is _orig_thin
ptd.run(root)
gn.run(root)
