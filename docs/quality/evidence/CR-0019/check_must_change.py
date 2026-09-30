"""CR-0019 must-change gate MC (PA-0021(b)); written before approval under
CLAUDE.md section 1 / CR-0011 A3. Read-only on both trees.

Compares the pre-CR artifacts (OLD root) with the regenerated ones (NEW
root) against the pre-registration written by preregister.py
(preregister_P.csv, _B.csv, _C_split.csv, _N.csv) on the CR-0017 live
artifacts.

MC0  OLD's 20 digested artifacts equal the CR-0017 live record copy
     (docs/quality/evidence/CR-0017/live/acceptance_record.json, sha256
     9d5ad0a9...). Otherwise the pre-registration is stale: FAIL, re-run
     preregister.py under review.
MC1  P per region: NEW thinned_positives_R has exactly the pre-registered
     rows (key, split, block_id, year), no more, no fewer.
     Every row whose key is also in OLD has a line byte-identical to its
     OLD line, except the `split` field for exactly the pre-registered
     split changes (preregister rows whose OLD split differs).
MC2  B: NEW block_assignments.csv == preregister_B.csv (block_id, split, n),
     row for row.
MC3  C: NEW candidate_pool.csv has OLD's header and OLD's rows in OLD's
     order; each line is byte-identical to OLD's except the `split` field
     of exactly the pre-registered rows in preregister_C_split.csv, which
     carry the pre-registered new split.
MC4  N per region: the key set, split and is_nonveg equal preregister_N.csv
     exactly; every row equals, as text, the NEW C row with that key on
     every column N and C share; label is 0 on every row; the combined
     file is in canonical (longitude, latitude) order; per (R, split) the
     N count equals the NEW P count (NEG_RATIO 1.0).
MC5  train_/val_ files (P and N, NEW tree): header + the combined file's
     split == train / val lines, in order.
MC does not check the N-only columns other than label (obs_date,
coord_uncertainty_m, gbif_id, common_name): R4's full-row replay does,
in the same acceptance run.

Exit 0 only if every check passes. Every check is reported.

Usage (repository root):
  python docs/quality/evidence/CR-0019/check_must_change.py --old OLD --new NEW
"""
import argparse
import csv
import hashlib
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "..", "CR-0017", "live", "acceptance_record.json")
RECORD_SHA = "9d5ad0a9f92c4278e752cb1207f76decd63972d7159933f0ce8d8b41d18c5aba"
REGIONS = ("ME", "NH", "VT")
BLOCKS = "data/pipeline/block_assignments.csv"
POOL = "data/negatives/candidate_pool.csv"


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read(root, rel):
    return pd.read_csv(os.path.join(root, rel), float_precision="round_trip")


def lines(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return f.read().splitlines()


def pre(name):
    return pd.read_csv(os.path.join(HERE, name), float_precision="round_trip")


def key(lon, lat):
    return (float(lon), float(lat))


def split_fields(line):
    """The line's fields, CSV-parsed (quoted commas stay in one field)."""
    return next(csv.reader([line]))


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

    # ---- MC0 ------------------------------------------------------------
    rec_ok = sha(RECORD) == RECORD_SHA
    with open(RECORD) as f:
        pinned = json.load(f)["artifacts"]
    bad = [rel for rel, h in sorted(pinned.items())
           if not os.path.exists(os.path.join(a.old, rel))
           or sha(os.path.join(a.old, rel)) != h]
    check("MC0", rec_ok and not bad and len(pinned) == 20,
          f"record copy sha ok={rec_ok}; {len(pinned)} artifacts; mismatched {bad}")

    P = pre("preregister_P.csv")
    B = pre("preregister_B.csv")
    CS = pre("preregister_C_split.csv")
    NP = pre("preregister_N.csv")

    # ---- MC1 / MC5 (positives) -------------------------------------------
    newP = {}
    for R in REGIONS:
        rel = f"data/pipeline/thinned_positives_{R}.csv"
        new = read(a.new, rel)
        newP[R] = new
        old = read(a.old, rel)
        exp = P[P["region"] == R]
        e = {key(r.longitude, r.latitude): (r.split, str(r.block_id), int(r.year))
             for r in exp.itertuples()}
        g = {key(r.longitude, r.latitude): (r.split, str(r.block_id), int(r.year))
             for r in new.itertuples()}
        check(f"MC1 {R} rows", e == g and len(new) == len(exp),
              f"new {len(new)}, pre-registered {len(exp)}, "
              f"missing {len(set(e) - set(g))}, extra {len(set(g) - set(e))}, "
              f"differing {sum(1 for k in set(e) & set(g) if e[k] != g[k])}")
        ol, nl = lines(a.old, rel), lines(a.new, rel)
        hdr = split_fields(ol[0])
        si = hdr.index("split")
        oldline = {key(r.longitude, r.latitude): ol[i + 1] for i, r in enumerate(old.itertuples())}
        oldsplit = {key(r.longitude, r.latitude): r.split for r in old.itertuples()}
        probs = 0
        n_split_changed = 0
        for i, r in enumerate(new.itertuples()):
            k = key(r.longitude, r.latitude)
            if k not in oldline or k not in e:
                continue          # extra/missing rows are MC1 rows' failures
            of, nf = split_fields(oldline[k]), split_fields(nl[i + 1])
            if len(of) != len(hdr) or len(nf) != len(hdr):
                probs += 1
                continue
            exp_split = e.get(k, (None,))[0]
            if oldsplit[k] != exp_split:
                n_split_changed += 1
                of[si] = exp_split
            if of != nf:
                probs += 1
        check(f"MC1 {R} kept lines", nl[0] == ol[0] and probs == 0,
              f"header equal={nl[0] == ol[0]}; {probs} kept rows differ beyond the "
              f"pre-registered split changes ({n_split_changed} split changes)")
        for s in ("train", "val"):
            relp = f"data/pipeline/{s}_positives_{R}.csv"
            want = [nl[0]] + [nl[i + 1] for i, v in enumerate(new["split"]) if v == s]
            check(f"MC5 {s}_positives_{R}", lines(a.new, relp) == want)

    # ---- MC2 ----------------------------------------------------------------
    nb = read(a.new, BLOCKS)
    okB = (list(nb.columns) == ["block_id", "split", "n"] and len(nb) == len(B)
           and nb.astype(str).values.tolist() == B.astype(str).values.tolist())
    check("MC2", okB, f"new {len(nb)} rows, pre-registered {len(B)}")

    # ---- MC3 ----------------------------------------------------------------
    oc, nc = lines(a.old, POOL), lines(a.new, POOL)
    ocd, ncd = read(a.old, POOL), read(a.new, POOL)
    hdr = split_fields(oc[0])
    si = hdr.index("split")
    flips = {(r.region, key(r.longitude, r.latitude)): r.split_new for r in CS.itertuples()}
    probs, n_flip = 0, 0
    same_len = len(oc) == len(nc) and oc[0] == nc[0]
    if same_len:
        for i, (ro, rn) in enumerate(zip(ocd.itertuples(), ncd.itertuples())):
            ko = (ro.region, key(ro.longitude, ro.latitude))
            kn = (rn.region, key(rn.longitude, rn.latitude))
            of, nf = split_fields(oc[i + 1]), split_fields(nc[i + 1])
            if ko != kn or len(of) != len(hdr) or len(nf) != len(hdr):
                probs += 1
                continue
            if ko in flips:
                n_flip += 1
                if of[si] == flips[ko]:
                    probs += 1          # pre-registered flip not made
                of[si] = flips[ko]
            if of != nf:
                probs += 1
    check("MC3", same_len and probs == 0 and n_flip == len(flips),
          f"header/rows equal length={same_len}; {n_flip}/{len(flips)} pre-registered "
          f"split changes found; {probs} rows differ otherwise")

    # ---- MC4 / MC5 (negatives) ----------------------------------------------
    shared = [c for c in ncd.columns]
    cidx = {key(r.longitude, r.latitude): i for i, r in enumerate(ncd.itertuples())}
    for R in REGIONS:
        rel = f"data/negatives/negatives_{R}.csv"
        new = read(a.new, rel)
        exp = NP[NP["region"] == R]
        e = {key(r.longitude, r.latitude): (r.split, bool(r.is_nonveg)) for r in exp.itertuples()}
        g = {key(r.longitude, r.latitude): (r.split, bool(r.is_nonveg)) for r in new.itertuples()}
        check(f"MC4 {R} rows", e == g and len(new) == len(exp),
              f"new {len(new)}, pre-registered {len(exp)}, missing {len(set(e) - set(g))}, "
              f"extra {len(set(g) - set(e))}")
        cols = [c for c in new.columns if c in shared]
        diff = 0
        for r in new.itertuples(index=False):
            k = key(r.longitude, r.latitude)
            i = cidx.get(k)
            if i is None:
                diff += 1
                continue
            crow = ncd.iloc[i]
            rr = r._asdict()
            for c in cols:
                a_, b_ = rr[c], crow[c]
                if not ((pd.isna(a_) and pd.isna(b_)) or str(a_) == str(b_)):
                    diff += 1
                    break
        check(f"MC4 {R} equals C", diff == 0, f"{diff} rows not equal to their NEW C row "
              f"on {len(cols)} shared columns")
        check(f"MC4 {R} label", bool((new["label"] == 0).all()))
        srt = new.sort_values(["longitude", "latitude"], kind="mergesort")
        check(f"MC4 {R} order", srt.index.tolist() == list(range(len(new))))
        for s in ("train", "val"):
            np_ = int((newP[R]["split"] == s).sum())
            nn_ = int((new["split"] == s).sum())
            check(f"MC4 {R} {s} count", np_ == nn_, f"P {np_}, N {nn_}")
        nl = lines(a.new, rel)
        for s in ("train", "val"):
            relp = f"data/negatives/{s}_negatives_{R}.csv"
            want = [nl[0]] + [nl[i + 1] for i, v in enumerate(new["split"]) if v == s]
            check(f"MC5 {s}_negatives_{R}", lines(a.new, relp) == want)

    for line in report:
        print(line)
    print(f"MC: {'PASS' if not fails else 'FAIL'} ({len(report) - len(fails)}/{len(report)} checks pass)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
