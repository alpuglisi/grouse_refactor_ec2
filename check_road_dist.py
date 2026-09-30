"""CR-0014 acceptance for the regenerated road_dist rasters.

Independent of generate_road_distance.py by construction: it never
imports it, and it keeps its OWN copy of the TIGER 2023 files in
~/.cache/grouse_cr0014/ (downloaded here, never written to data/), from
which it re-derives the county-coverage mask T, the Canada set C and the
exact-distance truth. Constants and the recipe live in
docs/quality/cr0014_pins.json.

Subcommands:
    fetch    download this verifier's TIGER copy (atomic, zip-validated)
    pin      compute T and C per region from that copy; write C's count
             and digest into the pins file (run BEFORE regeneration)
    backup   copy the 30 road_dist files + write a manifest (B0's input)
    check    run every gate against --root

Canada rule (the recipe, identical in the generator):
    D_road  float64 metres, EDT on the grid padded by pad_px, roads
            rasterised all_touched=True, cropped to the grid
    T       county-union mask on the grid, all_touched=True
    L       ~T & evt not in NODATA_SENTINELS & evt != 7292 (Open Water),
            evt = {R}_2024_evt.tif
    D_can   EDT to the nearest L pixel on the grid
    C       T & (D_can < D_road)          (strict)
The raster must be -9999 exactly on ~T | C.

Gates: R0 R0b R1 R2 R3 RD1-RD5 R6 R7 R8 B0 (exit 1 if any fails).
Observations: X1 |C| and records with centre in C; X2 pixels in T\\C
closer to a non-US grid edge than to any road; X3 sample points whose
nearest road lies outside grid + pad.

RD thresholds (derivation, CR-0014): truth is measured from the pixel
centre, so the EDT (pixel centre to nearest road-marked pixel centre)
differs from it by at most the road's in-pixel offset (<= 21.2 m, half
the 30 m diagonal, either sign) plus log1p encoding (0.5 * (1 + d) /
1000 m, < 18 m below 35 km; max in-coverage distance is 17.2 km): 60 m
for p99 and the exceedance count leaves headroom (observed max 21.4 m
over 4,000 points per region in review). all_touched widens each road,
so correct rasters read slightly LOW - hence the signed-median band
[-20, +5] m (observed -8.8 m).
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile

import numpy as np
import rasterio
import rasterio.features
from affine import Affine
from rasterio.transform import array_bounds
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grouse_data import NODATA_SENTINELS  # noqa: E402

PINS = os.path.join(HERE, "docs/quality/cr0014_pins.json")
CACHE = os.path.expanduser("~/.cache/grouse_cr0014")
TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER{y}/{kind}/{name}"
NODATA = -9999
OPEN_WATER = 7292


def load_pins(path=PINS):
    with open(path) as f:
        return json.load(f)


def digest(mask):
    return hashlib.sha256(np.packbits(mask.ravel())).hexdigest()[:32]


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ---- this verifier's TIGER copy -------------------------------------------

def zip_ok(path):
    try:
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None
    except zipfile.BadZipFile:
        return False


def fetch(url, path):
    if os.path.exists(path) and zip_ok(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    urllib.request.urlretrieve(url, part)
    if not zip_ok(part):
        os.remove(part)
        raise RuntimeError(f"invalid zip from {url}")
    os.replace(part, path)
    return path


def grid_of(template):
    with rasterio.open(template) as s:
        return s.crs, s.transform, s.height, s.width


def padded(transform, h, w, pad_px):
    t = transform * Affine.translation(-pad_px, -pad_px)
    return t, h + 2 * pad_px, w + 2 * pad_px


def region_counties(pins, crs, transform, h, w):
    """Counties intersecting the padded grid bbox (densified before
    reprojection), in the grid CRS."""
    import geopandas as gpd
    from shapely.geometry import box
    y, pad = pins["tiger_year"], pins["pad_px"]
    name = f"tl_{y}_us_county.zip"
    path = fetch(TIGER_URL.format(y=y, kind="COUNTY", name=name),
                 os.path.join(CACHE, name))
    counties = gpd.read_file(path)
    pt, ph, pw = padded(transform, h, w, pad)
    x0, y0, x1, y1 = array_bounds(ph, pw, pt)
    fp = gpd.GeoSeries([box(min(x0, x1), min(y0, y1), max(x0, x1),
                            max(y0, y1)).segmentize(1000.0)], crs=crs)
    fp = fp.to_crs(counties.crs).iloc[0]
    return counties[counties.intersects(fp)].to_crs(crs)


def region_roads(pins, county_rows, crs):
    import geopandas as gpd
    import pandas as pd
    y = pins["tiger_year"]
    frames, zips = [], {}
    for st, cf in zip(county_rows["STATEFP"], county_rows["COUNTYFP"]):
        name = f"tl_{y}_{st}{cf}_roads.zip"
        path = fetch(TIGER_URL.format(y=y, kind="ROADS", name=name),
                     os.path.join(CACHE, name))
        zips[name] = path
        g = gpd.read_file(path)
        frames.append(g[g["MTFCC"].isin(pins["mtfcc"])][["geometry"]])
    roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                             geometry="geometry", crs=frames[0].crs)
    return roads.to_crs(crs), zips


# ---- the recipe -------------------------------------------------------------

def coverage_mask(county_rows, transform, h, w):
    return rasterio.features.rasterize(
        ((g, 1) for g in county_rows.geometry if g is not None),
        out_shape=(h, w), transform=transform, fill=0, default_value=1,
        all_touched=True, dtype="uint8").astype(bool)


def road_distance(roads, transform, h, w, pad_px):
    pt, ph, pw = padded(transform, h, w, pad_px)
    m = rasterio.features.rasterize(
        ((g, 1) for g in roads.geometry if g is not None),
        out_shape=(ph, pw), transform=pt, fill=0, default_value=1,
        all_touched=True, dtype="uint8")
    d = distance_transform_edt(m == 0, sampling=(abs(transform.e),
                                                 abs(transform.a)))
    return d[pad_px:pad_px + h, pad_px:pad_px + w]


def canada_land(T, evt):
    return ~T & ~np.isin(evt, NODATA_SENTINELS) & (evt != OPEN_WATER)


def canada_set(T, L, d_road, transform):
    """C = T & (D_can < D_road), strict. Pure function of arrays. With no
    L at all D_can is +inf, so C is empty - scipy's EDT of an
    all-foreground array is finite and would mask pixels near a corner."""
    if not L.any():
        return np.zeros_like(T)
    d_can = distance_transform_edt(~L, sampling=(abs(transform.e),
                                                 abs(transform.a)))
    return T & (d_can < d_road)


def derive(pins, mask_root, region):
    evt_path = os.path.join(mask_root, f"{region}_{pins['evt_year']}_evt.tif")
    if sha_file(evt_path) != pins["evt_sha256"][region]:
        raise SystemExit(f"{evt_path}: sha256 differs from the pinned evt")
    crs, transform, h, w = grid_of(evt_path)
    counties = region_counties(pins, crs, transform, h, w)
    roads, zips = region_roads(pins, counties, crs)
    T = coverage_mask(counties, transform, h, w)
    d_road = road_distance(roads, transform, h, w, pins["pad_px"])
    with rasterio.open(evt_path) as s:
        evt = s.read(1)
    L = canada_land(T, evt)
    C = canada_set(T, L, d_road, transform)
    return dict(crs=crs, transform=transform, h=h, w=w, counties=counties,
                roads=roads, zips=zips, T=T, L=L, C=C, d_road=d_road)


# ---- RD sampling --------------------------------------------------------------

def strata(D, home_fips, pins):
    """Boolean masks of the five strata, all within T \\ C."""
    T, C, tr = D["T"], D["C"], D["transform"]
    samp = (abs(tr.e), abs(tr.a))
    h, w = T.shape
    state = rasterio.features.rasterize(
        ((g, int(fp)) for g, fp in zip(D["counties"].geometry,
                                       D["counties"]["STATEFP"])),
        out_shape=(h, w), transform=tr, fill=0, all_touched=False,
        dtype="uint8")
    home = state == int(home_fips)
    other = (state != 0) & ~home
    d_sl = np.where(home, distance_transform_edt(~other, sampling=samp),
                    distance_transform_edt(~home, sampling=samp))
    d_cov = distance_transform_edt(T, sampling=samp)
    rr, cc = np.indices((h, w), dtype=np.int32)
    d_edge = np.minimum.reduce([rr, cc, h - 1 - rr, w - 1 - cc]) * samp[0]
    ok = T & ~C
    return {
        "uniform": ok,
        "interior": ok & (d_cov > 5000) & (d_sl > 5000) & (d_edge > 5000),
        "state_line": ok & (d_sl <= 5000),
        "grid_edge": ok & (d_edge <= 10000),
        "coverage_edge": ok & (d_cov <= 5000),
    }


def sample(mask, n, seed):
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return idx
    rng = np.random.default_rng(seed)
    return rng.choice(idx, size=min(n, idx.size), replace=False)


def rd_stats(err, excluded, t):
    """RD1-RD5 for one stratum. err in metres (raster - truth)."""
    a = np.abs(err)
    return {
        "RD1": (float(np.median(a)), float(np.median(a)) <= t["rd1_median_abs_m"]),
        "RD2": (float(np.percentile(a, 99)),
                float(np.percentile(a, 99)) <= t["rd2_p99_abs_m"]),
        "RD3": (int((a > t["rd3_max_abs_m"]).sum()),
                int((a > t["rd3_max_abs_m"]).sum()) == 0),
        "RD4": (float(np.median(err)),
                t["rd4_signed_band_m"][0] <= float(np.median(err))
                <= t["rd4_signed_band_m"][1]),
        "RD5": (int(excluded), int(excluded) == 0),
    }


# ---- subcommands --------------------------------------------------------------

def cmd_fetch(args, pins):
    for r in args.regions:
        crs, tr, h, w = grid_of(os.path.join(
            args.mask_root, f"{r}_{pins['evt_year']}_evt.tif"))
        rows = region_counties(pins, crs, tr, h, w)
        _, zips = region_roads(pins, rows, crs)
        print(f"{r}: {len(zips)} county road files in {CACHE}")


def cmd_pin(args, pins):
    for r in args.regions:
        D = derive(pins, args.mask_root, r)
        pins["T"][r] = {"inside": int(D["T"].sum()), "sha256": digest(D["T"])}
        pins["C"][r] = {"count": int(D["C"].sum()), "sha256": digest(D["C"])}
        print(f"{r}: T {pins['T'][r]}  C {pins['C'][r]}  "
              f"road files {len(D['zips'])}", flush=True)
    with open(args.pins, "w") as f:
        json.dump(pins, f, indent=2)
        f.write("\n")


def cmd_backup(args, pins):
    os.makedirs(args.backup_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.root, "*_road_dist.tif")))
    with open(args.manifest, "w") as m:
        m.write("name\tsha256\tsize\tmtime_ns\n")
        for p in files:
            st = os.stat(p)
            sha = sha_file(p)
            m.write(f"{os.path.basename(p)}\t{sha}\t{st.st_size}\t"
                    f"{st.st_mtime_ns}\n")
            dst = os.path.join(args.backup_dir, os.path.basename(p))
            shutil.copyfile(p, dst)
            if sha_file(dst) != sha:
                raise SystemExit(f"backup of {p} does not verify")
    print(f"backup: {len(files)} files, manifest {args.manifest}")


def cmd_check(args, pins):
    from models import road_dist_decode
    rows = []

    def add(gid, kind, subj, val, req, ok=None):
        rows.append((gid, kind, subj, str(val), str(req), ok))

    if "B0" in args.gates:
        man = {}
        with open(args.manifest) as f:
            next(f)
            for line in f:
                n, sha, *_ = line.rstrip("\n").split("\t")
                man[n] = sha
        bad = [n for n, s in man.items()
               if sha_file(os.path.join(args.backup_dir, n)) != s]
        add("B0", "GATE", f"backup ({len(man)})", bad or "all match",
            "all match", not bad)
    if "R8" in args.gates:
        n = len(glob.glob(os.path.join(args.cache_dir, "patches_*")))
        add("R8", "GATE", args.cache_dir, n, 0, n == 0)

    t = pins["rd_thresholds"]
    for r in args.regions:
        D = derive(pins, args.mask_root, r)
        T, C = D["T"], D["C"]
        add("R0", "GATE", f"{r} T", (int(T.sum()), digest(T)),
            (pins["T"][r]["inside"], pins["T"][r]["sha256"]),
            (int(T.sum()), digest(T)) == (pins["T"][r]["inside"],
                                          pins["T"][r]["sha256"]))
        if "R0b" in args.gates:
            diff = [n for n, p in D["zips"].items()
                    if not os.path.exists(os.path.join(args.roads_dir, n))
                    or sha_file(os.path.join(args.roads_dir, n)) != sha_file(p)]
            add("R0b", "GATE", f"{r} road zips vs {args.roads_dir}",
                diff or "all identical", "all identical", not diff)
        files = sorted(glob.glob(os.path.join(args.root,
                                              f"{r}_*_road_dist.tif")))
        if args.files:
            files = [f for f in files if os.path.basename(f) in args.files]
        shas = {sha_file(f) for f in files}
        if not args.files:
            add("R3", "GATE", f"{r} year-copies ({len(files)})",
                f"{len(shas)} distinct", 1, len(shas) == 1)
        if not files:
            add("R1", "GATE", r, "no files", "files", False)
            continue
        with rasterio.open(files[0]) as s:
            arr = s.read(1)
        nod = arr == NODATA
        n1 = int((~T & ~nod).sum())
        add("R1", "GATE", r, n1, 0, n1 == 0)
        got = (int((nod & T).sum()), digest(nod & T))
        want = (pins["C"][r]["count"], pins["C"][r]["sha256"])
        add("R2", "GATE", f"{r} nodata∩T", got, f"C pin {want}",
            got == want and (int(C.sum()), digest(C)) == want)
        for f in files:
            with rasterio.open(f) as s:
                tags = s.tags()
                sig = (dict(s.profile), s.tags(ns="IMAGE_STRUCTURE"))
            add("R7", "GATE", os.path.basename(f),
                tags.get("GROUSE_COVERAGE"), "present",
                "GROUSE_COVERAGE" in tags)
            bak = os.path.join(args.backup_dir, os.path.basename(f))
            if os.path.exists(bak):
                with rasterio.open(bak) as b:
                    bsig = (dict(b.profile), b.tags(ns="IMAGE_STRUCTURE"))
                add("R6", "GATE", os.path.basename(f),
                    "identical" if sig == bsig else "differs", "identical",
                    sig == bsig)
        # RD1-RD5
        from shapely import STRtree, points
        tree = STRtree(np.asarray(D["roads"].geometry.values))
        geoms = np.asarray(D["roads"].geometry.values)
        tr, h, w = D["transform"], D["h"], D["w"]
        pt, ph, pw = padded(tr, h, w, pins["pad_px"])
        from shapely.geometry import box
        x0, y0, x1, y1 = array_bounds(ph, pw, pt)
        padbox = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        home = pins["state_fips"][r]
        for i, (name, m) in enumerate(strata(D, home, pins).items()):
            idx = sample(m, pins["rd_points_per_stratum"],
                         pins["rd_seed"] + 100 * i + ord(r[0]))
            rr, cc = np.unravel_index(idx, (h, w))
            xs, ys = rasterio.transform.xy(tr, rr, cc)
            pts = points(np.asarray(xs), np.asarray(ys))
            near, dist = tree.query_nearest(pts, return_distance=True,
                                            all_matches=False)
            truth = np.empty(len(pts))
            truth[near[0]] = dist
            enc = arr[rr, cc]
            excluded = int((enc == NODATA).sum())
            val = road_dist_decode(enc[enc != NODATA])
            err = val - truth[enc != NODATA]
            for gid, (v, ok) in rd_stats(err, excluded, t).items():
                add(gid, "GATE", f"{r} {name} (n={len(idx)})",
                    f"{v:.1f}" if isinstance(v, float) else v,
                    "see pins", ok)
            outside = int(sum(not geoms[j].intersects(padbox)
                              for j in near[1]))
            add("X3", "OBS", f"{r} {name}", outside, "report")
        # X1, X2
        add("X1", "OBS", f"{r} |C|", int(C.sum()), "report")
        frame = np.zeros_like(T)
        frame[0, :] = frame[-1, :] = frame[:, 0] = frame[:, -1] = True
        edge_out = frame & ~T
        if edge_out.any():
            d_e = distance_transform_edt(~edge_out,
                                         sampling=(abs(tr.e), abs(tr.a)))
            add("X2", "OBS", f"{r} T\\C nearer a non-US edge than a road",
                int((T & ~C & (d_e < D["d_road"])).sum()), "report")
        try:
            from grouse_data import GrouseData
            from pyproj import Transformer
            rd = GrouseData()[r]
            to = Transformer.from_crs("EPSG:4326", D["crs"], always_xy=True)
            for kind in ("positives", "negatives"):
                df = getattr(rd, kind)("all")
                x, y = to.transform(df["longitude"].values,
                                    df["latitude"].values)
                rows_, cols_ = rasterio.transform.rowcol(tr, x, y)
                rows_, cols_ = np.asarray(rows_), np.asarray(cols_)
                inb = (rows_ >= 0) & (rows_ < h) & (cols_ >= 0) & (cols_ < w)
                n = int(C[rows_[inb], cols_[inb]].sum())
                add("X1", "OBS", f"{r} {kind} centre in C", n, "report")
        except Exception as e:  # observation only; never fails the check
            add("X1", "OBS", f"{r} records", f"skipped: {e}", "report")
        del D
        print(f"{r}: checked", flush=True)

    failed = [x for x in rows if x[1] == "GATE" and x[5] is False]
    text = "\n".join(
        f"{g:4s} {k:4s} {'' if ok is None else ('PASS' if ok else 'FAIL'):4s} "
        f"{s:40s} value={v}  required={q}" for g, k, s, v, q, ok in rows)
    text += (f"\n\n{len(rows)} rows, {len(failed)} gate failure(s): "
             + ("FAIL" if failed else "ALL GATES PASS"))
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    sys.exit(1 if failed else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "pin", "backup", "check"])
    ap.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    ap.add_argument("--root", default=os.path.join(HERE, "data/landfire"),
                    help="Directory holding the road_dist rasters to check.")
    ap.add_argument("--mask-root", default=os.path.join(HERE, "data/landfire"),
                    help="Directory holding {R}_<evt_year>_evt.tif.")
    ap.add_argument("--roads-dir", default=os.path.join(HERE, "data/roads"),
                    help="The generator's road cache, for R0b.")
    ap.add_argument("--backup-dir",
                    default="/home/ec2-user/grouse_backup/CR-0014")
    ap.add_argument("--manifest", default=os.path.join(
        HERE, "docs/quality/evidence/CR-0014-manifest.tsv"))
    ap.add_argument("--cache-dir", default=os.path.join(HERE, "data/cache"))
    ap.add_argument("--files", nargs="+", default=None,
                    help="check: only these file names (rehearsal).")
    ap.add_argument("--gates", nargs="+",
                    default=["B0", "R0b", "R8"],
                    help="Optional gates to include besides the per-region "
                         "ones (R0-R3, RD1-RD5, R6, R7 always run).")
    ap.add_argument("--pins", default=PINS)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    pins = load_pins(args.pins)
    {"fetch": cmd_fetch, "pin": cmd_pin, "backup": cmd_backup,
     "check": cmd_check}[args.command](args, pins)


if __name__ == "__main__":
    main()
