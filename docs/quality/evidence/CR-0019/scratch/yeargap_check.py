"""CR-0019 deliverable 4 (pipeline part): train.filter_by_year_gap on the
scratch tree's split files, exactly as build_datasets calls it (same
features as train.py's default, discover_features), at tolerance 2 (the
default: must return every frame unchanged) and 1 (must refuse).
build_datasets itself is not called: its standing_checks refuses until the
deliverable 2 acceptance run writes a record. Read-only.

    cd SCRATCH && python .../yeargap_check.py
"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
sys.path.insert(0, W)
import pandas as pd  # noqa: E402
import regions  # noqa: E402
import train  # noqa: E402
from grouse_data import GrouseData, DataConfig  # noqa: E402

data = GrouseData(DataConfig(base_dir=os.path.abspath(".")))
features = train.discover_features(data, list(regions.REGIONS))
print("features:", features)
refused = 0
for tol in (2, 1):
    for r in regions.REGIONS:
        rd = data[r]
        for what, df in (("train positive", rd.positives("train")),
                         ("train negative", rd.negatives("train")),
                         ("val positive", rd.positives("val")),
                         ("val negative", rd.negatives("val"))):
            try:
                out = train.filter_by_year_gap(df, rd, features, tol, what, r)
            except SystemExit as e:
                refused += 1
                print(f"tol {tol} {r} {what}: REFUSED ({len(df)} rows): {e.code}")
                continue
            same = out.equals(df.reset_index(drop=True))
            print(f"tol {tol} {r} {what}: {len(df)} rows, returned "
                  f"{len(out)}, unchanged={same}")
            assert same, (tol, r, what)
    if tol == 2:
        assert refused == 0
print(f"refusals at tolerance 1: {refused}")
assert refused > 0
print("YEARGAP CHECK PASS")
