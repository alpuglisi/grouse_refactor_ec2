"""CR-0021 must-change gate MC (PA-0021(b); CR-0021 section 3). Written
before approval (CLAUDE.md section 1 / CR-0011 A3). Read-only on both trees.

Compares the pre-CR tree (OLD: deliverable 5's backup of today's live
tree) with the regenerated tree (NEW) against the pre-registration written
by preregister.py (preregister_C.csv, preregister_N.csv,
preregister_draw.json), pinned below by sha256 once deliverable 1 has run.

MC0  OLD's 20 digested artifacts and its three raw gbif_negatives_R.csv
     equal the pinned CR-0019 live acceptance record (sha256 ed27583b...).
MC1  P and B unchanged: thinned/train/val positives of every region and
     block_assignments.csv are byte-identical in OLD and NEW.
MC2  raw files: OLD's bytes are an exact prefix of NEW's; NEW's sha256
     equals the pre-registered post-top-up hash; every appended row has the
     header's field count, state == R, year in {2023, 2024}, and a gbif_id
     absent from OLD.
MC3  C: NEW candidate_pool.csv has OLD's header and, row for row in order,
     exactly preregister_C.csv's (region, split, year, is_nonveg,
     longitude, latitude, gbif_id).
MC4  N per region: exactly preregister_N.csv's rows (key, split, year,
     is_nonveg), in canonical (longitude, latitude) order; label 0; each
     row equals, as text, the NEW C row with that key on every shared
     column; per (region, split, stratum) the N count equals
     round(P count x NEG_RATIO) with the pre-registered strata, and the
     per-stratum counts equal preregister_draw.json.
MC5  train_/val_ negative files: header + the combined file's lines by
     split, in order (P's are covered by MC1).
Exit 0 only if every check passes; every check is reported. Exit 2 if the
pre-registration is not pinned yet (transcription, CR-0021 section 4).

Usage (repository root):
  python docs/quality/evidence/CR-0021/check_must_change.py --old OLD --new NEW
"""
import argparse
import csv
import hashlib
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "..", "CR-0019", "live", "acceptance_record.json")
RECORD_SHA = "ed27583beb8b9f95b23ce3c51d18817ee1d9a1a42043b0c773138b028da9c42a"
REGIONS = ("ME", "NH", "VT")
TOPUP_YEARS = (2023, 2024)
NEG_RATIO = 1.0
RAW = "data/negatives/gbif_negatives_{R}.csv"
POOL = "data/negatives/candidate_pool.csv"
P_FILES = ([f"data/pipeline/{k}_positives_{R}.csv" for R in REGIONS
            for k in ("thinned", "train", "val")] + ["data/pipeline/block_assignments.csv"])

# Pinned at transcription (CR-0021 section 4, "Writing the result in"),
# from the files preregister.py wrote on the EC2 host. None = not yet run.
PRE_SHA = {
    "preregister_C.csv": None,
    "preregister_N.csv": None,
    "preregister_draw.json": None,
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(root, rel):
    return pd.read_csv(os.path.join(root, rel), float_precision="round_trip")


def lines(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", newline="") as f:
        return f.read().splitlines()


def pre(name):
    p = os.path.join(HERE, name)
    if sha(p) != PRE_SHA[name]:
        raise SystemExit(f"{name}: sha256 differs from the pinned pre-registration")
    return p


def key(lon, lat):
    return (float(lon), float(lat))


def truthy(v):
    """is_nonveg as written by the pipeline (bool, or 'True'/'False' text)."""
    return str(v).strip().lower() == "true"


def stratum_index(year, strata):
    for i, s in enumerate(strata):
        if int(year) in s:
            return i
    raise ValueError(f"year {year} in no stratum")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    a = ap.parse_args(argv)
    if any(v is None for v in PRE_SHA.values()):
        print("MC: NOT PINNED - run preregister.py, then pin PRE_SHA (CR-0021 section 4)")
        return 2
    fails, report = [], []

    def check(name, ok, detail=""):
        report.append(f"{name}: {'PASS' if ok else 'FAIL'} {detail}".rstrip())
        if not ok:
            fails.append(name)

    # ---- MC0 ----------------------------------------------------------------
    rec_ok = sha(RECORD) == RECORD_SHA
    with open(RECORD) as f:
        rec = json.load(f)
    pinned = dict(rec["artifacts"])
    for R in REGIONS:
        pinned[RAW.format(R=R)] = rec["inputs"][RAW.format(R=R)]
    bad = [rel for rel, h in sorted(pinned.items())
           if not os.path.exists(os.path.join(a.old, rel)) or sha(os.path.join(a.old, rel)) != h]
    check("MC0", rec_ok and not bad and len(rec["artifacts"]) == 20,
          f"record sha ok={rec_ok}; {len(pinned)} files; mismatched {bad}")

    C = pd.read_csv(pre("preregister_C.csv"), float_precision="round_trip")
    NP = pd.read_csv(pre("preregister_N.csv"), float_precision="round_trip")
    with open(pre("preregister_draw.json")) as f:
        draw = json.load(f)
    strata = [tuple(int(y) for y in s) for s in draw["strata"]]

    # ---- MC1 ----------------------------------------------------------------
    for rel in P_FILES:
        o, n = os.path.join(a.old, rel), os.path.join(a.new, rel)
        check(f"MC1 {rel}", os.path.exists(n) and sha(o) == sha(n))

    # ---- MC2 ----------------------------------------------------------------
    old_ids = set()
    for R in REGIONS:
        old_ids |= set(read(a.old, RAW.format(R=R))["gbif_id"].astype(str))
    for R in REGIONS:
        rel = RAW.format(R=R)
        with open(os.path.join(a.old, rel), "rb") as f:
            ob = f.read()
        with open(os.path.join(a.new, rel), "rb") as f:
            nb = f.read()
        prefix = nb.startswith(ob) and ob.endswith(b"\n")
        post_ok = sha(os.path.join(a.new, rel)) == draw["post_topup_sha256"].get(rel)
        probs = 0
        if prefix:
            hdr = next(csv.reader([ob.decode("utf-8").splitlines()[0]]))
            for row in csv.reader(nb[len(ob):].decode("utf-8").splitlines()):
                if len(row) != len(hdr):
                    probs += 1
                    continue
                r = dict(zip(hdr, row))
                try:
                    y = int(float(r["year"]))
                except ValueError:
                    y = None
                if r["state"] != R or y not in TOPUP_YEARS or r["gbif_id"] in old_ids:
                    probs += 1
        check(f"MC2 {rel}", prefix and post_ok and probs == 0,
              f"old bytes a prefix={prefix}; post sha pinned={post_ok}; bad appended rows {probs}")

    # ---- MC3 ----------------------------------------------------------------
    nc = read(a.new, POOL)
    hdr_ok = lines(a.old, POOL)[0] == lines(a.new, POOL)[0]
    def norm(df):
        return [(str(r.region), str(r.split), int(r.year), truthy(r.is_nonveg),
                 float(r.longitude), float(r.latitude), str(int(float(r.gbif_id))))
                for r in df.itertuples()]
    got, want = norm(nc), norm(C)
    check("MC3", hdr_ok and got == want,
          f"header equal={hdr_ok}; new {len(nc)} rows, pre-registered {len(C)}; "
          f"rows equal in order={got == want}")

    # ---- MC4 / MC5 ------------------------------------------------------------
    cidx = {key(r.longitude, r.latitude): i for i, r in enumerate(nc.itertuples())}
    for R in REGIONS:
        rel = f"data/negatives/negatives_{R}.csv"
        new = read(a.new, rel)
        exp = NP[NP["region"] == R]
        e = {key(r.longitude, r.latitude): (r.split, int(r.year), truthy(r.is_nonveg))
             for r in exp.itertuples()}
        g = {key(r.longitude, r.latitude): (r.split, int(r.year), truthy(r.is_nonveg))
             for r in new.itertuples()}
        check(f"MC4 {R} rows", e == g and len(new) == len(exp),
              f"new {len(new)}, pre-registered {len(exp)}, missing {len(set(e) - set(g))}, "
              f"extra {len(set(g) - set(e))}")
        shared = [c for c in new.columns if c in nc.columns]
        diff = 0
        for r in new.itertuples(index=False):
            i = cidx.get(key(r.longitude, r.latitude))
            if i is None:
                diff += 1
                continue
            crow, rr = nc.iloc[i], r._asdict()
            if any(not ((pd.isna(rr[c]) and pd.isna(crow[c])) or str(rr[c]) == str(crow[c]))
                   for c in shared):
                diff += 1
        check(f"MC4 {R} equals C", diff == 0, f"{diff} rows differ from their NEW C row")
        check(f"MC4 {R} label", bool((new["label"] == 0).all()))
        srt = new.sort_values(["longitude", "latitude"], kind="mergesort")
        check(f"MC4 {R} order", srt.index.tolist() == list(range(len(new))))
        P = read(a.new, f"data/pipeline/thinned_positives_{R}.csv")
        for s in ("train", "val"):
            ps = P[P["split"] == s]["year"].map(lambda y: stratum_index(y, strata))
            Ns = new[new["split"] == s]
            ns = Ns["year"].map(lambda y: stratum_index(y, strata))
            nvs = Ns["is_nonveg"].map(truthy)
            exp_d = draw["draw"][R][s]["strata"]
            for k, st in enumerate(strata):
                n_pos, n_neg = int((ps == k).sum()), int((ns == k).sum())
                n_nv = int(((ns == k) & nvs).sum())
                got_d = {"n": n_neg, "n_nv": n_nv, "n_hab": n_neg - n_nv}
                n_exp = int(round(n_pos * NEG_RATIO))
                ok = n_neg == n_exp and got_d == exp_d[str(st[0])]
                check(f"MC4 {R} {s} stratum {st[0]}", ok,
                      f"P {n_pos}, N {got_d}, pre-registered {exp_d[str(st[0])]}")
        nl = lines(a.new, rel)
        for s in ("train", "val"):
            relp = f"data/negatives/{s}_negatives_{R}.csv"
            want_l = [nl[0]] + [nl[i + 1] for i, v in enumerate(new["split"]) if v == s]
            check(f"MC5 {s}_negatives_{R}", lines(a.new, relp) == want_l)

    for line in report:
        print(line)
    print(f"MC: {'PASS' if not fails else 'FAIL'} ({len(report) - len(fails)}/{len(report)} checks pass)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
