"""CR-0019 deliverable 2: read-only run of every GATE on today's real files
with the CR-0019 acceptance (E14, the replay's year floor, YEAR_MIN in the
config). Calls acceptance_split.run_gates (never full_run), so no record,
OBS file or artifact can be written. Prints the report to stdout.

Expected (CR-0019 section Test plan): E14 FAILs ((a) P, 1,437 rows: ME 814,
NH 256, VT 367; (b) P years {2016..2024} vs N {2020..2024}); E11 FAILs (no
YEAR_MIN in the manifest constants; on this branch before deliverable 3,
regions.py also lacks YEAR_MIN); R1-R4 FAIL; every other gate passes.

DETAIL compares the replay's outputs with the pre-registration
(preregister_P/_N/_B/_C_split.csv in this directory), which was produced
before approval by preregister.py's own floor subclass.

Usage: python acceptance_prefix.py <repo worktree> <data root>
Output committed as acceptance_prefix.txt in this directory."""
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

WT = sys.argv[1]
ROOT = sys.argv[2]
sys.path.insert(0, WT)
import acceptance_split as A  # noqa: E402

EV = os.path.join(WT, "docs", "quality", "evidence", "CR-0019")
cfg = A.load_config(os.path.join(WT, "docs", "quality", "acceptance_split.json"))
rec_path = os.path.join(ROOT, A.rpath(cfg, "acceptance_record"))


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


rec_before = sha(rec_path)
with open(rec_path) as f:
    rec = json.load(f)
head = subprocess.run(["git", "-C", WT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
print("CR-0019 deliverable 2: acceptance_split.py GATEs on today's real files (read-only)")
print(f"data root : {ROOT}")
print(f"config    : docs/quality/acceptance_split.json (sha256 {cfg['_sha256']})")
print(f"code      : {head} + working tree (acceptance_split.py sha256 {sha(os.path.join(WT, 'acceptance_split.py'))})")
print(f"regions.py: {A.regions_py_path(cfg)} (YEAR_MIN defined: {'YEAR_MIN' in A.parse_regions_py(A.regions_py_path(cfg))})")
print(f"started   : {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
print("driver    : run_gates() only; OBS not computed; no record written")
print(f"live record sha256 {rec_before}; its config_sha256 {rec['config_sha256']}")
same = all(rec["artifacts"].get(rel) == sha(os.path.join(ROOT, rel)) for rel in A.digested_paths(cfg))
print(f"today's 20 digested artifacts equal the live record's digests: {same}")
print()
t0 = time.time()
ctx, results = A.run_gates(ROOT, cfg)
print("GATES (exact)")
for gid in A.GATE_IDS:
    for line in A.format_gate(gid, results[gid]):
        print(line)
npass = sum(results[g]["status"] == "PASS" for g in A.GATE_IDS)
print()
print(f"SUMMARY: {npass}/{len(A.GATE_IDS)} GATEs pass; "
      f"FAIL: {', '.join(g for g in A.GATE_IDS if results[g]['status'] != 'PASS') or 'none'}")
print(f"runtime: {time.time() - t0:.1f} s")
print(f"live record unchanged: {sha(rec_path) == rec_before}")
print()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

print("DETAIL 1: expected FAIL set (CR-0019 test plan)")
fails = sorted(g for g in A.GATE_IDS if results[g]["status"] != "PASS")
expect = sorted(["E11", "E14", "R1", "R2", "R3", "R4"])
print(f"  FAIL set {fails} == expected {expect}: {fails == expect}")
e11 = results["E11"]["problems"]
print(f"  E11 problems naming YEAR_MIN: {sum('YEAR_MIN' in p for p in e11)} of {len(e11)}; "
      f"every E11 problem names YEAR_MIN: {all('YEAR_MIN' in p for p in e11)}")

print("DETAIL 2: E14 counts recomputed here with pandas from the files")
ymin = cfg["constants"]["YEAR_MIN"]
P = pd.concat([pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "thinned_positives", R))).assign(_R=R)
               for R in cfg["constants"]["REGIONS"]], ignore_index=True)
N = pd.concat([pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "negatives", R))).assign(_R=R)
               for R in cfg["constants"]["REGIONS"]], ignore_index=True)
C = pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "candidate_pool")))
lowP = P[P["year"] < ymin]
print(f"  P year < {ymin}: {len(lowP)} ({', '.join(f'{R} {n}' for R, n in lowP['_R'].value_counts().sort_index().items())}); "
      f"null {int(P['year'].isna().sum())}")
print(f"  N year < {ymin}: {int((N['year'] < ymin).sum())}; null {int(N['year'].isna().sum())}")
print(f"  C non-null year < {ymin}: {int((C['year'] < ymin).sum())}; null {int(C['year'].isna().sum())}")
print(f"  P years {sorted(int(v) for v in set(P['year']))}")
print(f"  N years {sorted(int(v) for v in set(N['year']))}")

print("DETAIL 3: the replay's outputs (CR-0019 floor) vs the pre-registration")
rep = ctx.replay()
print(f"  replay stage errors: {{{', '.join(f'{k}: {type(v).__name__}' for k, v in rep.errors.items() if v)}}}")


def k5(lon, lat):
    return (float(np.round(lon, 5)), float(np.round(lat, 5)))


preP = pd.read_csv(os.path.join(EV, "preregister_P.csv"), float_precision="round_trip")
repP = pd.concat([rep.pos[R] for R in cfg["constants"]["REGIONS"]], ignore_index=True)
a = {(r.region, *k5(r.longitude, r.latitude), r.split, str(r.block_id), int(r.year)) for r in preP.itertuples()}
b = {(r.region, *k5(r.longitude, r.latitude), r.split, str(r.block_id), int(r.year)) for r in repP.itertuples()}
print(f"  P (region, key, split, block_id, year): replay {len(b)} rows, pre-registered {len(a)}; equal: {a == b}")
preN = pd.read_csv(os.path.join(EV, "preregister_N.csv"), float_precision="round_trip")
repN = pd.concat([rep.neg[R] for R in cfg["constants"]["REGIONS"]], ignore_index=True)
a = {(r.region, *k5(r.longitude, r.latitude), r.split, int(r.year), bool(r.is_nonveg)) for r in preN.itertuples()}
b = {(r.region, *k5(r.longitude, r.latitude), r.split, int(r.year), bool(A.bool_array(pd.Series([r.is_nonveg]))[0]))
     for r in repN.itertuples()}
print(f"  N (region, key, split, year, is_nonveg): replay {len(b)} rows, pre-registered {len(a)}; equal: {a == b}")
preB = pd.read_csv(os.path.join(EV, "preregister_B.csv"))
a = set(zip(preB["block_id"].astype(str), preB["split"], preB["n"].astype(int)))
b = set(zip(rep.B["block_id"].astype(str), rep.B["split"], rep.B["n"].astype(int)))
print(f"  B (block_id, split, n): replay {len(b)} rows, pre-registered {len(a)}; equal: {a == b}")
preC = pd.read_csv(os.path.join(EV, "preregister_C_split.csv"), float_precision="round_trip")
live = {(r, *k5(lo, la)): s for r, lo, la, s in zip(C["region"], C["longitude"], C["latitude"], C["split"])}
rc = rep.pool_full
new = {(r, *k5(lo, la)): s for r, lo, la, s in zip(rc["region"], rc["longitude"], rc["latitude"], rc["split"])}
changed = {(k, live[k], new[k]) for k in live if k in new and live[k] != new[k]}
pre = {((r.region, *k5(r.longitude, r.latitude)), r.split_old, r.split_new) for r in preC.itertuples()}
print(f"  C: same key set as live: {set(live) == set(new)}; split changes {len(changed)} == "
      f"pre-registered {len(pre)}: {changed == pre}")
print(f"  draw counts: {json.dumps(rep.draw_counts, sort_keys=True)}")
print(f"  positives counts step 2: {json.dumps({R: rep.counts['positives'][R]['2'] for R in rep.regions})}")
print(f"  pool counts step 1: {json.dumps({R: rep.counts['negatives'][R]['1'] for R in rep.regions})}")
print(f"live record unchanged at end: {sha(rec_path) == rec_before}")
