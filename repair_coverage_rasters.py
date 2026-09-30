"""CR-0010: write nodata outside coverage in the existing tsd, TreeMap
and tcc rasters.

Six input channels carry fabricated readings where their source product
has no coverage (mostly Canada and ocean): tsd reads "undisturbed 30
years" (BUG-0024), TreeMap reads 0 "non-forest" (BUG-0025), tcc reads 0
(BUG-0030). This script sets exactly those pixels to the file's declared
nodata, index-for-index, and changes nothing else.

Coverage, per feature (docs/quality/change-requests/CR-0010-*.md):
    tsd                       disturbance-intersection: every Annual
                              Disturbance vintage's value is not a
                              NODATA_SENTINEL, intersected over vintages
    balive tpa_live qmd       nlcd: the region's NLCD raster != -9999
    carbon_dwn tcc

Every mask is checked against the pre-registered digest in
docs/quality/cr0010_pins.json before any file is touched. Acceptance is
check_raster_repair.py, which derives the masks independently.

Subcommands, in the order CR-0010's deliverables run them:
    manifest  hash the 174 in-scope files and every other *.tif
    backup    copy the in-scope files to --backup-dir, verify hashes
    repair    repair in place (temp file + os.replace), tag each file
"""
import argparse
import concurrent.futures
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grouse_data import NODATA_SENTINELS, REPAIR_TAG
from regions import REGIONS

HERE = os.path.dirname(os.path.abspath(__file__))
PINS = os.path.join(HERE, "docs/quality/cr0010_pins.json")
EVIDENCE = os.path.join(HERE, "docs/quality/evidence")
MANIFEST_INSCOPE = os.path.join(EVIDENCE, "CR-0010-manifest-inscope.tsv")
MANIFEST_OTHER = os.path.join(EVIDENCE, "CR-0010-manifest-other.tsv")
DEFAULT_ROOT = os.path.join(HERE, "data/landfire")
DEFAULT_DIST = os.path.join(HERE, "data/disturbance")
DEFAULT_BACKUP = "/home/ec2-user/grouse_backup/CR-0010"
TMP_SUFFIX = ".cr0010tmp"
DIST_RE = re.compile(r"Dist(\d{2})", re.IGNORECASE)


def load_pins(path=PINS):
    with open(path) as f:
        return json.load(f)


def inscope_re(features):
    return re.compile(rf"^({'|'.join(REGIONS)})_(\d{{4}})_"
                      rf"({'|'.join(features)})\.tif$")


def list_inscope(root, pins):
    pat = inscope_re(pins["feature_mask"])
    return sorted(p for p in glob.glob(os.path.join(root, "*.tif"))
                  if pat.match(os.path.basename(p)))


def sha256_file(path, bufsize=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                return h.hexdigest()
            h.update(b)


def mask_digest(mask):
    return hashlib.sha256(np.packbits(mask.ravel())).hexdigest()[:32]


# ---- masks -------------------------------------------------------------

def dist_vintages(dist_dir):
    """{year: path}, newest LANDFIRE release per disturbance year - the
    selection generate_time_since_disturbance.fetch_disturbance makes."""
    found = {}
    for p in glob.glob(os.path.join(dist_dir, "**", "*.tif"),
                       recursive=True):
        m = DIST_RE.search(os.path.basename(p))
        if not m:
            continue
        yy = int(m.group(1))
        y = 1900 + yy if yy >= 90 else 2000 + yy
        if y not in found or p > found[y]:
            found[y] = p
    return found


def nlcd_mask(root, region):
    paths = sorted(glob.glob(os.path.join(root, f"{region}_*_nlcd.tif")))
    if not paths:
        raise SystemExit(f"{region}: no nlcd raster under {root}")
    with rasterio.open(paths[-1]) as src:
        return src.read(1) != -9999, src.transform, src.crs, src.shape


def disturbance_mask(dist_dir, template, first_year, block_rows=1024):
    """Intersection over every vintage of value not in NODATA_SENTINELS,
    each read onto the template grid with WarpedVRT nearest. Also returns
    the intersection over vintages <= first_year, for rule 2."""
    vint = dist_vintages(dist_dir)
    if not vint:
        raise SystemExit(f"no disturbance vintages under {dist_dir}")
    with rasterio.open(template) as ref:
        crs, transform, (h, w) = ref.crs, ref.transform, ref.shape
    cov = np.ones((h, w), dtype=bool)
    early = None
    sentinels = np.array(NODATA_SENTINELS)
    for d in sorted(vint):
        if early is None and d > first_year:
            early = cov.copy()
        with rasterio.open(vint[d]) as s, \
                WarpedVRT(s, crs=crs, transform=transform, width=w,
                          height=h, resampling=Resampling.nearest) as v:
            for r0 in range(0, h, block_rows):
                n = min(block_rows, h - r0)
                a = v.read(1, window=((r0, r0 + n), (0, w)))
                cov[r0:r0 + n] &= ~np.isin(a, sentinels)
    if early is None:
        early = cov.copy()
    return cov, early, len(vint)


def region_masks(root, dist_dir, region, pins):
    """{'nlcd': mask, 'disturbance': mask}, each checked against the pin.
    Exits on any mismatch - nothing is repaired with an unpinned mask."""
    nl, transform, crs, shape = nlcd_mask(root, region)
    tsd_files = sorted(glob.glob(os.path.join(root, f"{region}_*_tsd.tif")))
    first_year = int(os.path.basename(tsd_files[0]).split("_")[1])
    dist, early, n_vint = disturbance_mask(dist_dir, tsd_files[0],
                                           first_year)
    if not np.array_equal(dist, early):
        raise SystemExit(
            f"{region}: disturbance coverage over vintages <= {first_year} "
            f"differs from coverage over all {n_vint} - one mask can no "
            f"longer serve every tsd year (CR-0010 rule 2). Stop.")
    masks = {"nlcd": nl, "disturbance": dist}
    for name, m in masks.items():
        pin = pins["masks"][region][name]
        got = (int(m.sum()), mask_digest(m))
        if got != (pin["inside"], pin["sha256"]):
            raise SystemExit(f"{region} {name} mask {got} != pin "
                             f"{(pin['inside'], pin['sha256'])}. Stop.")
        print(f"   {region} {name}: inside {got[0]:,}  sha {got[1]}  ok")
    return masks, transform, crs, shape


# ---- subcommands -------------------------------------------------------

def write_manifest(path, files, root):
    with open(path, "w") as f:
        f.write("name\tsha256\tsize\tmtime_ns\n")
        for p in files:
            st = os.stat(p)
            f.write(f"{os.path.relpath(p, root)}\t{sha256_file(p)}\t"
                    f"{st.st_size}\t{st.st_mtime_ns}\n")


def cmd_manifest(args, pins):
    inscope = list_inscope(args.root, pins)
    if len(inscope) != pins["n_files"]:
        raise SystemExit(f"{len(inscope)} in-scope files, expected "
                         f"{pins['n_files']}")
    others = sorted(set(glob.glob(os.path.join(args.root, "*.tif")))
                    - set(inscope))
    os.makedirs(EVIDENCE, exist_ok=True)
    write_manifest(MANIFEST_INSCOPE, inscope, args.root)
    write_manifest(MANIFEST_OTHER, others, args.root)
    print(f"manifests: {len(inscope)} in-scope, {len(others)} other")


def read_manifest(path):
    with open(path) as f:
        next(f)
        rows = [line.rstrip("\n").split("\t") for line in f]
    return {r[0]: {"sha256": r[1], "size": int(r[2]), "mtime_ns": int(r[3])}
            for r in rows}


def cmd_backup(args, pins):
    man = read_manifest(MANIFEST_INSCOPE)
    os.makedirs(args.backup_dir, exist_ok=True)
    for name, row in man.items():
        src = os.path.join(args.root, name)
        dst = os.path.join(args.backup_dir, name)
        if os.path.exists(dst) and sha256_file(dst) == row["sha256"]:
            continue
        shutil.copyfile(src, dst)   # a real copy: new inode, no metadata
        if sha256_file(dst) != row["sha256"]:
            raise SystemExit(f"backup of {name} does not match manifest")
    print(f"backup: {len(man)} files in {args.backup_dir}, hashes verified")


def repair_one(path, mask, mask_name, pin_sha, nodata, dry_run=False):
    with rasterio.open(path) as src:
        if REPAIR_TAG in src.tags():
            return path, "already repaired", 0
        if src.shape != mask.shape:
            raise SystemExit(f"{path}: shape {src.shape} != mask "
                             f"{mask.shape}")
        if src.nodata != nodata:
            raise SystemExit(f"{path}: nodata {src.nodata} != {nodata}")
        arr = src.read(1)
        profile = src.profile.copy()
        struct = src.tags(ns="IMAGE_STRUCTURE")
        tags = src.tags()
    out = np.where(mask, arr, np.int16(nodata)).astype(arr.dtype)
    changed = int((out != arr).sum())
    if dry_run:
        return path, "dry run", changed
    if "PREDICTOR" in struct:
        profile["predictor"] = int(struct["PREDICTOR"])
    tmp = path + TMP_SUFFIX
    with rasterio.open(tmp, "w", **profile) as dst:
        dst.write(out, 1)
        tags.update({REPAIR_TAG: "CR-0010",
                     "GROUSE_REPAIR_MASK": mask_name,
                     "GROUSE_REPAIR_MASK_SHA256": pin_sha,
                     "GROUSE_REPAIR_DATE":
                         datetime.date.today().isoformat()})
        dst.update_tags(**tags)
    os.replace(tmp, path)
    return path, "repaired", changed


def cmd_repair(args, pins):
    files = args.files or list_inscope(args.root, pins)
    by_region = {}
    for p in files:
        by_region.setdefault(os.path.basename(p)[:2], []).append(p)
    for region, paths in sorted(by_region.items()):
        print(f"{region}: deriving masks")
        masks, *_ = region_masks(args.mask_root, args.dist_dir, region, pins)
        jobs = []
        for p in paths:
            feat = os.path.basename(p)[:-4].split("_", 2)[2]
            name = pins["feature_mask"][feat]
            jobs.append((p, masks[name], name,
                         pins["masks"][region][name]["sha256"]))
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as ex:
            futs = [ex.submit(repair_one, p, m, n, s, pins["nodata"],
                              args.dry_run) for p, m, n, s in jobs]
            for fut in concurrent.futures.as_completed(futs):
                p, status, changed = fut.result()
                print(f"   {os.path.basename(p)}: {status}, "
                      f"{changed:,} px changed")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["manifest", "backup", "repair"])
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="Directory holding the rasters to act on.")
    ap.add_argument("--mask-root", default=DEFAULT_ROOT,
                    help="Directory holding the nlcd and tsd rasters the "
                         "masks are derived from. Default: %(default)s")
    ap.add_argument("--dist-dir", default=DEFAULT_DIST)
    ap.add_argument("--backup-dir", default=DEFAULT_BACKUP)
    ap.add_argument("--files", nargs="+", default=None,
                    help="repair: only these files (rehearsal).")
    ap.add_argument("--pins", default=PINS)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pins = load_pins(args.pins)
    {"manifest": cmd_manifest, "backup": cmd_backup,
     "repair": cmd_repair}[args.command](args, pins)


if __name__ == "__main__":
    main()
