"""CR-0017 must-change gate MC (PA-0021(b)); written before approval under
CLAUDE.md section 1 / CR-0011 A3. Read-only on both trees.

Compares the pre-CR artifacts (OLD root) with the regenerated ones (NEW
root) against the pre-registered removals in preregister_keys.csv
(written by preregister.py on the CR-0012 deliverable 6 artifacts).

MC0  OLD's 20 digested artifacts equal the CR-0012 d6 record copy
     (docs/quality/evidence/CR-0012-d6/acceptance_record.json). Otherwise
     the pre-registration is stale: FAIL, re-run preregister.py under review.
MC1  P (9 positive CSVs) and B (block_assignments.csv): NEW bytes == OLD.
MC2  C: NEW's data lines == OLD's data lines minus exactly the
     pre-registered C rows (header equal; order preserved).
MC3  N per region R: OLD keys minus NEW keys == the pre-registered N rows
     of R, exactly (a no-op or any other removal fails).
     Every retained row (key in OLD and NEW) has a byte-identical line.
MC4  N per (R, split, is_nonveg): row count NEW == OLD; the number of
     keys NEW adds equals the number removed in that cell; every added
     row is a row of NEW's C in the same (R, split, is_nonveg) cell, and
     equals that C row, as text, on every column N and C share; no cell
     exists in NEW that is absent from OLD.
MC5  train_negatives_R / val_negatives_R: header + the combined file's
     split == train / val lines, in order (NEW tree).
MC does not check WHICH replacements are drawn: R4's replay does that.

Exit 0 only if every check passes. Every check is reported.

Usage (repository root):
  python docs/quality/evidence/CR-0017/check_must_change.py --old OLD --new NEW
"""
import argparse
import hashlib
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(HERE, "preregister_keys.csv")
RECORD = os.path.join(HERE, "..", "CR-0012-d6", "acceptance_record.json")
REGIONS = ("ME", "NH", "VT")          # the three regions of the d6 record
POS = [f"data/pipeline/{k}_positives_{r}.csv"
       for k in ("thinned", "train", "val") for r in REGIONS]
BLOCKS = "data/pipeline/block_assignments.csv"
POOL = "data/negatives/candidate_pool.csv"


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read(root, rel):
    return pd.read_csv(os.path.join(root, rel), float_precision="round_trip")


def keyset(df):
    return set(zip(df["longitude"].astype(float), df["latitude"].astype(float)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    a = ap.parse_args()
    fails, report = [], []

    def check(name, ok, detail=""):
        report.append(f"{name}: {'PASS' if ok else 'FAIL'} {detail}".rstrip())
        if not ok:
            fails.append(name)

    with open(RECORD) as f:
        pinned = json.load(f)["artifacts"]
    bad = [rel for rel, h in sorted(pinned.items())
           if not os.path.exists(os.path.join(a.old, rel))
           or sha(os.path.join(a.old, rel)) != h]
    check("MC0", not bad, f"old artifacts differ from the d6 record: {bad}" if bad
          else f"{len(pinned)} old artifacts equal the d6 record")

    diff = [rel for rel in POS + [BLOCKS]
            if sha(os.path.join(a.old, rel)) != sha(os.path.join(a.new, rel))]
    check("MC1", not diff, f"changed: {diff}" if diff else "P and B unchanged")

    keys = pd.read_csv(KEYS, dtype={"longitude": str, "latitude": str})
    keys["lon"] = keys["longitude"].astype(float)
    keys["lat"] = keys["latitude"].astype(float)

    old_c, new_c = read(a.old, POOL), read(a.new, POOL)
    kc = set(zip(keys.loc[keys["set"] == "C", "lon"], keys.loc[keys["set"] == "C", "lat"]))
    with open(os.path.join(a.old, POOL)) as f:
        old_lines = f.read().splitlines()
    with open(os.path.join(a.new, POOL)) as f:
        new_lines = f.read().splitlines()
    ok_hdr = old_lines[0] == new_lines[0]
    oc_keys = list(zip(old_c["longitude"], old_c["latitude"]))
    expect = [ln for ln, k in zip(old_lines[1:], oc_keys) if k not in kc]
    n_hit = sum(k in kc for k in oc_keys)
    check("MC2", ok_hdr and n_hit == len(kc) and expect == new_lines[1:],
          f"pre-registered {len(kc)}, found in old C {n_hit}; old {len(old_lines) - 1:,} "
          f"-> new {len(new_lines) - 1:,} rows (expected {len(expect):,})")

    new_c_s = pd.read_csv(os.path.join(a.new, POOL), dtype=str,
                          keep_default_na=False)
    new_c_s.index = list(zip(new_c["longitude"], new_c["latitude"]))
    new_c_keys = set(new_c_s.index)

    def lines_by_key(root, rel):
        df = read(root, rel)
        with open(os.path.join(root, rel)) as f:
            ls = f.read().splitlines()
        return df, ls[0], dict(zip(zip(df["longitude"], df["latitude"]), ls[1:])), ls

    for r in REGIONS:
        rel = f"data/negatives/negatives_{r}.csv"
        o, _, o_lines, _ = lines_by_key(a.old, rel)
        n, n_hdr, n_lines, n_all = lines_by_key(a.new, rel)
        kn = keys[(keys["set"] == "N") & (keys["region"] == r)]
        want = set(zip(kn["lon"], kn["lat"]))
        gone = keyset(o) - keyset(n)
        kept = keyset(o) & keyset(n)
        changed = sorted(k for k in kept if o_lines[k] != n_lines[k])
        check(f"MC3[{r}]", gone == want and not changed,
              f"removed {len(gone)}, pre-registered {len(want)}; "
              f"unexpected {sorted(gone - want)[:3]}, kept {sorted(want - gone)[:3]}; "
              f"retained rows with changed lines {len(changed)} {changed[:2]}")
        n_s = pd.read_csv(os.path.join(a.new, rel), dtype=str, keep_default_na=False)
        n_s.index = list(zip(n["longitude"], n["latitude"]))
        shared = [c for c in n_s.columns if c in new_c_s.columns]
        ok, det = True, []
        ocells = set(zip(o["split"], o["is_nonveg"]))
        ncells = set(zip(n["split"], n["is_nonveg"]))
        if not ncells <= ocells:
            ok = False
            det.append(f"new cells {sorted(ncells - ocells)}")
        for (s_, nv), og in o.groupby(["split", "is_nonveg"]):
            ng = n[(n["split"] == s_) & (n["is_nonveg"] == nv)]
            removed = len(keyset(og) - keyset(ng))
            added = keyset(ng) - keyset(og)
            bad_add = [k for k in added if k not in new_c_keys
                       or not n_s.loc[[k], shared].iloc[0].equals(
                           new_c_s.loc[[k], shared].iloc[0])
                       or new_c_s.loc[[k], "region"].iloc[0] != r]
            cell_ok = len(ng) == len(og) and len(added) == removed and not bad_add
            ok &= cell_ok
            det.append(f"{s_}/{'nv' if nv else 'hab'} {len(og)}->{len(ng)} "
                       f"-{removed}+{len(added)}"
                       + (f" BAD {bad_add[:2]}" if bad_add else ""))
        check(f"MC4[{r}]", ok, "; ".join(det))
        sp = n["split"].tolist()
        ok5 = True
        for s_ in ("train", "val"):
            with open(os.path.join(a.new, f"data/negatives/{s_}_negatives_{r}.csv")) as f:
                part = f.read().splitlines()
            ok5 &= part == [n_hdr] + [ln for ln, x in zip(n_all[1:], sp) if x == s_]
        check(f"MC5[{r}]", ok5, "train_/val_ parts equal the split subsets")

    print("\n".join(report))
    print(f"\nMC: {'PASS' if not fails else 'FAIL ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
