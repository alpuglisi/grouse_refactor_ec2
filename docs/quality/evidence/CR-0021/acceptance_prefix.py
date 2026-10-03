"""CR-0021 deliverable 2: read-only run of every GATE on today's live files
with the CR-0021 acceptance (year-stratified replay draw, E9 amended, E15,
YEAR_STRATA in the config). Calls acceptance_split.run_gates (never
full_run), so no record, OBS file or artifact is written. Prints each
GATE's verdict and problems, then checks the exact expected outcome and
exits 1 on any deviation (0 only if every check holds).

Today's files: the accepted CR-0019 split (record ed27583b...), drawn per
(region, split) only, with the pre-top-up raw candidates; today's manifest
has no YEAR_STRATA. Expected, worked out from acceptance_split.py:

  FAIL E11  the manifest's two constants sections lack YEAR_STRATA (the
            config has it). regions.py: equal to the config once
            deliverable 3 is merged; before that, "YEAR_STRATA not defined"
            is the only other E11 problem allowed (reported, not a
            deviation).
  FAIL E15  (b) only: per (region, split, stratum) today's N counts take the
            pool's year mix, not P's (BUG-0073). (a) holds: the config's
            strata are well formed and every P, N and C year is in 2020-2024.
  FAIL R4   the replay's stratified draw raises ReplayError: on today's
            (pre-top-up) pool, single-year strata are short of habitat
            (preregister.txt section 3 "before", e.g. ME train 2024: 143 <
            213), which is why CR-0021 tops up 2023-2024.
  FAIL E9   (not in the CR's Test plan list; follows from the amended E9 on
            today's files): per-stratum clauses only. The NonVeg cap per
            stratum fails where today's unstratified N holds more NonVeg of
            a year than round(n_k x 0.3), and the habitat-supply clause
            fails on the same short strata as R4 (C is today's pool). The
            count clause (sum over strata) holds: totals are unchanged.
  PASS      E0-E8, E1p, E10, E12, E13, E14, R1, R2, R3 (positives, blocks
            and pool are unchanged by CR-0021; the replay's positives and
            pool stages do not read the strata).

Usage: python acceptance_prefix.py <repo worktree> <data root>
Output to be committed as acceptance_prefix.txt in this directory."""
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

EXPECT_FAIL = ["E11", "E15", "E9", "R4"]
cfg = A.load_config(os.path.join(WT, "docs", "quality", "acceptance_split.json"))
rec_path = os.path.join(ROOT, A.rpath(cfg, "acceptance_record"))
deviations = []


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check(name, ok, detail=""):
    print(f"CHECK {name}: {'ok' if ok else 'DEVIATION'}{(' - ' + detail) if detail else ''}")
    if not ok:
        deviations.append(name)


rec_before = sha(rec_path)
with open(rec_path) as f:
    rec = json.load(f)
head = subprocess.run(["git", "-C", WT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
rp = A.regions_py_path(cfg)
rvals = A.parse_regions_py(rp)
print("CR-0021 deliverable 2: acceptance_split.py GATEs on today's live files (read-only)")
print(f"data root : {ROOT}")
print(f"config    : docs/quality/acceptance_split.json (sha256 {cfg['_sha256']})")
print(f"code      : {head} + working tree (acceptance_split.py sha256 {sha(os.path.join(WT, 'acceptance_split.py'))})")
print(f"strata    : config YEAR_STRATA {cfg['constants']['YEAR_STRATA']}")
print(f"regions.py: {rp} (YEAR_STRATA {rvals.get('YEAR_STRATA', 'not defined')!r})")
print(f"started   : {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
print("driver    : run_gates() only; OBS rows not computed (O11a below); no record written")
print(f"live record sha256 {rec_before}; its config_sha256 {rec['config_sha256']}")
same_art = all(rec["artifacts"].get(rel) == sha(os.path.join(ROOT, rel)) for rel in A.digested_paths(cfg))
raw = [A.rpath(cfg, "gbif_candidates", R) for R in cfg["constants"]["REGIONS"]]
same_raw = all((rec.get("inputs") or {}).get(rel) == sha(os.path.join(ROOT, rel)) for rel in raw)
print()
check("today's 20 digested artifacts equal the live record's", same_art)
check("today's raw gbif_negatives_R.csv equal the live record's inputs (pre-top-up)", same_raw)
print()

t0 = time.time()
ctx, results = A.run_gates(ROOT, cfg)
print("GATES (exact)")
for gid in A.GATE_IDS:
    for line in A.format_gate(gid, results[gid]):
        print(line)
npass = sum(results[g]["status"] == "PASS" for g in A.GATE_IDS)
fails = sorted(g for g in A.GATE_IDS if results[g]["status"] != "PASS")
print()
print(f"SUMMARY: {npass}/{len(A.GATE_IDS)} GATEs pass; FAIL: {', '.join(fails) or 'none'}")
print(f"runtime: {time.time() - t0:.1f} s")
print()

print("VERDICTS vs expected")
for gid in A.GATE_IDS:
    want = "FAIL" if gid in EXPECT_FAIL else "PASS"
    got = results[gid]["status"]
    check(f"{gid} {got} (expected {want})", got == want)
check(f"FAIL set {fails} == expected {sorted(EXPECT_FAIL)}", fails == sorted(EXPECT_FAIL))
print()

print("REASONS")
for gid in EXPECT_FAIL:
    check(f"{gid}: no missing input", results[gid]["missing"] == [], str(results[gid]["missing"][:3]))
e11 = results["E11"]["problems"]
want11 = {f"manifest[{sec}].constants differs from the config (['YEAR_STRATA'])"
          for sec in ("positives", "negatives")}
extra11 = set(e11) - want11
if "YEAR_STRATA" in rvals:
    check("regions.py YEAR_STRATA equals the config (deliverable 3 merged)",
          A._norm_json(rvals["YEAR_STRATA"]) == A._norm_json(cfg["constants"]["YEAR_STRATA"]))
    allowed = set()
else:
    print("NOTE regions.py has no YEAR_STRATA (deliverable 3 not merged): E11 also reports it")
    allowed = {f"regions.py: YEAR_STRATA not defined (config YEAR_STRATA = {cfg['constants']['YEAR_STRATA']!r})"}
check("E11: both manifest sections lack YEAR_STRATA", want11 <= set(e11))
check("E11: no other problem", extra11 <= allowed, str(sorted(extra11 - allowed))[:400])
e15 = results["E15"]["problems"]
check("E15: every problem is E15(b)", bool(e15) and all(p.startswith("E15(b) [") for p in e15),
      str([p for p in e15 if not p.startswith("E15(b) [")][:3]))
e9 = results["E9"]["problems"]
per_stratum = [p for p in e9 if p.startswith("[") and p.split("]")[0].count("/") == 2]
check("E9: every problem is a per-stratum clause (NonVeg cap or habitat supply)",
      bool(e9) and len(per_stratum) == len(e9), str([p for p in e9 if p not in per_stratum][:3]))
check("E9: the count clause holds", not any("sum over strata" in p for p in e9))
print(f"  E9: {sum('NonVeg negatives > cap' in p for p in e9)} NonVeg-cap and "
      f"{sum('habitat pool' in p for p in e9)} habitat-supply problems")
rep = ctx.replay()
err = rep.errors.get("draw")
print(f"  replay stage errors: {{{', '.join(f'{k}: {type(v).__name__}: {v}' for k, v in rep.errors.items() if v)}}}")
check("R4: replay positives and pool stages ran", rep.errors.get("positives") is None and rep.errors.get("pool") is None)
check("R4: the stratified draw raised ReplayError on a habitat shortfall",
      isinstance(err, A.ReplayError) and "habitat pool" in str(err) and "< habitat target" in str(err))
check("R4: reported as the draw stage's failure",
      any("replay stage 'draw' raised ReplayError" in p for p in results["R4"]["problems"]))
print()

import pandas as pd  # noqa: E402

print("DETAIL 1: per (region, split, stratum) counts, recomputed here with pandas (E15(b))")
strata = [tuple(s) for s in cfg["constants"]["YEAR_STRATA"]]
regs = cfg["constants"]["REGIONS"]
P = pd.concat([pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "thinned_positives", R))).assign(_R=R)
               for R in regs], ignore_index=True)
N = pd.concat([pd.read_csv(os.path.join(ROOT, A.rpath(cfg, "negatives", R))).assign(_R=R)
               for R in regs], ignore_index=True)
n_diff = 0
for R in regs:
    for s in A.SPLITS:
        row = []
        for st in strata:
            p = int(((P["_R"] == R) & (P["split"] == s) & P["year"].isin(st)).sum())
            n = int(((N["_R"] == R) & (N["split"] == s) & N["year"].isin(st)).sum())
            n_diff += p != n
            row.append(f"{st[0]}: P {p} N {n}")
        print(f"  {R} {s}: " + "; ".join(row))
n_b = sum(p.startswith("E15(b) [") for p in e15)
check(f"E15(b) problem count {n_b} == cells with P != N recomputed here {n_diff}", n_b == n_diff)

print("DETAIL 2: O11a on today's files (report-only; BUG-0073 / preregister.txt: pooled 0.6615)")
o11 = A.stats_o11(P, N, cfg, regs, perm=False)
for scope in ("train", "val", "pooled"):
    print(f"  O11a [{scope}]: pooled {o11[f'O11.a.{scope}.pooled']:.4f}; "
          + ", ".join(f"{R} {o11[f'O11.a.{scope}.{R}']:.4f}" for R in regs))
print(f"  O11w: {o11.get('O11.w')}")
print()
check("live record unchanged at end", sha(rec_path) == rec_before)
print()
print(f"RESULT: {'AS EXPECTED' if not deviations else 'DEVIATION'}"
      f"{(' (' + '; '.join(deviations) + ')') if deviations else ''}")
sys.exit(1 if deviations else 0)
