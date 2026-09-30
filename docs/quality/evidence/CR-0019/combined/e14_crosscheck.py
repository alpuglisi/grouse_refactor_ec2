"""CR-0019 deliverable 4 combined check: independent pandas re-statement of
E14 on the scratch tree (acceptance_split reports E14 as one gate).
(a) every P and N row (combined files, pooled) has an integral year >=
regions.YEAR_MIN; every non-null C year >= YEAR_MIN. (b) distinct P years
== distinct N years. Read-only.   cd SCRATCH && python .../e14_crosscheck.py
"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
sys.path.insert(0, W)
import pandas as pd  # noqa: E402
import regions  # noqa: E402

ymin = regions.YEAR_MIN
sets = {}
ok = True
for cls, d, stem in (("P", "data/pipeline", "thinned_positives"), ("N", "data/negatives", "negatives")):
    y = pd.concat([pd.read_csv(f"{d}/{stem}_{r}.csv", usecols=["year"])["year"] for r in regions.REGIONS])
    y = pd.to_numeric(y, errors="coerce")
    bad = int((y.isna() | (y != y.round()) | (y < ymin)).sum())
    sets[cls] = sorted(int(v) for v in y.dropna().unique())
    print(f"E14(a) {cls}: {len(y)} rows, bad {bad}, min {y.min():.0f}, max {y.max():.0f}")
    ok &= bad == 0
c = pd.to_numeric(pd.read_csv("data/negatives/candidate_pool.csv", usecols=["year"])["year"], errors="coerce")
nbad = int((c.dropna() < ymin).sum())
print(f"E14(a) C: {len(c)} rows, {int(c.isna().sum())} null, non-null below {ymin}: {nbad}")
ok &= nbad == 0
print(f"E14(b) P years {sets['P']} vs N years {sets['N']}: {'equal' if sets['P'] == sets['N'] else 'DIFFER'}")
ok &= sets["P"] == sets["N"]
print("YEAR_MIN", ymin, "E14 CROSSCHECK", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
