"""CR-0010 acceptance: verify the coverage repair of the tsd, TreeMap and
tcc rasters against pre-registered constants and the backup.

Deliberately does NOT import repair_coverage_rasters.py: the masks are
re-derived here from their sources, so a bookkeeping slip in the repair
(wrong mask, wrong file) cannot also be made by the verifier.

Gates (docs/quality/change-requests/CR-0010-*.md, "Acceptance gates"):
    B0   backup files hash to the originals' manifest
    F1   checked file set == manifest; no stray temp files
    F2   every other *.tif in the raster dir is unchanged
    G0   each mask re-derived here matches its pin (digest, inside count)
    G1   no pixel inside coverage changed
    G2   every pixel outside coverage is the declared nodata
    G2p  changed pixels == N_pre, per file
    G6   profile, IMAGE_STRUCTURE, band tags, overviews, mask flags
         unchanged; no .aux.xml sidecar
    G7   GROUSE_REPAIR tag present with the pinned mask digest
    G8.1 no patches_* in the cache dir
    G8.2 mtime differs from the manifest's pre-repair mtime
Observations (reported, never fail): X1 nlcd-vs-disturbance disagreement,
X2 size ratio, X3 training windows touching out-of-coverage pixels, X4
tsd in-coverage 0 / TSD_MAX_YEARS counts before and after.

Exit status 1 if any gate fails.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grouse_data import NODATA_SENTINELS

HERE = os.path.dirname(os.path.abspath(__file__))
ALL_GATES = ["B0", "F1", "F2", "G0", "G1", "G2", "G2p", "G6", "G7",
             "G8.1", "G8.2"]
ALL_OBS = ["X1", "X2", "X3", "X4"]
FILE_RE = re.compile(r"^(ME|NH|VT)_(\d{4})_([a-z_]+)\.tif$")


class Report:
    def __init__(self):
        self.rows = []

    def add(self, gid, kind, subject, value, required, ok=None):
        self.rows.append((gid, kind, subject, str(value), str(required), ok))

    def failed(self):
        return [r for r in self.rows if r[1] == "GATE" and r[5] is False]

    def render(self):
        out = []
        for gid, kind, subj, val, req, ok in self.rows:
            flag = "" if ok is None else ("PASS" if ok else "FAIL")
            out.append(f"{gid:5s} {kind:4s} {flag:4s} {subj:32s} "
                       f"value={val}  required={req}")
        return "\n".join(out)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def read_manifest(path):
    rows = {}
    with open(path) as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            rec = dict(zip(header, line.rstrip("\n").split("\t")))
            rows[rec["name"]] = rec
    return rows


def digest(mask):
    return hashlib.sha256(np.packbits(mask.ravel())).hexdigest()[:32]


# ---- independent mask derivation ----------------------------------------

def derive_nlcd(mask_root, region):
    """Every NLCD year must give the same mask; returns it."""
    paths = sorted(glob.glob(os.path.join(mask_root,
                                          f"{region}_*_nlcd.tif")))
    masks = []
    for p in paths:
        with rasterio.open(p) as s:
            masks.append(s.read(1) != -9999)
    first = masks[0]
    same = all(np.array_equal(first, m) for m in masks[1:])
    return first, same, len(paths)


def derive_disturbance(dist_dir, template):
    by_year = {}
    for p in glob.glob(os.path.join(dist_dir, "**", "*.tif"),
                       recursive=True):
        m = re.search(r"Dist(\d{2})", os.path.basename(p), re.I)
        if m:
            yy = int(m.group(1))
            y = 1900 + yy if yy >= 90 else 2000 + yy
            by_year[y] = max(by_year.get(y, p), p)
    with rasterio.open(template) as t:
        crs, tr, h, w = t.crs, t.transform, t.height, t.width
    cov = np.ones((h, w), bool)
    bad = np.array(NODATA_SENTINELS)
    for y in sorted(by_year):
        with rasterio.open(by_year[y]) as s:
            with WarpedVRT(s, crs=crs, transform=tr, width=w, height=h,
                           resampling=Resampling.nearest) as v:
                step = 2048
                for r in range(0, h, step):
                    n = min(step, h - r)
                    blk = v.read(1, window=((r, r + n), (0, w)))
                    cov[r:r + n] &= ~np.isin(blk, bad)
    return cov, len(by_year)


# ---- checks ---------------------------------------------------------------

def profile_signature(src):
    p = dict(src.profile)
    p["crs"] = src.crs.to_wkt() if src.crs else None
    p["transform"] = tuple(src.transform)
    return {"profile": p,
            "image_structure": src.tags(ns="IMAGE_STRUCTURE"),
            "band_tags": src.tags(1),
            "overviews": src.overviews(1),
            "mask_flags": [f.name for f in src.mask_flag_enums[0]]}


def check_file(rep, path, bak_path, region, feat, mask, pins, man_row,
               gates, obs):
    name = os.path.basename(path)
    nodata = pins["nodata"]
    mask_name = pins["feature_mask"][feat]
    with rasterio.open(path) as s:
        cur = s.read(1)
        cur_sig = profile_signature(s)
        tags = s.tags()
        declared = s.nodata
    with rasterio.open(bak_path) as b:
        old = b.read(1)
        old_sig = profile_signature(b)
    if cur.shape != mask.shape:
        rep.add("G1", "GATE", name, f"shape {cur.shape}", mask.shape, False)
        return
    changed = cur != old
    if "G1" in gates:
        n = int((changed & mask).sum())
        rep.add("G1", "GATE", name, n, 0, n == 0)
    if "G2" in gates:
        n = int(((cur != nodata) & ~mask).sum())
        ok = n == 0 and declared == nodata
        rep.add("G2", "GATE", name, f"{n} (declared {declared})", 0, ok)
    if "G2p" in gates:
        n = int(changed.sum())
        want = pins["n_pre"][region][feat]
        rep.add("G2p", "GATE", name, n, want, n == want)
    if "G6" in gates:
        diffs = [k for k in cur_sig if cur_sig[k] != old_sig[k]]
        sidecar = os.path.exists(path + ".aux.xml")
        rep.add("G6", "GATE", name, diffs or "identical",
                "identical, no sidecar", not diffs and not sidecar)
    if "G7" in gates:
        want = pins["masks"][region][mask_name]["sha256"]
        ok = (tags.get("GROUSE_REPAIR") == "CR-0010"
              and tags.get("GROUSE_REPAIR_MASK_SHA256") == want)
        rep.add("G7", "GATE", name, tags.get("GROUSE_REPAIR_MASK_SHA256"),
                want, ok)
    if "G8.2" in gates and man_row is not None:
        now = os.stat(path).st_mtime_ns
        ok = now != int(man_row["mtime_ns"])
        rep.add("G8.2", "GATE", name, now, f"!= {man_row['mtime_ns']}", ok)
    if "X4" in obs and feat == "tsd":
        from models import tsd_encode, TSD_MAX_YEARS
        cap = int(tsd_encode(np.array([TSD_MAX_YEARS]))[0])
        for label, a in (("before", old), ("after", cur)):
            rep.add("X4", "OBS", f"{name} {label}",
                    f"zero={int(((a == 0) & mask).sum())} "
                    f"max={int(((a == cap) & mask).sum())}", "unchanged")


def check_windows(rep, region, masks, transform, crs):
    """X3: training records whose 64x64 window touches uncovered pixels."""
    from pyproj import Transformer
    from grouse_data import GrouseData
    rd = GrouseData()[region]
    to = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = ~transform
    for kind in ("positives", "negatives"):
        for split in ("train", "val"):
            df = getattr(rd, kind)(split)
            x, y = to.transform(df["longitude"].values, df["latitude"].values)
            col, row = inv * (np.asarray(x), np.asarray(y))
            row, col = np.floor(row).astype(int), np.floor(col).astype(int)
            for mname, m in masks.items():
                h, w = m.shape
                anyout = centre = 0
                for r, c in zip(row, col):
                    if not (0 <= r < h and 0 <= c < w):
                        centre += 1
                        anyout += 1
                        continue
                    centre += int(not m[r, c])
                    win = m[max(r - 32, 0):r + 32, max(c - 32, 0):c + 32]
                    anyout += int(not win.all())
                rep.add("X3", "OBS", f"{region} {kind}/{split} {mname}",
                        f"window={anyout} centre={centre} of {len(df)}",
                        "report")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "data/landfire"))
    ap.add_argument("--mask-root", default=os.path.join(HERE, "data/landfire"))
    ap.add_argument("--dist-dir", default=os.path.join(HERE, "data/disturbance"))
    ap.add_argument("--backup-dir", default="/home/ec2-user/grouse_backup/CR-0010")
    ap.add_argument("--pins", default=os.path.join(
        HERE, "docs/quality/cr0010_pins.json"))
    ap.add_argument("--manifest-inscope", default=os.path.join(
        HERE, "docs/quality/evidence/CR-0010-manifest-inscope.tsv"))
    ap.add_argument("--manifest-other", default=os.path.join(
        HERE, "docs/quality/evidence/CR-0010-manifest-other.tsv"))
    ap.add_argument("--cache-dir", default=os.path.join(HERE, "data/cache"))
    ap.add_argument("--files", nargs="+", default=None,
                    help="Check only these file names (rehearsal). F2 is "
                         "skipped and F1 checks only these names.")
    ap.add_argument("--gates", nargs="+", default=ALL_GATES)
    ap.add_argument("--obs", nargs="*", default=ALL_OBS)
    ap.add_argument("--out", default=None, help="Also write the report here.")
    args = ap.parse_args()

    with open(args.pins) as f:
        pins = json.load(f)
    gates, obs = set(args.gates), set(args.obs)
    rep = Report()
    man = read_manifest(args.manifest_inscope)
    feats = pins["feature_mask"]

    present = sorted(os.path.basename(p)
                     for p in glob.glob(os.path.join(args.root, "*.tif"))
                     if (m := FILE_RE.match(os.path.basename(p)))
                     and m.group(3) in feats)
    names = args.files or present

    if "F1" in gates:
        if args.files:
            missing = [n for n in names if n not in man or n not in present]
            rep.add("F1", "GATE", "requested files", missing or "all present",
                    "all in manifest and on disk", not missing)
        else:
            extra = sorted(set(present) - set(man))
            gone = sorted(set(man) - set(present))
            rep.add("F1", "GATE", "file set",
                    f"{len(present)} present, missing={gone}, extra={extra}",
                    f"== manifest ({len(man)})", not extra and not gone
                    and len(present) == pins["n_files"])
        strays = [p for p in os.listdir(args.root)
                  if ".cr0010tmp" in p or p.endswith(".tmp")]
        rep.add("F1", "GATE", "stray temp files", strays or 0, 0, not strays)

    if "B0" in gates:
        bad = [n for n in names
               if sha_file(os.path.join(args.backup_dir, n))
               != man[n]["sha256"]]
        rep.add("B0", "GATE", f"backup ({len(names)} files)", bad or "all match",
                "all match", not bad)

    if "F2" in gates and not args.files:
        other = read_manifest(args.manifest_other)
        bad = [n for n, r in other.items()
               if not os.path.exists(os.path.join(args.root, n))
               or sha_file(os.path.join(args.root, n)) != r["sha256"]]
        rep.add("F2", "GATE", f"other rasters ({len(other)})",
                bad or "all unchanged", "all unchanged", not bad)

    if "G8.1" in gates:
        n = len(glob.glob(os.path.join(args.cache_dir, "patches_*")))
        rep.add("G8.1", "GATE", args.cache_dir, n, 0, n == 0)

    by_region = {}
    for n in names:
        m = FILE_RE.match(n)
        by_region.setdefault(m.group(1), []).append((n, m.group(3)))

    size_before = size_after = 0
    for region, items in sorted(by_region.items()):
        nl, same, n_nl = derive_nlcd(args.mask_root, region)
        template = sorted(glob.glob(os.path.join(args.mask_root,
                                                 f"{region}_*_nlcd.tif")))[0]
        dist, n_vint = derive_disturbance(args.dist_dir, template)
        masks = {"nlcd": nl, "disturbance": dist}
        if "G0" in gates:
            rep.add("G0", "GATE", f"{region} nlcd year-invariant",
                    f"{n_nl} years same={same}", True, same)
            for mname, m in masks.items():
                pin = pins["masks"][region][mname]
                got = (int(m.sum()), digest(m))
                rep.add("G0", "GATE", f"{region} {mname}", got,
                        (pin["inside"], pin["sha256"]),
                        got == (pin["inside"], pin["sha256"]))
        if "X1" in obs:
            g = nl.size
            rep.add("X1", "OBS", f"{region} nlcd-vs-disturbance",
                    f"nlcd_only={(nl & ~dist).sum() / g:.5%} "
                    f"dist_only={(dist & ~nl).sum() / g:.5%}", "report")
        for name, feat in sorted(items):
            path = os.path.join(args.root, name)
            bak = os.path.join(args.backup_dir, name)
            check_file(rep, path, bak, region, feat, masks[feats[feat]],
                       pins, man.get(name), gates, obs)
            size_before += os.path.getsize(bak)
            size_after += os.path.getsize(path)
        if "X3" in obs:
            with rasterio.open(template) as t:
                check_windows(rep, region, masks, t.transform, t.crs)
        print(f"{region}: checked {len(items)} files", flush=True)

    if "X2" in obs and size_before:
        rep.add("X2", "OBS", "size after/before",
                f"{size_after / size_before:.3f}", "report")

    text = rep.render()
    failed = rep.failed()
    summary = (f"\n{len(rep.rows)} rows, {len(failed)} gate failure(s): "
               + ("FAIL" if failed else "ALL GATES PASS"))
    print(text + summary)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + summary + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
