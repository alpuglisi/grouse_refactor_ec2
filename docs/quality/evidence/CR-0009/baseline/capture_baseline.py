"""CR-0009 deliverable 2 (§ Baselines): baseline capture. Read-only on
data/ and the CR-0007 backup; writes only into this directory.

    python docs/quality/evidence/CR-0009/baseline/capture_baseline.py points
    python symptom_check.py --reproduce ...   (see README.txt)
    python docs/quality/evidence/CR-0009/baseline/capture_baseline.py scores

`points`: verify S0 against CR-0007-backup-manifest.txt; copy
calibration.json and inv_matched_pairs.csv here; write each snapshot's
in-box records (lon, lat, label, split, source region file, TIGER side)
and the NH region-file set in the form symptom_check.py --points accepts.
`scores`: sample the R run's in-process gap3/bce maps at every point set;
AUC/AP by split x side (symptom_check.item3_blocks).
"""
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, "..", "..", "..", "..", ".."))
sys.path.insert(0, REPO)
import symptom_check as sc  # noqa: E402
from regions import REGIONS  # noqa: E402

S0 = "/home/ec2-user/grouse_backup/CR-0007"
S1 = os.path.join(REPO, "data")
MANIFEST = os.path.join(REPO, "docs", "quality", "evidence",
                        "CR-0007-backup-manifest.txt")
FILES = {1: "pipeline/thinned_positives_{r}.csv",
         0: "negatives/negatives_{r}.csv"}
MODELS = ("gap3.pth", "bce.pth")


def rel(p):
    return os.path.relpath(p, REPO) if p.startswith(REPO) else p


def points():
    pins = sc.load_pins()
    box = pins["box"]
    man = {}
    with open(MANIFEST) as f:
        for line in f:
            h, p = line.split(None, 1)
            man[p.strip()] = h
    inputs, log = {}, []
    for snap, root in (("S0", S0), ("S1", S1)):
        frames = []
        for r in REGIONS:
            for label, tpl in FILES.items():
                p = os.path.join(root, tpl.format(r=r))
                h = sc.sha256(p)
                inputs[rel(p)] = h
                if snap == "S0":
                    ok = man.get(tpl.format(r=r)) == h
                    log.append(f"S0 {tpl.format(r=r)}: sha256 {h} "
                               f"{'matches' if ok else 'DOES NOT MATCH'} "
                               f"CR-0007-backup-manifest.txt")
                    if not ok:
                        raise SystemExit("\n".join(log))
                frames.append(sc.box_frame(pd.read_csv(p), label, r, box))
        pts = pd.concat(frames, ignore_index=True)
        pts["side"] = sc.point_sides(pts)
        pts["duplicate_across_files"] = pts.duplicated(
            ["longitude", "latitude", "label"], keep=False)
        pts = pts[["longitude", "latitude", "label", "split",
                   "source_file_region", "side", "duplicate_across_files"]]
        pts.to_csv(os.path.join(BASE, f"points_{snap}_all_region_files.csv"),
                   index=False)
        nh = pts[pts.source_file_region == pins["map_region"]].drop(
            columns="duplicate_across_files")
        sc.union_point_set([nh])            # must have no duplicate
        nh.to_csv(os.path.join(BASE, f"points_{snap}_NH_region_files.csv"),
                  index=False)
    for a, b in ((1, "pipeline/thinned_positives_{r}.csv"),
                 (0, "negatives/negatives_{r}.csv")):
        for r in REGIONS:
            f = b.format(r=r)
            same = inputs[rel(os.path.join(S0, f))] == inputs[
                rel(os.path.join(S1, f))]
            log.append(f"S0 vs S1 {f}: {'byte-identical' if same else 'DIFFER'}")
    for src, dst in (("data/calibration/calibration.json", "calibration.json"),
                     ("inv_matched_pairs.csv", "inv_matched_pairs.csv")):
        shutil.copyfile(os.path.join(REPO, src), os.path.join(BASE, dst))
        inputs[src] = sc.sha256(os.path.join(REPO, src))
        log.append(f"copied {src} -> baseline/{dst} (sha256 "
                   f"{sc.sha256(os.path.join(BASE, dst))})")
    inputs[rel(sc.county_zip())] = sc.sha256(sc.county_zip())
    for m in MODELS:
        inputs[m] = sc.sha256(os.path.join(REPO, m))
    with open(os.path.join(BASE, "inputs_sha256_points_stage.json"), "w") as f:
        json.dump(inputs, f, indent=1, sort_keys=True)
    with open(os.path.join(BASE, "points_capture_log.txt"), "w") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))


def scores():
    lines = ["Item 3 baseline scores (CR-0009 § Baselines 2): maps from the R "
             "run (baseline/R/R_<model>/map_box_NH_<model>.tif, in-process, "
             "calibration = baseline/calibration.json). AUC/AP by side x "
             "split; records on NaN pixels excluded (counted as off-map)."]
    out = {}
    for m in MODELS:
        stem = os.path.splitext(m)[0]
        mp = os.path.join(BASE, "R", f"R_{stem}", f"map_box_NH_{stem}.tif")
        lines += ["", f"== {m}  map {rel(mp)} sha256 {sc.sha256(mp)}"]
        for f in sorted(os.listdir(BASE)):
            if not (f.startswith("points_S") and f.endswith(".csv")):
                continue
            pts = pd.read_csv(os.path.join(BASE, f))
            v = sc.sample_map(mp, pts)
            blocks, off = sc.item3_blocks(pts.label.values, v,
                                          pts.side.values,
                                          pts.split.astype(str).values)
            note = (" (all region files, duplicates kept - not a reference "
                    "set)" if "all_region" in f else " (reference set)")
            lines.append(f"-- {f}{note}: {len(pts)} records, "
                         f"{int(np.isfinite(v).sum())} on the map, off-map by "
                         f"side {off}")
            for k, b in blocks.items():
                if b["n"]:
                    lines.append(
                        f"   {k:9s} n={b['n']:4d} pos={b['pos']:4d} "
                        f"neg={b['neg']:3d} AUC={sc.fmt(b.get('auc'))} "
                        f"AP={sc.fmt(b.get('ap'))} "
                        f"mean_pos={sc.fmt(b.get('mean_pos'))} "
                        f"mean_neg={sc.fmt(b.get('mean_neg'))}")
            out[f"{m}|{f}"] = {"off_map_by_side": off, "blocks": blocks}
    with open(os.path.join(BASE, "item3_scores.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(BASE, "item3_scores.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    print("\n".join(lines))


if __name__ == "__main__":
    {"points": points, "scores": scores}[sys.argv[1]]()
