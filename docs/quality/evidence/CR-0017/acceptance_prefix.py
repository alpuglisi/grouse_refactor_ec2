"""CR-0017 deliverable 2: read-only run of every GATE on today's real files.
Calls acceptance_split.run_gates (never full_run), so no record, OBS file
or artifact can be written. Prints the report to stdout.

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

cfg = A.load_config(os.path.join(WT, "docs", "quality", "acceptance_split.json"))
rec_path = os.path.join(ROOT, A.rpath(cfg, "acceptance_record"))


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


rec_before = sha(rec_path)
with open(rec_path) as f:
    rec = json.load(f)
head = subprocess.run(["git", "-C", WT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
print("CR-0017 deliverable 2: acceptance_split.py GATEs on today's real files (read-only)")
print(f"data root : {ROOT}")
print(f"config    : docs/quality/acceptance_split.json (sha256 {cfg['_sha256']})")
print(f"code      : {head} + working tree (acceptance_split.py sha256 {sha(os.path.join(WT, 'acceptance_split.py'))})")
print(f"started   : {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
print(f"driver    : run_gates() only; OBS not computed; no record written")
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
print("DETAIL (CR-0017 test plan: R4 replaces exactly the pre-registered negatives; draw counts equal)")
import io  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
KEYS_REL = "docs/quality/evidence/CR-0017/preregister_keys.csv"
if os.path.exists(os.path.join(WT, KEYS_REL)):
    keys_src = KEYS_REL
    with open(os.path.join(WT, KEYS_REL), encoding="utf-8") as f:
        keys_text = f.read()
else:        # on the unmerged acceptance branch the keys live at fc52728 (records branch)
    keys_src = f"fc52728:{KEYS_REL}"
    keys_text = subprocess.run(["git", "-C", WT, "show", keys_src], capture_output=True,
                               text=True, check=True).stdout
keys = pd.read_csv(io.StringIO(keys_text), float_precision="round_trip")
print(f"pre-registered keys: {keys_src} (sha256 {hashlib.sha256(keys_text.encode()).hexdigest()})")
for g in ("R3", "R4"):
    print(f"{g}: {len(results[g]['problems'])} problem lines; any draw-count line: "
          f"{any(p.startswith('draw:') for p in results[g]['problems'])}")
rep = ctx.replay()
preN = {(r.region, float(np.round(r.longitude, 5)), float(np.round(r.latitude, 5))) for r in keys[keys["set"] == "N"].itertuples()}
preC = {(r.region, float(np.round(r.longitude, 5)), float(np.round(r.latitude, 5))) for r in keys[keys["set"] == "C"].itertuples()}
live_N, rep_N = set(), set()
for R in cfg["constants"]["REGIONS"]:
    live = pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "negatives", R)), float_precision="round_trip")
    live_N |= {(R, a, b) for a, b in A.key_list(live, 5)}
    rep_N |= {(R, a, b) for a, b in A.key_list(rep.neg[R], 5)}
live_C = pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "candidate_pool")), float_precision="round_trip")
lc = {(r, a, b) for r, (a, b) in zip(live_C["region"], A.key_list(live_C, 5))}
rc = {(r, a, b) for r, (a, b) in zip(rep.pool_full["region"], A.key_list(rep.pool_full, 5))}
print(f"C: live minus replay = {len(lc - rc)} rows (== pre-registered 88: {lc - rc == preC}); "
      f"replay minus live = {len(rc - lc)}")
print(f"N: live minus replay = {len(live_N - rep_N)} rows (== pre-registered 23: {live_N - rep_N == preN}); "
      f"replay minus live = {len(rep_N - live_N)} (replacements)")
with open(os.path.join(ROOT, A.rpath(cfg, "split_manifest"))) as f:
    M = json.load(f)
print(f"draw counts: manifest == replay: {A._norm_json(M['negatives']['draw']) == A._norm_json(rep.draw_counts)}")
for R in cfg["constants"]["REGIONS"]:
    print(f"  pool {R}: step 5 manifest {M['negatives']['counts'][R]['5']} vs replay "
          f"{rep.counts['negatives'][R]['5']}; step 6 manifest {M['negatives']['counts'][R]['6']} vs "
          f"replay {rep.counts['negatives'][R]['6']}; step 11 manifest {M['negatives']['counts'][R]['11']} "
          f"vs replay {rep.counts['negatives'][R]['11']}")
print(f"live record unchanged at end: {sha(rec_path) == rec_before}")
