"""
generate_lidar_structure.py - CR-0036: 3DEP airborne-lidar forest-structure
layers on each region's template grid.

Features (int16, nodata -9999; "returns" = kept points with a valid HAG,
n(a,b) = count with a <= HAG < b, HAG in metres):

    lid_u05_2   n(0.5,2) / n(-2,2)          per mille   (occlusion-adjusted)
    lid_u1_3    n(1,3)   / n(-2,3)          per mille
    lid_u3_5    n(3,5)   / n(-2,5)          per mille
    lid_u5_10   n(5,10)  / n(-2,10)         per mille
    lid_p95     95th pct of HAG over returns >= 0.5 m (0 if < 5)  decimetres
    lid_wcov5   first returns > 5 m / all first returns   per mille
                (leaf-off: woody + conifer cover, NOT canopy closure)
    lid_sd      SD (ddof 0) of HAG over returns >= 0.5 m (0 if < 5)  dm

A ratio feature is NODATA where its denominator < LIDAR_MIN_DENOM; every
feature is NODATA where the cell has < LIDAR_MIN_RETURNS returns.

Pipeline (CR-0036 section 1):
  1. Cell assignment: per cell, the first work unit (assign_order: newest
     collect_end, then QL, then EPT, then name) whose pinned footprint
     contains the cell CENTRE (rasterize, all_touched=False). A cell whose
     unit delivers no kept return falls back to its next covering unit.
  2. Blocks of LIDAR_BLOCK_CELLS square; each unit assigned to a block's
     cells is read over the block footprint + LIDAR_PAD_M.
     EPT: readers.ept (requests 8, no resolution); LAS (rockyweb): tiles
     from the unit's .vpc, downloaded once to the scratch dir.
  3. PDAL READS ONLY. keep_points: Classification in {0,1,2,3,4,5,9} and
     not withheld (Withheld dimension, else ClassFlags & 0x04).
  4. transform_xy: the unit's PINNED PROJ pipeline (from_pipeline) to the
     template CRS; Z x the unit's z_to_m (1 for every EPT row).
  5. compute_hag: IDW^2 of the LIDAR_HAG_K nearest ground points within
     LIDAR_HAG_MAXDIST_M (<= LIDAR_PAD_M, so block seams are exact);
     ground HAG = 0; HAG < LIDAR_HAG_MIN_M or > LIDAR_HAG_MAX_M -> noise.
  6. bin_points: half-open cells on the template's pixel edges; a point
     counts only toward a cell assigned to its own unit.
  7. cell_metrics, encoders (raise on out-of-range; never clip).
  8. Blocks cached UNMASKED (metrics + meta) under a key of template grid,
     source-table sha256, recipe and units; masks applied at assembly.
  9. Assembly: staged .tmp, grid_mismatch(out, template) must be None,
     os.replace.

Year policy (section 2): static layer, masked per vintage Y:
  mask_a  disturbance between flight A and vintage Y (tsd at max(Y, A))
  mask_b  young regenerating stand when |Y - A| > YEAR_MATCH_TOLERANCE

Modes (repository root, in the conda env envs/lidar.yml):
    python generate_lidar_structure.py --pilot /tmp/lidar_pilot --region NH
        -> W1..W4 (+ W2seam, W2pad0, W3_hag_loo.json) for
           python check_lidar_structure.py --pilot /tmp/lidar_pilot
The full-region build writes data/ and is CR-0037 (not in this CR):
    python generate_lidar_structure.py --build --regions NH --cr0037
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

# ----------------------------------------------------------------------
# Recipe constants (part of the cache key)
# ----------------------------------------------------------------------
LIDAR_BLOCK_CELLS = 64
LIDAR_PAD_M = 60.0
LIDAR_HAG_K = 6
LIDAR_HAG_MAXDIST_M = 30.0
LIDAR_HAG_MIN_M = -2.0
LIDAR_HAG_MAX_M = 80.0
LIDAR_MIN_RETURNS = 50
LIDAR_MIN_DENOM = 20
LIDAR_MIN_TALL = 5
LIDAR_REGEN_YEARS = 20
LIDAR_DATE_SLACK_DAYS = 7
LIDAR_ASSIGN_POLICY = "newest"
EPT_REQUESTS = 8
KEEP_CLASSES = (0, 1, 2, 3, 4, 5, 9)
WITHHELD_BIT = 0x04
GROUND_CLASS = 2
NODATA = -9999
FIRST_TSD_YEAR = 2016                   # first tsd vintage on disk
GPS_EPOCH = dt.datetime(1980, 1, 6)     # adjusted standard = GPS sec - 1e9

LIDAR_FEATURES = ("lid_u05_2", "lid_u1_3", "lid_u3_5", "lid_u5_10",
                  "lid_p95", "lid_wcov5", "lid_sd")
_BINS = {"lid_u05_2": (0.5, 2.0), "lid_u1_3": (1.0, 3.0),
         "lid_u3_5": (3.0, 5.0), "lid_u5_10": (5.0, 10.0)}
META_BANDS = ("year", "doy", "n_returns", "n_ground", "n_nohag", "wu_index")

SOURCES_CSV = os.path.join(_here, "docs", "quality", "lidar",
                           "lidar_sources.csv")
FOOTPRINTS = os.path.join(_here, "docs", "quality", "lidar",
                          "lidar_footprints.geojson")

try:                                    # shared constants, if importable
    from models import TSD_MAX_YEARS
except Exception:                       # pragma: no cover (no torch here)
    TSD_MAX_YEARS = 30
try:
    from grouse_data import YEAR_MATCH_TOLERANCE
except Exception:                       # pragma: no cover
    YEAR_MATCH_TOLERANCE = 2


# ----------------------------------------------------------------------
# Pure core (pinned by tests/test_cr0036.py)
# ----------------------------------------------------------------------
def keep_points(classification, class_flags=None, withheld=None):
    """Section 1.3: class whitelist, withheld points dropped. The overlap
    flag (ClassFlags 0x08) does not drop a point."""
    keep = np.isin(np.asarray(classification), KEEP_CLASSES)
    if withheld is not None:
        keep &= ~np.asarray(withheld, bool)
    elif class_flags is not None:
        keep &= (np.asarray(class_flags).astype(np.int64) & WITHHELD_BIT) == 0
    return keep


def is_first(return_number):
    return np.asarray(return_number) == 1


def to_metres_z(z, row):
    return np.asarray(z, np.float64) * float(row["z_to_m"])


def _transformer(row, _cache={}):
    from pyproj import Transformer
    key = row["pipeline"]
    if key not in _cache:
        _cache[key] = Transformer.from_pipeline(key)
    return _cache[key]


def transform_xy(x, y, row):
    """Source XY -> template-CRS metres through the row's pinned pipeline."""
    gx, gy = _transformer(row).transform(np.asarray(x, np.float64),
                                         np.asarray(y, np.float64))
    return np.asarray(gx), np.asarray(gy)


def inverse_xy(x, y, row):
    from pyproj.enums import TransformDirection
    gx, gy = _transformer(row).transform(np.asarray(x, np.float64),
                                         np.asarray(y, np.float64),
                                         direction=TransformDirection.INVERSE)
    return np.asarray(gx), np.asarray(gy)


def check_source(row, header):
    """Refuse a source whose header disagrees with its pinned row."""
    if int(header["horiz_epsg"]) != int(row["horiz_epsg"]):
        raise ValueError(f"{row.get('work_unit')}: header CRS EPSG:"
                         f"{header['horiz_epsg']} != pinned {row['horiz_epsg']}")
    for k in ("xy_to_m", "z_to_m"):
        if not np.isclose(float(header[k]), float(row[k]), rtol=1e-9):
            raise ValueError(f"{row.get('work_unit')}: header {k} "
                             f"{header[k]} != pinned {row[k]}")


_QL_RANK = {"QL0": 0, "QL1": 1, "QL2": 2, "QL3": 3}


def assign_order(rows):
    """Newest collect_end first; ties: better QL, EPT before LAZ, name."""
    def key(r):
        end = dt.datetime.strptime(str(r["collect_end"]).replace("-", "/"),
                                   "%Y/%m/%d")
        return (-end.toordinal(), _QL_RANK.get(str(r.get("ql")), 9),
                0 if r.get("reader") == "ept" else 1, str(r["work_unit"]))
    return sorted(rows, key=key)


def bin_points(x, y, transform, shape):
    """Flat cell index on the template's half-open pixel edges; -1 outside."""
    H, W = shape
    inv = ~transform
    u = inv.a * x + inv.b * y + inv.c
    v = inv.d * x + inv.e * y + inv.f
    c = np.floor(u).astype(np.int64)
    r = np.floor(v).astype(np.int64)
    inside = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    return np.where(inside, r * W + c, -1)


def compute_hag(x, y, z, is_ground, k=None, maxdist=None):
    """HAG by inverse-distance-squared mean of the k nearest ground points
    within maxdist (XY, template metres). Ground HAG = 0; zero-distance
    neighbours -> their mean; no ground in range or noise -> NaN."""
    from scipy.spatial import cKDTree
    k = LIDAR_HAG_K if k is None else k
    maxdist = LIDAR_HAG_MAXDIST_M if maxdist is None else maxdist
    x, y, z = (np.asarray(a, np.float64) for a in (x, y, z))
    g = np.asarray(is_ground, bool)
    hag = np.full(x.size, np.nan)
    hag[g] = 0.0
    q = ~g
    if not g.any() or not q.any():
        return hag
    tree = cKDTree(np.column_stack([x[g], y[g]]))
    kk = min(k, int(g.sum()))
    d, i = tree.query(np.column_stack([x[q], y[q]]), k=kk,
                      distance_upper_bound=maxdist)
    if kk == 1:
        d, i = d[:, None], i[:, None]
    gz = np.append(z[g], np.nan)               # i == n -> missing
    zz = gz[i]
    ok = np.isfinite(d)
    zero = ok & (d == 0)
    w = np.where(ok & ~zero, 1.0 / np.where(d > 0, d, 1.0) ** 2, 0.0)
    num = np.nansum(np.where(ok & ~zero, w * zz, 0.0), axis=1)
    den = w.sum(axis=1)
    ground = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
    nz = zero.sum(axis=1)
    if nz.any():
        zmean = np.where(zero, zz, 0.0).sum(axis=1) / np.maximum(nz, 1)
        ground = np.where(nz > 0, zmean, ground)
    h = z[q] - ground
    h[(h < LIDAR_HAG_MIN_M) | (h > LIDAR_HAG_MAX_M)] = np.nan
    hag[q] = h
    return hag


def cell_metrics(cell, hag, first, n_cells):
    """Per-cell features (float64, NaN = NODATA) over points with a valid
    HAG; `cell` in [0, n_cells) (others ignored)."""
    cell = np.asarray(cell, np.int64)
    hag = np.asarray(hag, np.float64)
    first = np.asarray(first, bool)
    m = (cell >= 0) & (cell < n_cells) & np.isfinite(hag)
    c, h, f = cell[m], hag[m], first[m]
    out = {k: np.full(n_cells, np.nan) for k in LIDAR_FEATURES}
    n = np.bincount(c, minlength=n_cells)
    enough = n >= LIDAR_MIN_RETURNS
    for feat, (a, b) in _BINS.items():
        num = np.bincount(c, weights=((h >= a) & (h < b)), minlength=n_cells)
        den = np.bincount(c, weights=((h >= -2.0) & (h < b)), minlength=n_cells)
        ok = enough & (den >= LIDAR_MIN_DENOM)
        out[feat][ok] = 1000.0 * num[ok] / den[ok]
    nf = np.bincount(c, weights=f, minlength=n_cells)
    nf5 = np.bincount(c, weights=f & (h > 5.0), minlength=n_cells)
    ok = enough & (nf >= LIDAR_MIN_DENOM)
    out["lid_wcov5"][ok] = 1000.0 * nf5[ok] / nf[ok]
    tall = h >= 0.5
    tc, th = c[tall], h[tall]
    order = np.lexsort((th, tc))
    tc, th = tc[order], th[order]
    starts = np.searchsorted(tc, np.arange(n_cells))
    ends = np.searchsorted(tc, np.arange(n_cells), side="right")
    for i in np.flatnonzero(enough):
        seg = th[starts[i]:ends[i]]
        if seg.size >= LIDAR_MIN_TALL:
            out["lid_p95"][i] = 10.0 * np.percentile(seg, 95, method="linear")
            out["lid_sd"][i] = 10.0 * seg.std(ddof=0)
        else:
            out["lid_p95"][i] = 0.0
            out["lid_sd"][i] = 0.0
    return out


def _encode(values, lo, hi, name):
    v = np.asarray(values, np.float64)
    if not np.all(np.isfinite(v)):
        raise ValueError(f"{name}: non-finite input")
    r = np.rint(v)
    if r.size and (r.min() < lo or r.max() > hi or v.min() < lo or v.max() > hi):
        raise ValueError(f"{name}: value outside [{lo}, {hi}]")
    return r.astype(np.int16)


def lidar_share_encode(per_mille):
    """Per-mille share -> int16. Raises on NaN/inf or outside [0, 1000]."""
    return _encode(per_mille, 0, 1000, "lidar_share_encode")


def lidar_height_encode(decimetres):
    """Decimetres -> int16. Raises on NaN/inf or outside [0, 800]."""
    return _encode(decimetres, 0, 10 * LIDAR_HAG_MAX_M, "lidar_height_encode")


def encode_features(metrics):
    out = {}
    for f, v in metrics.items():
        a = np.full(v.shape, NODATA, np.int16)
        ok = np.isfinite(v)
        enc = lidar_height_encode if f in ("lid_p95", "lid_sd") \
            else lidar_share_encode
        a[ok] = enc(v[ok])
        out[f] = a
    return out


def tsd_years_at(A, tsd_by_year):
    """Years since last disturbance AT year A, from decoded tsd rasters
    keyed by vintage year. For A before the first vintage, uses
    tsd_FIRST - (FIRST - A); a negative result (disturbance after A) or
    tsd nodata -> NaN."""
    M = max(int(A), FIRST_TSD_YEAR)
    yrs = np.asarray(tsd_by_year[M], np.float64) - (M - int(A))
    return np.where(yrs >= 0, yrs, np.nan)


def mask_a(Y, A, years_at_max):
    """True = NODATA: a disturbance D = max(Y,A) - round(years) with
    min(Y,A) <= D <= max(Y,A); the undisturbed cap never masks; NaN masks."""
    Y, A = np.asarray(Y), np.asarray(A)
    yrs = np.asarray(years_at_max, np.float64)
    nan = ~np.isfinite(yrs)
    r = np.rint(np.where(nan, 0, yrs))
    capped = r >= TSD_MAX_YEARS
    D = np.maximum(Y, A) - r
    hit = (D >= np.minimum(Y, A)) & (D <= np.maximum(Y, A))
    return nan | (hit & ~capped)


def mask_b(Y, A, years_at_A):
    """True = NODATA: |Y - A| > tolerance and the cell was disturbed within
    LIDAR_REGEN_YEARS before A (inclusive); NaN masks when |Y - A| is
    beyond tolerance."""
    Y, A = np.asarray(Y), np.asarray(A)
    yrs = np.asarray(years_at_A, np.float64)
    gap = np.abs(Y - A) > YEAR_MATCH_TOLERANCE
    nan = ~np.isfinite(yrs)
    r = np.rint(np.where(nan, TSD_MAX_YEARS, yrs))
    young = (r >= 0) & (r <= LIDAR_REGEN_YEARS) & (r < TSD_MAX_YEARS)
    return gap & (young | nan)


# ----------------------------------------------------------------------
# Source table
# ----------------------------------------------------------------------
def load_sources(path=SOURCES_CSV, region=None):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("xy_to_m", "z_to_m"):
            r[k] = float(r[k])
        r["horiz_epsg"] = int(r["horiz_epsg"])
    if region is not None:
        rows = [r for r in rows if r.get("region") == region]
    return rows


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def recipe_digest():
    keys = sorted(k for k in globals() if k.startswith("LIDAR_")
                  or k in ("KEEP_CLASSES", "WITHHELD_BIT", "GROUND_CLASS",
                           "EPT_REQUESTS"))
    return hashlib.sha256(json.dumps({k: repr(globals()[k]) for k in keys},
                                     sort_keys=True).encode()).hexdigest()


def grid_digest(crs, transform, shape):
    return hashlib.sha256(json.dumps(
        [crs.to_wkt(), list(transform)[:6], list(shape)]).encode()).hexdigest()


# ----------------------------------------------------------------------
# Reading points (PDAL, imported lazily)
# ----------------------------------------------------------------------
DIMS = ("X", "Y", "Z", "Classification", "ReturnNumber", "GpsTime")


def _pdal_arrays(stages):
    import pdal
    p = pdal.Pipeline(json.dumps(stages))
    p.execute()
    arrs = [a for a in p.arrays if len(a)]
    meta = p.metadata
    if not arrs:
        return None, meta
    return np.concatenate(arrs), meta


def _header_from_meta(meta, row):
    """horiz_epsg, xy_to_m, z_to_m from PDAL reader metadata."""
    from pyproj import CRS
    md = meta.get("metadata", meta) if isinstance(meta, dict) else {}
    rd = next((v for k, v in md.items() if k.startswith("readers.")), {})
    if isinstance(rd, list):
        rd = rd[0]
    wkt = (rd.get("srs") or {}).get("wkt") or rd.get("comp_spatialreference")
    if not wkt:
        raise ValueError(f"{row['work_unit']}: no SRS in source header")
    crs = CRS.from_wkt(wkt)
    horiz = crs.sub_crs_list[0] if crs.is_compound else crs
    vert = crs.sub_crs_list[1] if crs.is_compound and \
        len(crs.sub_crs_list) > 1 else None
    xy = horiz.axis_info[0].unit_conversion_factor
    z = vert.axis_info[0].unit_conversion_factor if vert is not None \
        else float(row["z_to_m"])
    if row["reader"] == "ept":
        z = 1.0                                 # EPT Z is metres (A36-2-9)
    return dict(horiz_epsg=horiz.to_epsg() or -1, xy_to_m=xy, z_to_m=z)


def _vpc_tiles(row, bbox_src, scratch):
    """LAZ tile URLs of a rockyweb unit intersecting bbox (source CRS)."""
    import urllib.request
    vpc_url = row["location"].rstrip("/") + "/" + row.get("vpc", "")
    cache = os.path.join(scratch, f"{row['work_unit']}.vpc")
    if not os.path.exists(cache):
        urllib.request.urlretrieve(vpc_url, cache)
    with open(cache) as f:
        vpc = json.load(f)
    x0, y0, x1, y1 = bbox_src
    out = []
    for feat in vpc.get("features", []):
        pb = feat.get("properties", {}).get("proj:bbox")
        if not pb:
            continue
        bx0, by0, bx1, by1 = pb[0], pb[1], pb[-3 if len(pb) == 6 else 2], \
            pb[-2 if len(pb) == 6 else 3]
        if bx0 <= x1 and bx1 >= x0 and by0 <= y1 and by1 >= y0:
            href = next(iter(feat.get("assets", {}).values()), {}).get("href")
            if href:
                out.append(href if href.startswith("http") else
                           row["location"].rstrip("/") + "/" + href.lstrip("./"))
    return out


def _download(url, scratch):
    import urllib.request
    dest = os.path.join(scratch, os.path.basename(url))
    if not os.path.exists(dest):
        tmp = dest + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, dest)
    return dest


def read_unit(row, bbox_tpl, scratch, checked):
    """All points of one unit over a template-CRS bbox (x0, y0, x1, y1).
    Returns dict of arrays in template metres, or None."""
    corners_x = np.array([bbox_tpl[0], bbox_tpl[2], bbox_tpl[0], bbox_tpl[2]])
    corners_y = np.array([bbox_tpl[1], bbox_tpl[1], bbox_tpl[3], bbox_tpl[3]])
    sx, sy = inverse_xy(corners_x, corners_y, row)
    bb = (sx.min(), sy.min(), sx.max(), sy.max())
    if row["reader"] == "ept":
        stages = [{"type": "readers.ept", "filename": row["location"],
                   "requests": EPT_REQUESTS,
                   "bounds": f"([{bb[0]},{bb[2]}],[{bb[1]},{bb[3]}])"}]
        arr, meta = _pdal_arrays(stages)
        metas = [meta]
        arrs = [arr] if arr is not None else []
    else:
        arrs, metas = [], []
        for url in _vpc_tiles(row, bb, scratch):
            path = _download(url, scratch)
            stages = [{"type": "readers.las", "filename": path},
                      {"type": "filters.crop",
                       "bounds": f"([{bb[0]},{bb[2]}],[{bb[1]},{bb[3]}])"}]
            arr, meta = _pdal_arrays(stages)
            metas.append(meta)
            if arr is not None:
                arrs.append(arr)
    if row["work_unit"] not in checked:
        for meta in metas[:1]:
            check_source(row, _header_from_meta(meta, row))
        checked.add(row["work_unit"])
    if not arrs:
        return None
    a = np.concatenate(arrs)
    names = a.dtype.names
    for d in DIMS:
        if d not in names:
            raise ValueError(f"{row['work_unit']}: source lacks {d}")
    keep = keep_points(a["Classification"],
                       class_flags=a["ClassFlags"] if "ClassFlags" in names
                       else None,
                       withheld=a["Withheld"] if "Withheld" in names else None)
    a = a[keep]
    x, y = transform_xy(a["X"], a["Y"], row)    # pipeline handles XY units
    return dict(x=x, y=y, z=to_metres_z(a["Z"], row),
                ground=a["Classification"] == GROUND_CLASS,
                first=is_first(a["ReturnNumber"]),
                gps=np.asarray(a["GpsTime"], np.float64))


# ----------------------------------------------------------------------
# Blocks
# ----------------------------------------------------------------------
def gps_to_dates(gps):
    """Adjusted standard GPS time (GPS seconds - 1e9) -> (year, doy)."""
    secs = np.asarray(gps, np.float64) + 1e9
    days = np.floor(secs / 86400.0).astype(np.int64)
    base = np.datetime64(GPS_EPOCH.date(), "D")
    d = base + days.astype("timedelta64[D]")
    years = d.astype("datetime64[Y]").astype(np.int64) + 1970
    doy = (d - d.astype("datetime64[Y]")).astype(np.int64) + 1
    return years, doy, d


def _cell_median(cell, values, n_cells):
    out = np.full(n_cells, np.nan)
    if not cell.size:
        return out
    order = np.lexsort((values, cell))
    c, v = cell[order], values[order]
    starts = np.searchsorted(c, np.arange(n_cells))
    ends = np.searchsorted(c, np.arange(n_cells), side="right")
    has = ends > starts
    mid = (starts + ends - 1) // 2
    out[has] = v[mid[has]]
    return out


def process_block(block, units, transform, assign1, assign2, rows_by_idx,
                  scratch, pad=LIDAR_PAD_M):
    """One block: returns (metrics dict float, meta dict). block = (r0, c0,
    h, w) in window pixel coordinates; assign1/assign2 are the window's
    first/second-choice unit index rasters (-1 none)."""
    r0, c0, h, w = block
    n_cells = h * w
    bt = transform.__class__(transform.a, transform.b,
                             transform.c + c0 * transform.a,
                             transform.d, transform.e,
                             transform.f + r0 * transform.e)
    x0, y1 = bt.c, bt.f
    x1, y0 = x0 + w * bt.a, y1 + h * bt.e
    bbox = (min(x0, x1) - pad, min(y0, y1) - pad,
            max(x0, x1) + pad, max(y0, y1) + pad)
    a1 = assign1[r0:r0 + h, c0:c0 + w].ravel()
    a2 = assign2[r0:r0 + h, c0:c0 + w].ravel()
    metrics = {f: np.full(n_cells, np.nan) for f in LIDAR_FEATURES}
    meta = {b: np.zeros(n_cells, np.int64) for b in META_BANDS}
    meta["wu_index"][:] = -1
    checked = set()
    per_unit = {}

    def run(u):
        if u in per_unit:
            return per_unit[u]
        row = rows_by_idx[u]
        pts = read_unit(row, bbox, scratch, checked)
        if pts is None:
            per_unit[u] = None
            return None
        hag = compute_hag(pts["x"], pts["y"], pts["z"], pts["ground"])
        cell = bin_points(pts["x"], pts["y"], bt, (h, w))
        met = cell_metrics(cell, hag, pts["first"], n_cells)
        inb = cell >= 0
        ci = cell[inb]
        n_ret = np.bincount(ci, weights=np.isfinite(hag[inb]), minlength=n_cells)
        n_gr = np.bincount(ci, weights=pts["ground"][inb], minlength=n_cells)
        n_no = np.bincount(ci, weights=~np.isfinite(hag[inb]), minlength=n_cells)
        yrs, doy, d = gps_to_dates(pts["gps"][inb])
        med_day = _cell_median(ci, d.astype(np.int64).astype(np.float64),
                               n_cells)
        per_unit[u] = (met, n_ret, n_gr, n_no, med_day)
        return per_unit[u]

    for u in units:
        run(u)
    chosen = a1.copy()
    for i in range(n_cells):
        u = chosen[i]
        res = per_unit.get(u) if u >= 0 else None
        if (res is None or res[1][i] == 0) and a2[i] >= 0:
            chosen[i] = a2[i]               # fallback (A36-2-3)
    for u in np.unique(chosen[chosen >= 0]):
        res = run(int(u))
        sel = chosen == u
        if res is None:
            continue
        met, n_ret, n_gr, n_no, med_day = res
        row = rows_by_idx[int(u)]
        lo = np.datetime64(row["collect_start"].replace("/", "-"), "D") - \
            np.timedelta64(LIDAR_DATE_SLACK_DAYS, "D")
        hi = np.datetime64(row["collect_end"].replace("/", "-"), "D") + \
            np.timedelta64(LIDAR_DATE_SLACK_DAYS, "D")
        day = med_day.astype("int64").astype("datetime64[D]")
        in_win = np.isfinite(med_day) & (day >= lo) & (day <= hi)
        for f in LIDAR_FEATURES:
            metrics[f][sel] = np.where(in_win[sel], met[f][sel], np.nan)
        meta["year"][sel] = np.where(
            np.isfinite(med_day[sel]),
            day[sel].astype("datetime64[Y]").astype(np.int64) + 1970, 0)
        meta["doy"][sel] = np.where(
            np.isfinite(med_day[sel]),
            (day[sel] - day[sel].astype("datetime64[Y]")).astype(np.int64) + 1,
            0)
        meta["n_returns"][sel] = n_ret[sel]
        meta["n_ground"][sel] = n_gr[sel]
        meta["n_nohag"][sel] = n_no[sel]
        meta["wu_index"][sel] = int(u)
    return metrics, meta


# ----------------------------------------------------------------------
# Windows, assignment and writing
# ----------------------------------------------------------------------
def _template(rd):
    import rasterio
    path = rd.latest_raster_path("evt")
    with rasterio.open(path) as t:
        return t.crs, t.transform, (t.height, t.width), path


def assignment(rows, crs, transform, shape):
    """First- and second-choice unit index rasters (cell centre in the
    pinned footprint), indices into `rows` (already in assign_order)."""
    from rasterio.features import rasterize
    from rasterio.warp import transform_geom
    with open(FOOTPRINTS) as f:
        fc = json.load(f)
    geom = {}
    for feat in fc["features"]:
        geom.setdefault(feat["properties"]["work_unit"], []).append(
            transform_geom("EPSG:4326", crs, feat["geometry"]))
    a1 = np.full(shape, -1, np.int32)
    a2 = np.full(shape, -1, np.int32)
    for i in range(len(rows) - 1, -1, -1):          # lowest priority first
        gs = geom.get(rows[i]["work_unit"])
        if not gs:
            continue
        m = rasterize([(g, 1) for g in gs], out_shape=shape,
                      transform=transform, fill=0, all_touched=False,
                      dtype="uint8").astype(bool)
        a2[m] = a1[m]
        a1[m] = i
    return a1, a2


def window_at(crs, transform, shape, lon, lat, size):
    from rasterio.warp import transform as vtransform
    xs, ys = vtransform("EPSG:4326", crs, [lon], [lat])
    inv = ~transform
    c, r = inv * (xs[0], ys[0])
    r0, c0 = int(r) - size // 2, int(c) - size // 2
    H, W = shape
    if r0 < 0 or c0 < 0 or r0 + size > H or c0 + size > W:
        raise SystemExit(f"window at ({lon}, {lat}) leaves the template")
    return r0, c0, size, size


def compute_window(win, transform, a1, a2, rows, scratch, block=None,
                   pad=LIDAR_PAD_M, cache_dir=None, cache_tag=""):
    """Metrics and meta for a template window, block by block."""
    r0, c0, H, W = win
    block = block or LIDAR_BLOCK_CELLS
    metrics = {f: np.full((H, W), np.nan) for f in LIDAR_FEATURES}
    meta = {b: np.zeros((H, W), np.int64) for b in META_BANDS}
    meta["wu_index"][:] = -1
    for br in range(0, H, block):
        for bc in range(0, W, block):
            h, w = min(block, H - br), min(block, W - bc)
            key = None
            if cache_dir:
                key = os.path.join(cache_dir, hashlib.sha256(
                    f"{cache_tag}|{r0 + br}|{c0 + bc}|{h}|{w}|{pad}".encode()
                ).hexdigest() + ".npz")
                if os.path.exists(key):
                    z = np.load(key)
                    for f in LIDAR_FEATURES:
                        metrics[f][br:br + h, bc:bc + w] = z[f]
                    for b in META_BANDS:
                        meta[b][br:br + h, bc:bc + w] = z[b]
                    continue
            sub1 = a1[r0 + br:r0 + br + h, c0 + bc:c0 + bc + w]
            units = [int(u) for u in np.unique(sub1[sub1 >= 0])]
            bt = transform.__class__(transform.a, transform.b,
                                     transform.c + c0 * transform.a,
                                     transform.d, transform.e,
                                     transform.f + r0 * transform.e)
            met, mt = process_block(
                (br, bc, h, w), units, bt,
                a1[r0:r0 + H, c0:c0 + W], a2[r0:r0 + H, c0:c0 + W],
                rows, scratch, pad=pad)
            for f in LIDAR_FEATURES:
                metrics[f][br:br + h, bc:bc + w] = met[f].reshape(h, w)
            for b in META_BANDS:
                meta[b][br:br + h, bc:bc + w] = mt[b].reshape(h, w)
            if key:
                tmp = key + ".tmp.npz"
                np.savez(tmp, **{f: metrics[f][br:br + h, bc:bc + w]
                                 for f in LIDAR_FEATURES},
                         **{b: meta[b][br:br + h, bc:bc + w]
                            for b in META_BANDS})
                os.replace(tmp, key)
            print(f"      block ({br}, {bc}) units {units}", flush=True)
    return metrics, meta


def write_set(out_dir, prefix, metrics, meta, crs, transform, win,
              template_path, tags):
    import rasterio
    from grouse_data import grid_mismatch
    r0, c0, H, W = win
    wt = transform.__class__(transform.a, transform.b,
                             transform.c + c0 * transform.a,
                             transform.d, transform.e,
                             transform.f + r0 * transform.e)
    enc = encode_features({f: v.ravel() for f, v in metrics.items()})
    os.makedirs(out_dir, exist_ok=True)
    prof = dict(driver="GTiff", width=W, height=H, count=1, crs=crs,
                transform=wt, compress="deflate", tiled=True)
    for f in LIDAR_FEATURES:
        p = os.path.join(out_dir, f"{prefix}_{f}.tif")
        with rasterio.open(p + ".tmp", "w", dtype="int16", nodata=NODATA,
                           **prof) as d:
            d.write(enc[f].reshape(H, W), 1)
            d.update_tags(**tags, GROUSE_GRID="template-binned")
        with rasterio.open(p + ".tmp") as d, rasterio.open(template_path) as t:
            mm = grid_mismatch(d, t)
        if mm is not None:
            os.remove(p + ".tmp")
            raise SystemExit(f"{p}: grid_mismatch {mm} - refused")
        os.replace(p + ".tmp", p)
    p = os.path.join(out_dir, f"{prefix}_lidar_meta.tif")
    prof["count"] = len(META_BANDS)
    with rasterio.open(p + ".tmp", "w", dtype="int32", nodata=None,
                       **prof) as d:
        for i, b in enumerate(META_BANDS, 1):
            d.write(meta[b].astype(np.int32), i)
        d.update_tags(**tags)
    os.replace(p + ".tmp", p)


# ----------------------------------------------------------------------
# Pilot (CR-0036 section 6)
# ----------------------------------------------------------------------
W1_LONLAT, W1_CELLS = (-71.17, 43.08), 667          # 20 km
W3_CANDIDATES = ((-71.40, 44.20), (-71.68, 44.15), (-71.25, 44.26))
W2_CELLS, W3_CELLS, W4_CELLS = 128, 128, 400
LOO_SAMPLE = 200_000
STEEP_SLOPE = 0.30                                  # rise/run


def _best_window(score, size, stride):
    H, W = score.shape
    best, where = -np.inf, None
    for r in range(0, H - size + 1, stride):
        for c in range(0, W - size + 1, stride):
            s = score(r, c) if callable(score) else None
            if s is not None and s > best:
                best, where = s, (r, c, size, size)
    return where


def pick_w2(a1, rows):
    """NH block whose assigned cells split most evenly between an EPT unit
    and a LAS (rockyweb) unit."""
    is_ept = np.array([r["reader"] == "ept" for r in rows] + [False])
    H, W = a1.shape
    best, where = -1.0, None
    for r in range(0, H - W2_CELLS + 1, W2_CELLS // 2):
        for c in range(0, W - W2_CELLS + 1, W2_CELLS // 2):
            s = a1[r:r + W2_CELLS, c:c + W2_CELLS]
            s = s[s >= 0]
            if s.size < 0.9 * W2_CELLS ** 2:
                continue
            e = is_ept[s].mean()
            score = min(e, 1 - e)
            if score > best:
                best, where = score, (r, c, W2_CELLS, W2_CELLS)
    if where is None or best <= 0:
        raise SystemExit("no EPT/LAS seam window found")
    return where


def pick_w4(a1, rows):
    """A 400-cell window entirely inside one LAS (rockyweb) unit."""
    H, W = a1.shape
    for i, row in enumerate(rows):
        if row["reader"] != "las":
            continue
        for r in range(0, H - W4_CELLS + 1, W4_CELLS // 4):
            for c in range(0, W - W4_CELLS + 1, W4_CELLS // 4):
                if (a1[r:r + W4_CELLS, c:c + W4_CELLS] == i).all():
                    return (r, c, W4_CELLS, W4_CELLS)
    raise SystemExit("no window inside a single rockyweb unit")


def hag_loo(x, y, z, ground, seed=0):
    """C9 evidence: leave-one-out ground-Z RMSE by slope class for the
    pinned IDW and for the nearest-1 control (no distance limit)."""
    from scipy.spatial import cKDTree
    gx, gy, gz = x[ground], y[ground], z[ground]
    rng = np.random.default_rng(seed)
    idx = rng.choice(gx.size, size=min(LOO_SAMPLE, gx.size), replace=False)
    tree = cKDTree(np.column_stack([gx, gy]))
    d, i = tree.query(np.column_stack([gx[idx], gy[idx]]), k=LIDAR_HAG_K + 1,
                      distance_upper_bound=LIDAR_HAG_MAXDIST_M)
    d, i = d[:, 1:], i[:, 1:]                  # leave self out
    gzz = np.append(gz, np.nan)[i]
    ok = np.isfinite(d) & (d > 0)
    w = np.where(ok, 1.0 / np.where(ok, d, 1.0) ** 2, 0.0)
    pred = np.where(w.sum(1) > 0, np.nansum(w * np.nan_to_num(gzz), 1)
                    / np.where(w.sum(1) > 0, w.sum(1), 1), np.nan)
    d1, i1 = tree.query(np.column_stack([gx[idx], gy[idx]]), k=2)
    nn1 = gz[i1[:, 1]]
    # local slope from a plane fit to the 6 neighbours
    slope = np.full(idx.size, np.nan)
    for j in range(idx.size):
        nb = i[j][np.isfinite(d[j])]
        if nb.size >= 3:
            A = np.column_stack([gx[nb] - gx[idx[j]], gy[nb] - gy[idx[j]],
                                 np.ones(nb.size)])
            coef = np.linalg.lstsq(A, gz[nb], rcond=None)[0]
            slope[j] = float(np.hypot(coef[0], coef[1]))
    out = {}
    for name, sel in (("flat", slope < STEEP_SLOPE),
                      ("steep", slope >= STEEP_SLOPE)):
        e1 = (pred - gz[idx])[sel & np.isfinite(pred)]
        e0 = (nn1 - gz[idx])[sel]
        out[name] = dict(n=int(sel.sum()),
                         rmse_idw=float(np.sqrt(np.mean(e1 ** 2))) if e1.size else None,
                         rmse_nn1=float(np.sqrt(np.mean(e0 ** 2))) if e0.size else None)
    return out


def pilot(out_dir, region, scratch, workers):
    from grouse_data import GrouseData
    rd = GrouseData()[region]
    crs, transform, shape, tpath = _template(rd)
    rows = assign_order(load_sources(region=region))
    if not rows:
        raise SystemExit(f"no {region} rows in {SOURCES_CSV}")
    a1, a2 = assignment(rows, crs, transform, shape)
    tags = dict(GROUSE_SOURCE="3DEP", GROUSE_LIDAR_SOURCES=json.dumps(
        {"sha256": file_sha256(SOURCES_CSV),
         "units": {i: r["work_unit"] for i, r in enumerate(rows)}}),
        GROUSE_RECIPE=recipe_digest())
    cache = os.path.join(scratch, "blocks")
    os.makedirs(cache, exist_ok=True)
    tag = "|".join([grid_digest(crs, transform, shape),
                    file_sha256(SOURCES_CSV), recipe_digest()])
    wins = {"W1": window_at(crs, transform, shape, *W1_LONLAT, W1_CELLS),
            "W2": pick_w2(a1, rows), "W4": pick_w4(a1, rows)}
    for lon, lat in W3_CANDIDATES:
        try:
            w3 = window_at(crs, transform, shape, lon, lat, W3_CELLS)
        except SystemExit:
            continue
        if (a1[w3[0]:w3[0] + W3_CELLS, w3[1]:w3[1] + W3_CELLS] >= 0).mean() > 0.95:
            wins["W3"] = w3
            break
    if "W3" not in wins:
        raise SystemExit("no covered W3 candidate")
    import time
    log = {}
    for name, win in wins.items():
        t0 = time.time()
        print(f"{name}: window {win}", flush=True)
        met, meta = compute_window(win, transform, a1, a2, rows, scratch,
                                   cache_dir=cache, cache_tag=tag)
        write_set(out_dir, name, met, meta, crs, transform, win, tpath, tags)
        log[name] = dict(window=win, seconds=time.time() - t0,
                         returns=int(meta["n_returns"].sum()))
        if name == "W2":
            for pfx, blk, pad in (("W2seam", W2_CELLS, LIDAR_PAD_M),
                                  ("W2pad0", LIDAR_BLOCK_CELLS, 0.0)):
                m2, mt2 = compute_window(win, transform, a1, a2, rows,
                                         scratch, block=blk, pad=pad)
                write_set(out_dir, pfx, m2, mt2, crs, transform, win,
                          tpath, tags)
        if name == "W3":
            r0, c0, H, W = win
            bt = transform.__class__(transform.a, transform.b,
                                     transform.c + c0 * transform.a,
                                     transform.d, transform.e,
                                     transform.f + r0 * transform.e)
            bbox = (bt.c, bt.f + H * bt.e, bt.c + W * bt.a, bt.f)
            u = int(np.bincount(a1[r0:r0 + H, c0:c0 + W][
                a1[r0:r0 + H, c0:c0 + W] >= 0]).argmax())
            pts = read_unit(rows[u], bbox, scratch, set())
            with open(os.path.join(out_dir, "W3_hag_loo.json"), "w") as f:
                json.dump(hag_loo(pts["x"], pts["y"], pts["z"],
                                  pts["ground"]), f, indent=1)
    with open(os.path.join(out_dir, "pilot_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps(log, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pilot", metavar="OUT_DIR")
    ap.add_argument("--region", default="NH")
    ap.add_argument("--scratch", default="/tmp/lidar_scratch")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--build", action="store_true",
                    help="full-region build into data/ (CR-0037 only)")
    ap.add_argument("--cr0037", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.scratch, exist_ok=True)
    if args.build:
        if not args.cr0037:
            raise SystemExit("--build writes data/ and needs CR-0037's "
                             "approval (pass --cr0037 once it is approved)")
        raise SystemExit("--build is delivered by CR-0037")
    if not args.pilot:
        ap.print_help()
        sys.exit(2)
    pilot(args.pilot, args.region, args.scratch, args.workers)


if __name__ == "__main__":
    main()
