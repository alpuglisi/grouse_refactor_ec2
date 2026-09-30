#!/usr/bin/env python3
"""
acceptance_split.py - CR-0013 acceptance gates for CR-0012's pooled split
and pooled negative draw.

Independence (CR-0013 design rule 1): this script never imports
prepare_training_data, generate_negatives, analyze_grouse, train,
dataset, models or regions. Its third-party dependencies are numpy,
pandas, scipy, pyproj, rasterio and geopandas, all imported inside the
functions that use them, so `standing_checks` pulls in only numpy, pandas
and scipy. The normative functions CR-0013 lists (pinned at 05d788d) are
re-implemented here from their source; regions.py is parsed, not imported.

Gates (GATE, exact): E0-E14 (incl. E1p) on the pipeline's files and R1-R4,
which replay CR-0012 section 2 from the inputs and compare full rows.
CR-0017 section 3 adds E13 (no N or C row within BUFFER_M of the
sightings' acquisition-domain edge) and rule (b) of pool step 6 to the
replay's buffer_drop; the domain is built here from the county file, never
from regions or generate_negatives (CR-0013 design rule 1).
CR-0019 section 3 adds E14 (every P and N year is an integer >= YEAR_MIN,
every non-null C year >= YEAR_MIN; the pooled P and N year sets are equal)
and the year floor to the replay: positives step 2 keeps habitat rows with
year >= YEAR_MIN (before thinning; a null evaluated-sighting year raises)
and pool step 1 drops candidates with a non-null year < YEAR_MIN. YEAR_MIN
is the config constant; E11 checks the regions.py literal (parsed, not
imported).
Observations (OBS, never blocking): O1-O10.

Usage:
    python acceptance_split.py [--data-root DIR] [--config PATH]
    python acceptance_split.py --emit-reference DIR     # replay's own artifacts
    python acceptance_split.py --calibrate              # after every GATE passes
    python acceptance_split.py --standing               # standing subset only

Exit code 0 only when every GATE passes (full run), the replay succeeds
(--emit-reference) or standing_checks does not raise (--standing).
There is no flag, environment variable or config key that disables or
downgrades a GATE (CR-0013 design rule 3).
"""
import argparse
import ast
import csv
import datetime
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "docs", "quality", "acceptance_split.json")
SPLITS = ("train", "val")
P_KINDS = ("thinned_positives", "train_positives", "val_positives")
N_KINDS = ("negatives", "train_negatives", "val_negatives")
ENV_KEYS = ("pandas", "numpy", "scipy", "pyproj", "PROJ", "rasterio", "GDAL", "geopandas",
            "shapely", "pyogrio", "op_4326_5070")
ENV_DESCRIPTIVE = ("op_rule",)     # config-only text, not a measured value
GATE_IDS = ("E0", "E1", "E1p", "E2", "E3", "E4", "E5", "E6", "E7", "E8",
            "E9", "E10", "E11", "E12", "E13", "E14", "R1", "R2", "R3", "R4")
OBS_IDS = tuple(f"O{i}" for i in range(1, 11))


class AcceptanceError(RuntimeError):
    """standing_checks failure. A real exception, never an assert, so it
    survives `python -O`."""


class ReplayError(RuntimeError):
    """A raise that CR-0012 section 2 specifies (or a premise it states
    that the inputs violate)."""


class MissingInput(Exception):
    def __init__(self, relpath):
        super().__init__(f"missing {relpath}")
        self.relpath = relpath


# ==========================================================================
# Config, paths, digests
# ==========================================================================
REQUIRED_FLOAT_REL_TOL = 1e-12   # CR-0013 "floats to relative 1e-12"; not configurable (rule 3)
REQUIRED_DOMAIN_EDGE = {"source": "paths.county_polygons",   # CR-0017 section 3; not configurable
                        "edge_crs": "EPSG:5070"}


class ConfigError(ValueError):
    """A config that would downgrade a GATE (CR-0013 design rule 3)."""


def load_config(path=None):
    path = os.path.abspath(path or DEFAULT_CONFIG)
    with open(path, "rb") as f:
        raw = f.read()
    cfg = json.loads(raw.decode("utf-8"))
    tol = cfg.get("comparison", {}).get("float_rel_tol")
    if tol != REQUIRED_FLOAT_REL_TOL:
        raise ConfigError(f"{path}: comparison.float_rel_tol is {tol!r}; CR-0013 requires "
                          f"exactly {REQUIRED_FLOAT_REL_TOL!r} (design rule 3: no config key "
                          f"may downgrade a GATE)")
    de = cfg.get("paths", {}).get("domain_edge")
    for k, want in REQUIRED_DOMAIN_EDGE.items():
        got = de.get(k) if isinstance(de, dict) else None
        if got != want:
            raise ConfigError(f"{path}: paths.domain_edge.{k} is {got!r}; CR-0017 requires exactly "
                              f"{want!r} (the domain-edge rule of E13/R3 cannot be removed, "
                              f"re-pointed or re-projected by config)")
    cfg["_path"] = path
    cfg["_sha256"] = hashlib.sha256(raw).hexdigest()
    return cfg


def rpath(cfg, kind, region=None):
    t = cfg["paths"][kind]
    if isinstance(t, dict):
        t = t["path"]
    return t.format(region=region) if "{region}" in t else t


def digested_paths(cfg):
    """The 20 digested artifacts: 18 region CSVs, B and C."""
    regions = cfg["constants"]["REGIONS"]
    out = [rpath(cfg, k, R) for R in regions for k in P_KINDS + N_KINDS]
    return out + [rpath(cfg, "block_assignments"), rpath(cfg, "candidate_pool")]


def standing_csv_paths(cfg):
    regions = cfg["constants"]["REGIONS"]
    return [rpath(cfg, k, R) for R in regions for k in P_KINDS + N_KINDS]


_SHA_CACHE = {}


def sha256_file(path):
    st = os.stat(path)
    key = (os.path.realpath(path), st.st_size, st.st_mtime_ns)
    if key in _SHA_CACHE:
        return _SHA_CACHE[key]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    _SHA_CACHE[key] = h.hexdigest()
    return _SHA_CACHE[key]


def _norm_json(v):
    """Tuples -> lists etc., for config/manifest/regions.py comparisons."""
    return json.loads(json.dumps(v))


def git_commit():
    try:
        c = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30)
        commit = c.stdout.strip() or None
        s = subprocess.run(["git", "-C", REPO_ROOT, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=60)
        dirty = any(line[:2].strip() and not line.startswith("??")
                    and line.rstrip().endswith(".py")
                    for line in s.stdout.splitlines())
        return commit, dirty
    except Exception:
        return None, None


def current_environment():
    """The environment measured at run time, in the config's shape."""
    from importlib.metadata import version   # shapely/pyogrio: versions only, never imported
    import geopandas
    import numpy
    import pandas
    import pyproj
    import rasterio
    import scipy
    from pyproj import Transformer
    return {
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "pyproj": pyproj.__version__,
        "PROJ": pyproj.proj_version_str,
        "rasterio": rasterio.__version__,
        "GDAL": rasterio.__gdal_version__,
        "geopandas": geopandas.__version__,
        "shapely": version("shapely"),
        "pyogrio": version("pyogrio"),
        "op_4326_5070": Transformer.from_crs(
            "EPSG:4326", "EPSG:5070", always_xy=True).definition,
    }


def read_csv(full):
    import pandas as pd
    return pd.read_csv(full, float_precision="round_trip")


def read_csv_rows(full):
    with open(full, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def read_header(full):
    with open(full, newline="", encoding="utf-8") as f:
        return next(csv.reader(f), [])


def write_csv_atomic(df, full):
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    tmp = f"{full}.tmp{os.getpid()}"
    df.to_csv(tmp, index=False)
    os.replace(tmp, full)


def write_json_atomic(obj, full):
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    tmp = f"{full}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, full)


# ==========================================================================
# Hash spec, keys, blocks, geometry (CR-0012 section 1-2)
# ==========================================================================
def order_key(text, seed):
    return int.from_bytes(
        hashlib.blake2b(f"{seed}:{text}".encode(), digest_size=8).digest(), "big")


def coord_text(lon, lat):
    return f"{float(lon):.6f},{float(lat):.6f}"


def draw_u(key):
    return (key + 0.5) / 2**64


def md5_is_val(block_id, seed, vf):
    """generate_negatives.split_for_unassigned at 05d788d:110-115."""
    h = int(hashlib.md5(f"{seed}:{block_id}".encode()).hexdigest(), 16)
    return (h % 10_000) < vf * 10_000


def py_round(x):
    """Python's built-in round() on the float64 product (half to even)."""
    return int(round(float(x)))


_T5070 = []


def to_5070(lon, lat):
    import numpy as np
    from pyproj import Transformer
    if not _T5070:
        _T5070.append(Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True))
    x, y = _T5070[0].transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def key_arrays(df, decimals):
    import numpy as np
    return (np.round(df["longitude"].to_numpy(dtype=float), decimals),
            np.round(df["latitude"].to_numpy(dtype=float), decimals))


def key_list(df, decimals):
    lo, la = key_arrays(df, decimals)
    return list(zip(lo.tolist(), la.tolist()))


def block_ids(x, y, cfg):
    import numpy as np
    C = cfg["constants"]
    bs = C["BLOCK_SIZE_M"]
    x0, y0 = C["BLOCK_ORIGIN_5070"]
    bx = np.floor((np.asarray(x, dtype=float) - x0) / bs).astype(np.int64)
    by = np.floor((np.asarray(y, dtype=float) - y0) / bs).astype(np.int64)
    return np.array([f"{a}_{b}" for a, b in zip(bx.tolist(), by.tolist())], dtype=object)


def thin_mask(lons, lats, xs, ys, seed, min_spacing):
    """CR-0012 positives step 4 / pool step 5: visit by ascending
    order_key(coord), ties by lon then lat; keep iff the squared distance
    to every kept row is >= MIN_SPACING_M**2."""
    import numpy as np
    n = len(lons)
    lons = [float(v) for v in lons]
    lats = [float(v) for v in lats]
    keys = [order_key(coord_text(lo, la), seed) for lo, la in zip(lons, lats)]
    order = sorted(range(n), key=lambda i: (keys[i], lons[i], lats[i]))
    ms = float(min_spacing)
    ms2 = ms * ms
    grid = {}
    keep = np.zeros(n, dtype=bool)
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    for i in order:
        x, y = xs[i], ys[i]
        cx, cy = math.floor(x / ms), math.floor(y / ms)
        ok = True
        for gx in range(cx - 2, cx + 3):
            for gy in range(cy - 2, cy + 3):
                for kx, ky in grid.get((gx, gy), ()):
                    dx = x - kx
                    dy = y - ky
                    if dx * dx + dy * dy < ms2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            keep[i] = True
            grid.setdefault((cx, cy), []).append((x, y))
    return keep


def min_d2_within(qx, qy, rx, ry, radius):
    """Exact squared float64 distance from each query to its nearest
    reference within `radius` (inf if none)."""
    import numpy as np
    from scipy.spatial import cKDTree
    qx = np.asarray(qx, dtype=float)
    qy = np.asarray(qy, dtype=float)
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)
    out = np.full(len(qx), np.inf)
    if len(qx) == 0 or len(rx) == 0:
        return out
    tree = cKDTree(np.column_stack([rx, ry]))
    lists = tree.query_ball_point(np.column_stack([qx, qy]),
                                  r=float(radius) * (1 + 1e-9) + 1e-6)
    for i, lst in enumerate(lists):
        if lst:
            dx = rx[lst] - qx[i]
            dy = ry[lst] - qy[i]
            out[i] = (dx * dx + dy * dy).min()
    return out


def close_pairs(x, y, dist):
    """Index pairs (i<j) with squared distance < dist**2."""
    import numpy as np
    from scipy.spatial import cKDTree
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2:
        return np.zeros((0, 2), dtype=int)
    tree = cKDTree(np.column_stack([x, y]))
    pairs = tree.query_pairs(r=float(dist) * (1 + 1e-9) + 1e-6, output_type="ndarray")
    if len(pairs) == 0:
        return pairs
    dx = x[pairs[:, 0]] - x[pairs[:, 1]]
    dy = y[pairs[:, 0]] - y[pairs[:, 1]]
    return pairs[dx * dx + dy * dy < float(dist) ** 2]


def nearest_dist(qx, qy, rx, ry):
    import numpy as np
    from scipy.spatial import cKDTree
    if len(rx) == 0 or len(qx) == 0:
        return np.full(len(qx), np.nan)
    d, _ = cKDTree(np.column_stack([rx, ry])).query(np.column_stack([qx, qy]), k=1)
    return np.asarray(d, dtype=float)


def bool_array(s):
    import pandas as pd
    if pd.api.types.is_bool_dtype(s):
        return s.to_numpy(dtype=bool)
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "1.0"]).to_numpy()


def sort_canonical(df, cols):
    return df.sort_values(list(cols), kind="mergesort").reset_index(drop=True)


# ==========================================================================
# Rasters: raster_path (grouse_data.RegionData at 05d788d), sample_raster
# (analyze_grouse at 05d788d), window predicate (CR-0012 section 1)
# ==========================================================================
_VALID_CACHE = {}
_HDR_CACHE = {}


def _file_key(full):
    st = os.stat(full)
    return (os.path.realpath(full), st.st_size, st.st_mtime_ns)


class Rasters:
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        rc = cfg["raster"]
        self.raster_dir = rc["raster_dir"]
        self.template = rc["template"]
        self.min_frac = float(rc["validity_min_frac"])
        self.sentinels = [float(s) for s in cfg["NODATA_SENTINELS"]]
        self.window_px = int(cfg["constants"]["WINDOW_PX"])
        self._years = {}
        self._tr = {}
        self.read = set()          # relpaths opened: part of input set I

    def rel(self, region, feature, year):
        return self.template.format(raster_dir=self.raster_dir, region=region,
                                    year=int(year), feature=feature)

    def full(self, rel):
        return os.path.join(self.root, rel)

    def raster_years(self, region, feature):
        k = (region, feature)
        if k not in self._years:
            pattern = re.compile(rf"^{region}_(\d{{4}})_{feature}\.tif$")
            found = []
            for p in glob.glob(os.path.join(self.root, self.raster_dir,
                                            f"{region}_*_{feature}.tif")):
                m = pattern.match(os.path.basename(p))
                if m:
                    found.append(int(m.group(1)))
            self._years[k] = sorted(set(found))
        return self._years[k]

    def is_valid(self, rel):
        """RegionData._is_valid_raster: nodata None -> valid; else the
        non-nodata fraction of band 1 >= min_valid_frac. Streamed in row
        windows (same count, early exit once the fraction is reached)."""
        import numpy as np
        full = self.full(rel)
        try:
            fk = _file_key(full)
        except OSError:
            return False
        self.read.add(rel)
        if fk in _VALID_CACHE:
            return _VALID_CACHE[fk]
        try:
            import rasterio
            from rasterio.windows import Window
            with rasterio.open(full) as src:
                nd = src.nodata
                if nd is None:
                    valid = True
                else:
                    total = src.width * src.height
                    valid = False
                    if total:
                        count = 0
                        step = 512
                        for r0 in range(0, src.height, step):
                            h = min(step, src.height - r0)
                            data = src.read(1, window=Window(0, r0, src.width, h))
                            count += int(np.count_nonzero(data != nd))
                            if count / total >= self.min_frac:
                                valid = True
                                break
        except Exception:
            valid = False
        _VALID_CACHE[fk] = valid
        return valid

    def raster_path(self, region, feature, year):
        years = self.raster_years(region, feature)
        if not years:
            raise ReplayError(f"[{region}] no rasters on disk for feature '{feature}' "
                              f"under {os.path.join(self.root, self.raster_dir)}")
        year = int(year)
        if year not in years:
            year = min(years, key=lambda y: (abs(y - year), y))
        rel = self.rel(region, feature, year)
        if self.is_valid(rel):
            return rel
        for cy in sorted(years, reverse=True):
            if cy == year:
                continue
            c = self.rel(region, feature, cy)
            if self.is_valid(c):
                return c
        raise ReplayError(f"[{region}] every {feature} raster on disk ({years}) "
                          f"failed content validation")

    def header(self, rel):
        full = self.full(rel)
        fk = _file_key(full)
        self.read.add(rel)
        if fk not in _HDR_CACHE:
            import rasterio
            with rasterio.open(full) as src:
                _HDR_CACHE[fk] = (src.transform, src.width, src.height,
                                  src.crs.to_wkt() if src.crs else None)
        return _HDR_CACHE[fk]

    def transformer(self, crs_wkt):
        from pyproj import Transformer
        if crs_wkt not in self._tr:
            self._tr[crs_wkt] = Transformer.from_crs("EPSG:4326", crs_wkt, always_xy=True)
        return self._tr[crs_wkt]

    def window_ok(self, rel, lons, lats):
        import numpy as np
        from rasterio.transform import rowcol
        lons = np.asarray(lons, dtype=float)
        lats = np.asarray(lats, dtype=float)
        out = np.zeros(len(lons), dtype=bool)
        if len(lons) == 0:
            return out
        transform, width, height, crs = self.header(rel)
        xs, ys = self.transformer(crs).transform(lons, lats)
        xs = np.asarray(xs, dtype=float)
        ys = np.asarray(ys, dtype=float)
        fin = np.isfinite(xs) & np.isfinite(ys)
        if fin.any():
            rows, cols = rowcol(transform, xs[fin], ys[fin])
            rows = np.asarray(rows, dtype=np.int64)
            cols = np.asarray(cols, dtype=np.int64)
            n = self.window_px
            h = n // 2
            r0 = rows - h
            c0 = cols - h
            out[fin] = (r0 >= 0) & (r0 + n <= height) & (c0 >= 0) & (c0 + n <= width)
        return out

    def sample(self, rel, lons, lats):
        """analyze_grouse.sample_raster at 05d788d."""
        import numpy as np
        import rasterio
        out = np.full(len(lons), np.nan)
        full = self.full(rel)
        if not os.path.exists(full):
            return out
        self.read.add(rel)
        with rasterio.open(full) as src:
            xs, ys = self.transformer(src.crs.to_wkt()).transform(
                np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
            xs, ys = np.asarray(xs), np.asarray(ys)
            b = src.bounds
            inside = (xs >= b.left) & (xs <= b.right) & (ys >= b.bottom) & (ys <= b.top)
            idx = np.where(inside)[0]
            if len(idx) == 0:
                return out
            vals = np.array([v[0] for v in src.sample(zip(xs[idx], ys[idx]))], dtype=float)
            if src.nodata is not None:
                vals[vals == src.nodata] = np.nan
            for s in self.sentinels:
                vals[vals == s] = np.nan
            out[idx] = vals
        return out


def fill_years(df, rasters, region, cfg):
    """dataset.py:98-102 at 05d788d (the max over the frame given)."""
    import numpy as np
    if "year" not in df.columns or df["year"].isna().all():
        return np.full(len(df), max(rasters.raster_years(region, cfg["year_fill_feature"])),
                       dtype=np.int64)
    y = df["year"]
    return y.fillna(y.max()).astype(int).to_numpy()


def window_mask(df, region, rasters, cfg):
    import numpy as np
    ok = np.ones(len(df), dtype=bool)
    if len(df) == 0:
        return ok
    years = fill_years(df, rasters, region, cfg)
    lons = df["longitude"].to_numpy(dtype=float)
    lats = df["latitude"].to_numpy(dtype=float)
    for yr in sorted(set(years.tolist())):
        m = years == yr
        for feat in cfg["feature_spec_keys"]:
            rel = rasters.raster_path(region, feat, yr)
            ok[m] &= rasters.window_ok(rel, lons[m], lats[m])
    return ok


def sample_features(df, region, rasters, cfg, feats):
    """Values at each row for `feats`, at raster_path(feat, filled year)."""
    import numpy as np
    out = {f: np.full(len(df), np.nan) for f in feats}
    if len(df) == 0:
        return out
    years = fill_years(df, rasters, region, cfg)
    lons = df["longitude"].to_numpy(dtype=float)
    lats = df["latitude"].to_numpy(dtype=float)
    for yr in sorted(set(years.tolist())):
        m = years == yr
        for f in feats:
            try:
                rel = rasters.raster_path(region, f, yr)
            except ReplayError:
                continue
            out[f][m] = rasters.sample(rel, lons[m], lats[m])
    return out


# ==========================================================================
# Envelope machinery (analyze_grouse / generate_negatives at 05d788d)
# ==========================================================================
def load_crosswalk(root, cfg):
    """load_evt_crosswalk at 05d788d (newest LF*_EVT.csv), plus the config
    pin: the newest file must be the pinned path with the pinned sha256."""
    cw = cfg["paths"]["crosswalk"]
    files = sorted(glob.glob(os.path.join(root, cw["glob"])))
    if not files:
        raise MissingInput(cw["path"])
    newest = os.path.relpath(files[-1], root)
    if newest != cw["path"]:
        raise ReplayError(f"newest EVT crosswalk is {newest}; the config pins {cw['path']}")
    got = sha256_file(files[-1])
    if got != cw["sha256"]:
        raise ReplayError(f"{newest} sha256 {got[:12]}... differs from the config pin "
                          f"{cw['sha256'][:12]}...")
    import pandas as pd
    tbl = pd.read_csv(files[-1], float_precision="round_trip")
    tbl.columns = [c.upper().strip() for c in tbl.columns]
    if "VALUE" not in tbl.columns or "EVT_PHYS" not in tbl.columns:
        raise ReplayError(f"{newest} lacks VALUE/EVT_PHYS columns")
    return dict(zip(tbl["VALUE"].astype(int), tbl["EVT_PHYS"].astype(str)))


def is_evt_phys_nonveg(series, prefixes):
    pattern = "|".join(prefixes)
    return series.astype(str).str.contains(pattern, case=False, na=False)


def coarse_quantile_bin(series, n_bins=4):
    import pandas as pd
    try:
        binned = pd.qcut(series, q=n_bins, labels=False, duplicates="drop")
        return binned.map(lambda v: f"Q{int(v) + 1}" if pd.notna(v) else "NA").astype(str)
    except ValueError:
        return series.astype(int).astype(str)


def fit_scheme_binners(df, scheme):
    import numpy as np
    binners = {}
    for col, variant in scheme:
        if variant.startswith("q"):
            n = int(variant[1:])
            edges = df[col].quantile(np.linspace(0, 1, n + 1)).values.astype(float)
            edges = np.unique(edges)
            edges[0], edges[-1] = -np.inf, np.inf
            binners[(col, variant)] = edges
    return binners


def _apply_binner(series, edges):
    import pandas as pd
    labels = [f"Q{i + 1}" for i in range(len(edges) - 1)]
    return pd.cut(series, bins=edges, labels=labels, include_lowest=True).astype(str)


def build_envelope_id(df, scheme, binners=None):
    import pandas as pd
    parts = []
    for col, variant in scheme:
        if variant == "raw":
            if pd.api.types.is_numeric_dtype(df[col]):
                lab = df[col].astype(int).astype(str)
            else:
                lab = df[col].astype(str)
        elif variant.startswith("q"):
            if binners and (col, variant) in binners:
                lab = _apply_binner(df[col], binners[(col, variant)])
            else:
                lab = coarse_quantile_bin(df[col], int(variant[1:]))
        else:
            raise ValueError(f"Unknown variant '{variant}' for {col}")
        parts.append(col.upper() + ":" + lab)
    out = parts[0]
    for p in parts[1:]:
        out = out + "|" + p
    return out


def build_weight(env_id, metrics_map, nonveg, C):
    """generate_negatives.build_weight at 05d788d (four basis strings)."""
    import numpy as np
    import pandas as pd
    if nonveg:
        return C["NONVEG_WEIGHT"], "NonVeg (hard negative)"
    row = metrics_map.get(env_id)
    if row is None:
        return C["NEUTRAL_WEIGHT"], "Unknown envelope (neutral)"
    if str(row["Classification"]).startswith("Landscape-Rare"):
        return C["NEUTRAL_WEIGHT"], "Landscape-Rare (neutral)"
    w = row["Selection_Ratio"]
    if pd.isna(w):
        return 1.0 / C["W_CAP"], "Selected (ratio undefined, min weight)"
    return 1.0 / float(np.clip(w, C["W_FLOOR"], C["W_CAP"])), row["Classification"]


def metrics_map_of(metrics):
    m = {}
    for env, cls, ratio in zip(metrics["Envelope"], metrics["Classification"],
                               metrics["Selection_Ratio"]):
        m[env] = {"Classification": cls, "Selection_Ratio": ratio}
    return m


def annotate(df, sightings, metrics, phys, cfg, C):
    """Pool step 9: evt_phys, envelope_id (binners fitted on the region's
    evaluated habitat rows), is_nonveg, weight, weight_basis."""
    import numpy as np
    import pandas as pd
    env = cfg["envelope"]
    scheme = [tuple(e) for e in env["ENVELOPE_SCHEME"]]
    out = df.copy()
    out["evt_phys"] = out["evt"].astype(int).map(phys).fillna("Unmapped")
    habitat = sightings[~sightings["nonveg_landcover"].astype(bool)]
    binners = fit_scheme_binners(habitat, scheme)
    out["envelope_id"] = build_envelope_id(out, scheme, binners=binners)
    out["is_nonveg"] = (out["sclass"].isin(env["NON_VEG_SCLASS_CODES"])
                        | is_evt_phys_nonveg(out["evt_phys"], env["EVT_PHYS_NONVEG_PREFIXES"]))
    mm = metrics_map_of(metrics)
    ws, bs = [], []
    for e, nv in zip(out["envelope_id"], out["is_nonveg"]):
        w, b = build_weight(e, mm, nv, C)
        ws.append(w)
        bs.append(b)
    out["weight"] = np.asarray(ws, dtype=float)
    out["weight_basis"] = pd.Series(bs, index=out.index, dtype=object)
    return out


# ==========================================================================
# verify_partition (CR-0007 v9 section 1, 6619bdd), re-implemented
# ==========================================================================
_POLY_CACHE = {}


def county_rel(cfg):
    """PATH_TEMPLATES["tiger_county"] at COUNTY_POLYGONS_YEAR (CR-0007 v9 section 1)."""
    cp = cfg["paths"]["county_polygons"]
    rel = cp["template"].format(year=cp["year"])
    if rel != cp["path"]:
        raise ReplayError(f"config: county template gives {rel}, path says {cp['path']}")
    where = "STATEFP IN (" + ",".join(f"'{v}'" for v in cp["STATE_FIPS"].values()) + ")"
    if where != cp["where"]:
        raise ReplayError(f"config: county filter {cp['where']!r} != {where!r} from STATE_FIPS")
    return rel


_DISSOLVED_CACHE = {}


def county_dissolved(root, cfg):
    """The pinned county file, filtered by `where` and dissolved by
    `dissolve_by`, in the file's own CRS (`source_crs`). The one read shared
    by verify_partition (projected to target_crs) and the acquisition domain
    (projected to domain_edge.edge_crs)."""
    cp = cfg["paths"]["county_polygons"]
    county_rel(cfg)
    full = os.path.join(root, cp["path"])
    if not os.path.exists(full):
        raise MissingInput(cp["path"])
    got = sha256_file(full)
    if got != cp["sha256"]:
        raise ReplayError(f"{cp['path']} sha256 {got[:12]}... differs from the config pin")
    fk = _file_key(full)
    if fk not in _DISSOLVED_CACHE:
        import geopandas as gpd
        g = gpd.read_file(full, where=cp["where"], engine="pyogrio")
        if g.crs is None or g.crs.to_string() != cp["source_crs"]:
            raise ReplayError(f"{cp['path']} CRS {g.crs} is not {cp['source_crs']}")
        _DISSOLVED_CACHE[fk] = g.dissolve(by=cp["dissolve_by"]).reset_index()
    return _DISSOLVED_CACHE[fk]


def county_states(root, cfg):
    cp = cfg["paths"]["county_polygons"]
    g = county_dissolved(root, cfg)
    fk = _file_key(os.path.join(root, cp["path"]))
    if fk not in _POLY_CACHE:
        g = g.to_crs(cp["target_crs"])
        _POLY_CACHE[fk] = g[[cp["dissolve_by"], "geometry"]]
    return _POLY_CACHE[fk]


def verify_partition(lons, lats, states, root, cfg):
    """Boolean mask of records whose county-polygon state differs from
    `state` or that fall inside no polygon."""
    import geopandas as gpd
    import numpy as np
    cp = cfg["paths"]["county_polygons"]
    polys = county_states(root, cfg)
    n = len(lons)
    if n == 0:
        return np.zeros(0, dtype=bool)
    fips_to_state = {v: k for k, v in cp["STATE_FIPS"].items()}
    pts = gpd.GeoDataFrame({"_i": np.arange(n)},
                           geometry=gpd.points_from_xy(np.asarray(lons, dtype=float),
                                                       np.asarray(lats, dtype=float)),
                           crs=cp["target_crs"])
    j = gpd.sjoin(pts, polys, predicate=cp["predicate"], how="left")
    fcol = cp["dissolve_by"]
    matched = {}
    for i, fp in zip(j["_i"].to_numpy(), j[fcol].tolist()):
        s = matched.setdefault(int(i), set())
        if isinstance(fp, str):
            s.add(fips_to_state.get(fp, f"FIPS{fp}"))
    states = [str(s) for s in states]
    return np.array([matched.get(i, set()) != {states[i]} for i in range(n)], dtype=bool)


# ==========================================================================
# Acquisition-domain edge (CR-0017 section 3), re-implemented from the CR
# text; no regions/generate_negatives helper is used (design rule 1).
# ==========================================================================
_DOMAIN_CACHE = {}


def acquisition_domain(root, cfg):
    """D: the union of the dissolved county polygons (paths.domain_edge.source
    = paths.county_polygons), projected from the file CRS straight to
    edge_crs. A one-row GeoSeries."""
    import geopandas as gpd
    de = cfg["paths"]["domain_edge"]
    cp = cfg["paths"]["county_polygons"]
    g = county_dissolved(root, cfg)
    fk = (_file_key(os.path.join(root, cp["path"])), de["edge_crs"])
    if fk not in _DOMAIN_CACHE:
        proj = g.to_crs(de["edge_crs"])
        _DOMAIN_CACHE[fk] = gpd.GeoSeries([proj.geometry.union_all()], crs=de["edge_crs"])
    return _DOMAIN_CACHE[fk]


def _boundary_segments(domain, max_len):
    """Every boundary segment of every polygon in `domain` (exterior and
    interior rings), as arrays (ax, ay, bx, by). Segments longer than
    `max_len` are cut into collinear pieces (the union of the pieces is the
    segment, so point distances are unchanged)."""
    import numpy as np
    b = domain.boundary.explode(index_parts=False).reset_index(drop=True)
    xy = b.get_coordinates(index_parts=False)
    part = xy.index.to_numpy()
    cx = xy["x"].to_numpy(dtype=float)
    cy = xy["y"].to_numpy(dtype=float)
    same = part[1:] == part[:-1]
    ax, ay = cx[:-1][same], cy[:-1][same]
    bx, by = cx[1:][same], cy[1:][same]
    k = np.maximum(1, np.ceil(np.hypot(bx - ax, by - ay) / float(max_len))).astype(np.int64)
    idx = np.repeat(np.arange(len(ax)), k)
    start = np.repeat(np.cumsum(k) - k, k)
    i = np.arange(len(idx)) - start
    kk = k[idx].astype(float)
    t0, t1 = i / kk, (i + 1) / kk
    dx, dy = bx[idx] - ax[idx], by[idx] - ay[idx]
    last = i + 1 == k[idx]
    return (ax[idx] + t0 * dx, ay[idx] + t0 * dy,
            np.where(last, bx[idx], ax[idx] + t1 * dx),
            np.where(last, by[idx], ay[idx] + t1 * dy))


def domain_edge_within(x, y, domain, radius):
    """edge_m (CR-0017 sections 2-3) for points x, y in the domain's CRS,
    exact wherever edge_m <= radius and +inf wherever edge_m > radius:
    0.0 for a point inside no polygon of `domain` (or on its boundary),
    else the float64 Euclidean distance to the nearest boundary segment of
    any polygon of `domain`. With the unioned domain (one polygon row) the
    lines between states are not boundaries."""
    import geopandas as gpd
    import numpy as np
    from scipy.spatial import cKDTree
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    out = np.full(n, np.inf)
    if n == 0:
        return out
    radius = float(radius)
    pts = gpd.GeoDataFrame({"_i": np.arange(n)}, geometry=gpd.points_from_xy(x, y),
                           crs=domain.crs)
    polys = gpd.GeoDataFrame(geometry=gpd.GeoSeries(list(domain), crs=domain.crs))
    j = gpd.sjoin(pts, polys, predicate="within", how="inner")
    inside = np.zeros(n, dtype=bool)
    inside[j["_i"].to_numpy()] = True
    seg_len = max(radius, 1.0)
    ax, ay, bx, by = _boundary_segments(domain, seg_len)
    if len(ax):
        tree = cKDTree(np.column_stack([(ax + bx) / 2, (ay + by) / 2]))
        reach = radius + seg_len / 2 + radius * 1e-9 + 1e-6
        q = np.nonzero(inside)[0]
        lists = tree.query_ball_point(np.column_stack([x[q], y[q]]), r=reach)
        for qi, lst in zip(q, lists):
            if not lst:
                continue
            s = np.asarray(lst)
            sx, sy = bx[s] - ax[s], by[s] - ay[s]
            l2 = sx * sx + sy * sy
            with np.errstate(invalid="ignore", divide="ignore"):
                t = np.where(l2 > 0, ((x[qi] - ax[s]) * sx + (y[qi] - ay[s]) * sy) / l2, 0.0)
            t = np.clip(t, 0.0, 1.0)
            ex = x[qi] - (ax[s] + t * sx)
            ey = y[qi] - (ay[s] + t * sy)
            d = float(np.sqrt((ex * ex + ey * ey).min()))
            if d <= radius:
                out[qi] = d
    out[~inside] = 0.0
    return out


# ==========================================================================
# The replay (CR-0012 section 2)
# ==========================================================================
class Replay:
    """CR-0012 section 2, re-implemented from its text (29f388b) and the
    normative functions at 05d788d. Attack tests subclass it to build
    wrong pipelines; the gates always use this class unmodified."""

    def __init__(self, root, cfg, regions=None, constants=None):
        self.root = root
        self.cfg = cfg
        self.C = dict(cfg["constants"])
        if constants:
            self.C.update(constants)
        self.regions = list(regions if regions is not None else self.C["REGIONS"])
        self.rasters = Rasters(root, cfg)
        self.counts = {"positives": {}, "negatives": {}}
        self.inputs = {"positives": set(), "negatives": set()}
        self.draw_counts = {}
        self.dropped = []
        self.errors = {}
        self._S = {}
        self._metrics = {}
        self.pos = None
        self.B = None
        self.pool_full = None
        self.neg = None

    # ---- inputs ----------------------------------------------------------
    def read_input(self, section, kind, region=None):
        rel = rpath(self.cfg, kind, region)
        full = os.path.join(self.root, rel)
        if not os.path.exists(full):
            raise MissingInput(rel)
        self.inputs[section].add(rel)
        return read_csv(full)

    def sightings(self, R, section):
        self.inputs[section].add(rpath(self.cfg, "sightings", R))
        if R not in self._S:
            self._S[R] = self.read_input(section, "sightings", R)
        return self._S[R]

    def metrics(self, R):
        if R not in self._metrics:
            self._metrics[R] = self.read_input("negatives", "envelope_metrics", R)
        return self._metrics[R]

    def seed(self):
        return self.C["SPLIT_SEED"]

    def _count(self, section, df, step):
        for R in self.regions:
            self.counts[section].setdefault(R, {})[str(step)] = int((df["region"] == R).sum())

    # ---- orchestration -----------------------------------------------------
    def run(self, stop_on_error=False):
        for stage in ("positives", "pool", "draw"):
            if any(self.errors.get(s) for s in ("positives", "pool", "draw")):
                self.errors[stage] = ReplayError(f"not run: an earlier replay stage failed")
                continue
            try:
                getattr(self, f"run_{stage}")()
            except Exception as e:     # recorded, reported as the R gates' FAIL
                if stop_on_error:
                    raise
                self.errors[stage] = e
        return self

    # ---- positives ---------------------------------------------------------
    def check_sightings(self, R, df):
        if "region" not in df.columns:
            raise ReplayError(f"{rpath(self.cfg, 'sightings', R)} has no 'region' column "
                              f"(CR-0012 positives step 1 requires state == region == {R})")
        bad = (df["state"].astype(str) != R) | (df["region"].astype(str) != R)
        if bad.any():
            raise ReplayError(f"{rpath(self.cfg, 'sightings', R)}: {int(bad.sum())} rows "
                              f"violate state == region == {R}")

    def habitat_rows(self, df):
        return df[~df["nonveg_landcover"].astype(bool)].copy()

    def check_years(self, R, df):
        """CR-0019 positives step 2: every evaluated sighting of the region
        (habitat or not) has a non-null year, else the pipeline raises."""
        if "year" not in df.columns:
            raise ReplayError(f"{rpath(self.cfg, 'sightings', R)} has no 'year' column")
        n = int(df["year"].isna().sum())
        if n:
            raise ReplayError(f"{rpath(self.cfg, 'sightings', R)}: {n} rows with a null year "
                              f"(CR-0019 positives step 2)")

    def year_floor(self, df):
        """CR-0019 positives step 2: True where year >= YEAR_MIN."""
        return (df["year"] >= self.C["YEAR_MIN"]).to_numpy()

    def pool_year_floor(self, cand):
        """CR-0019 pool step 1: drop every row with a non-null year < YEAR_MIN;
        a null-year row is kept here (dropped at step 7, as in CR-0012)."""
        y = cand["year"]
        drop = (y.notna() & (y < self.C["YEAR_MIN"])).to_numpy()
        return cand[~drop].copy()

    def window_filter(self, R, df):
        return df[window_mask(df, R, self.rasters, self.cfg)].copy()

    def thin(self, lons, lats, xs, ys, frame=None):
        return thin_mask(lons, lats, xs, ys, self.seed(), self.C["MIN_SPACING_M"])

    def select_val_blocks(self, bids, seed=None, frame=None):
        from collections import Counter
        seed = self.seed() if seed is None else seed
        counts = Counter(list(bids))
        order = sorted(counts, key=lambda b: (order_key(b, seed), b))
        target = py_round(self.C["VAL_FRACTION"] * len(bids))
        val, running = set(), 0
        for b in order:
            if running >= target:
                break
            val.add(b)
            running += counts[b]
        return val

    def block_ids_for(self, x, y, frame=None):
        return block_ids(x, y, self.cfg)

    def run_positives(self):
        import numpy as np
        import pandas as pd
        frames = []
        for R in self.regions:
            df = self.sightings(R, "positives")
            self.check_sightings(R, df)
            self.check_years(R, df)
            cnt = self.counts["positives"].setdefault(R, {})
            cnt["1"] = len(df)
            hab = self.habitat_rows(df)
            hab = hab[self.year_floor(hab)].copy()      # CR-0019: before thinning (step 4)
            cnt["2"] = len(hab)
            hab = self.window_filter(R, hab)
            for rel in self.rasters.read:
                self.inputs["positives"].add(rel)
            cnt["3"] = len(hab)
            frames.append(hab)
        pooled = pd.concat(frames, ignore_index=True)
        lon = pooled["longitude"].to_numpy(dtype=float)
        lat = pooled["latitude"].to_numpy(dtype=float)
        x, y = to_5070(lon, lat)
        keep = self.thin(lon, lat, x, y, frame=pooled)
        th = pooled[keep].reset_index(drop=True)
        x, y = x[keep], y[keep]
        self._count("positives", th, 4)
        bids = self.block_ids_for(x, y, th)
        val_blocks = self.select_val_blocks(bids, frame=th)
        split = np.array(["val" if b in val_blocks else "train" for b in bids], dtype=object)
        th["block_id"] = bids
        th["split"] = split
        self._count("positives", th, 5)
        self.thinned_xy = (x, y)
        self.thinned_all = th
        cols = self.cfg["columns"]["positives"]
        missing = [c for c in cols if c not in th.columns]
        if missing:
            raise ReplayError(f"evaluated_sightings lacks columns {missing}")
        self.pos = {}
        for R in self.regions:
            sub = th.loc[th["region"] == R, cols]
            self.pos[R] = sort_canonical(sub, self.cfg["row_order"]["positives"])
        self._count("positives", th, 6)
        u, n = np.unique(bids.astype(str), return_counts=True)
        bsplit = dict(zip(bids.tolist(), split.tolist()))
        B = pd.DataFrame({"block_id": u, "split": [bsplit[b] for b in u], "n": n.astype(np.int64)})
        self.B = sort_canonical(B, self.cfg["row_order"]["block_assignments"])

    # ---- candidate pool ------------------------------------------------------
    def load_candidates(self):
        import pandas as pd
        frames = []
        for R in self.regions:
            g = self.read_input("negatives", "gbif_candidates", R)
            bad = g["state"].astype(str) != R
            if bad.any():
                raise ReplayError(f"{rpath(self.cfg, 'gbif_candidates', R)}: {int(bad.sum())} "
                                  f"rows have state != {R}")
            g = g.copy()
            g["region"] = R
            frames.append(g)
        cand = pd.concat(frames, ignore_index=True)
        cand = self.pool_year_floor(cand)                # CR-0019 pool step 1
        self._count("negatives", cand, 1)
        return cand

    def uncertainty_filter(self, cand):
        too_vague = cand["coord_uncertainty_m"] > self.C["MAX_COORD_UNCERTAINTY_M"]
        return cand[~too_vague.fillna(False).astype(bool)].copy()

    def dedup(self, cand):
        d = self.C["KEY_DECIMALS"]
        klo, kla = key_arrays(cand, d)
        tmp = cand.assign(_klon=klo, _klat=kla)
        if tmp["gbif_id"].isna().any() or tmp["gbif_id"].duplicated().any():
            raise ReplayError("gbif_id is null or not unique: the order-free dedup rule "
                              "(smallest gbif_id per key) is undefined")
        ns = tmp.groupby(["_klon", "_klat"])["state"].nunique()
        if (ns > 1).any():
            raise ReplayError(f"{int((ns > 1).sum())} keys are filed under two states")
        tmp = tmp.sort_values("gbif_id", kind="mergesort")
        tmp = tmp.drop_duplicates(["_klon", "_klat"], keep="first")
        return tmp.drop(columns=["_klon", "_klat"])

    def partition_drop(self, cand):
        self.inputs["negatives"].add(county_rel(self.cfg))
        bad = verify_partition(cand["longitude"].to_numpy(), cand["latitude"].to_numpy(),
                               cand["state"].astype(str).tolist(), self.root, self.cfg)
        self.dropped = sorted([float(a), float(b)] for a, b in
                              zip(cand["longitude"].to_numpy()[bad], cand["latitude"].to_numpy()[bad]))
        return cand[~bad].copy()

    def pool_until_partition(self):
        cand = self.load_candidates()
        cand = self.uncertainty_filter(cand)
        self._count("negatives", cand, 2)
        cand = self.dedup(cand)
        self._count("negatives", cand, 3)
        cand = self.partition_drop(cand)
        self._count("negatives", cand, 4)
        return cand

    def all_sightings_xy(self):
        import numpy as np
        xs, ys = [], []
        for R in self.regions:
            S = self.sightings(R, "negatives")
            x, y = to_5070(S["longitude"].to_numpy(dtype=float), S["latitude"].to_numpy(dtype=float))
            xs.append(x)
            ys.append(y)
        return np.concatenate(xs), np.concatenate(ys)

    def sighting_buffer_mask(self, cand):
        """Pool step 6 rule (a): squared distance to any sightings row <= BUFFER_M**2."""
        sx, sy = self.all_sightings_xy()
        b = float(self.C["BUFFER_M"])
        d2 = min_d2_within(cand["x_5070"].to_numpy(), cand["y_5070"].to_numpy(), sx, sy, b)
        return d2 <= b * b

    def domain(self):
        return acquisition_domain(self.root, self.cfg)

    def domain_edge_mask(self, cand):
        """Pool step 6 rule (b) (CR-0017): edge_m <= BUFFER_M. x_5070/y_5070
        here are the replay's own transform of lon/lat (step 5)."""
        b = float(self.C["BUFFER_M"])
        e = domain_edge_within(cand["x_5070"].to_numpy(), cand["y_5070"].to_numpy(),
                               self.domain(), b)
        return e <= b

    def buffer_drop(self, cand):
        """Pool step 6 (CR-0012, amended by CR-0017): drop (a) | (b), both
        row filters on the same step-5 pool."""
        drop = self.sighting_buffer_mask(cand) | self.domain_edge_mask(cand)
        return cand[~drop].copy()

    def extract(self, R, sub):
        import numpy as np
        feats = self.cfg["envelope"]["envelope_features"]
        vals = {f: np.full(len(sub), np.nan) for f in feats}
        lon = sub["longitude"].to_numpy(dtype=float)
        lat = sub["latitude"].to_numpy(dtype=float)
        for f in feats:
            for yr in sorted(sub["year"].dropna().unique()):
                m = (sub["year"] == yr).to_numpy()
                rel = self.rasters.raster_path(R, f, int(yr))
                vals[f][m] = self.rasters.sample(rel, lon[m], lat[m])
        sub = sub.copy()
        for f in feats:
            sub[f] = vals[f]
        return sub.dropna(subset=feats).copy()

    def assign_split(self, bids, sub=None):
        import numpy as np
        bsplit = dict(zip(self.B["block_id"].astype(str), self.B["split"].astype(str)))
        vf = float((self.B["split"] == "val").mean())
        seed = self.seed()
        return np.array([bsplit.get(b) or ("val" if md5_is_val(b, seed, vf) else "train")
                         for b in bids], dtype=object)

    def run_pool(self):
        import pandas as pd
        phys = load_crosswalk(self.root, self.cfg)
        self.inputs["negatives"].add(self.cfg["paths"]["crosswalk"]["path"])
        cand = self.pool_until_partition()
        lon = cand["longitude"].to_numpy(dtype=float)
        lat = cand["latitude"].to_numpy(dtype=float)
        x, y = to_5070(lon, lat)
        keep = self.thin(lon, lat, x, y, frame=cand)
        cand = cand[keep].copy()
        cand["x_5070"], cand["y_5070"] = x[keep], y[keep]
        self._count("negatives", cand, 5)
        cand = self.buffer_drop(cand)
        self._count("negatives", cand, 6)
        parts = {7: [], 8: [], 9: []}
        for R in self.regions:
            sub = cand[cand["region"] == R]
            sub = self.extract(R, sub)
            parts[7].append(sub)
            sub = self.window_filter(R, sub)
            parts[8].append(sub)
            sub = annotate(sub, self.sightings(R, "negatives"), self.metrics(R), phys,
                           self.cfg, self.C)
            parts[9].append(sub)
        for step in (7, 8, 9):
            self._count("negatives", pd.concat(parts[step], ignore_index=True), step)
        for rel in self.rasters.read:
            self.inputs["negatives"].add(rel)
        cand = pd.concat(parts[9], ignore_index=True)
        cand = self.post_annotate(cand)
        cand["block_id"] = self.block_ids_for(cand["x_5070"].to_numpy(), cand["y_5070"].to_numpy(), cand)
        cand["split"] = self.assign_split(cand["block_id"].tolist(), cand)
        cand = self.post_split(cand)
        self._count("negatives", cand, 10)
        cand = sort_canonical(cand, self.cfg["row_order"]["pool"])
        self.pool_full = cand
        self._count("negatives", cand, 11)

    def post_annotate(self, cand):
        """Hook for attack pipelines (identity here)."""
        return cand

    def post_split(self, cand):
        """Hook for attack pipelines (identity here)."""
        return cand

    @property
    def pool(self):
        return self.pool_full[self.cfg["columns"]["pool"]]

    # ---- draw ----------------------------------------------------------------
    def draw_scores(self, sub, seed):
        keys = [order_key("neg:" + coord_text(lo, la), seed)
                for lo, la in zip(sub["longitude"].to_numpy(), sub["latitude"].to_numpy())]
        w = sub["weight"].to_numpy(dtype=float)
        scores = [math.log(draw_u(k)) / float(wi) for k, wi in zip(keys, w)]
        return keys, scores

    def es_take(self, sub, k, seed):
        """Efraimidis-Spirakis: the k rows with the largest log(u)/weight,
        ties by ascending key."""
        if k <= 0 or len(sub) == 0:
            return sub.iloc[0:0]
        keys, scores = self.draw_scores(sub, seed)
        order = sorted(range(len(sub)), key=lambda i: (-scores[i], keys[i]))
        return sub.iloc[sorted(order[:k])]

    def draw_targets(self, R, s):
        n_pos = int((self.pos[R]["split"] == s).sum())
        return py_round(n_pos * self.C["NEG_RATIO"])

    def draw_select(self, seed=None, record=True):
        import pandas as pd
        seed = self.seed() if seed is None else seed
        pool = self.pool_full
        nv_all = bool_array(pool["is_nonveg"])
        picked = []
        for R in self.regions:
            for s in SPLITS:
                n = self.draw_targets(R, s)
                m = ((pool["region"] == R) & (pool["split"] == s)).to_numpy()
                nv = pool[m & nv_all]
                hab = pool[m & ~nv_all]
                n_nv = min(py_round(n * self.C["NONVEG_MAX_FRAC"]), len(nv))
                n_hab = n - n_nv
                if len(hab) < n_hab:
                    raise ReplayError(f"[{R}/{s}] habitat pool {len(hab)} < habitat target {n_hab}")
                take_h = self.es_take(hab, n_hab, seed)
                take_n = self.es_take(nv, n_nv, seed)
                if record:
                    self.draw_counts.setdefault(R, {})[s] = {"n": int(n), "n_nv": int(n_nv),
                                                            "n_hab": int(n_hab)}
                picked.extend([take_h, take_n])
        return pd.concat(picked, ignore_index=True)

    def run_draw(self):
        sel = self.draw_select()
        sel = sel.copy()
        sel["label"] = 0
        cols = self.cfg["columns"]["negatives"]
        missing = [c for c in cols if c not in sel.columns]
        if missing:
            raise ReplayError(f"negatives lack columns {missing}")
        self.neg = {}
        for R in self.regions:
            sub = sel.loc[sel["region"] == R, cols]
            self.neg[R] = sort_canonical(sub, self.cfg["row_order"]["negatives"])

    # ---- outputs ---------------------------------------------------------------
    def output_frames(self):
        """{relpath: DataFrame} for P, B, C, N (as CR-0012 writes them)."""
        out = {}
        for R in self.regions:
            p = self.pos[R]
            out[rpath(self.cfg, "thinned_positives", R)] = p
            out[rpath(self.cfg, "train_positives", R)] = p[p["split"] == "train"]
            out[rpath(self.cfg, "val_positives", R)] = p[p["split"] == "val"]
            n = self.neg[R]
            out[rpath(self.cfg, "negatives", R)] = n
            out[rpath(self.cfg, "train_negatives", R)] = n[n["split"] == "train"]
            out[rpath(self.cfg, "val_negatives", R)] = n[n["split"] == "val"]
        out[rpath(self.cfg, "block_assignments")] = self.B
        out[rpath(self.cfg, "candidate_pool")] = self.pool
        return out

    def manifest_constants(self):
        c = dict(self.C)
        c["REGIONS"] = list(self.regions)
        return c

    def build_manifest(self, out_root, outputs):
        env = current_environment()
        commit, dirty = git_commit()
        pos_out = [p for p in outputs if "positives" in p or p.endswith("block_assignments.csv")]
        neg_out = [p for p in outputs if p not in pos_out]

        def digests(root, rels):
            res = {}
            for rel in sorted(rels):
                full = os.path.join(root, rel)
                if os.path.exists(full):
                    res[rel] = sha256_file(full)
            return res

        def section(name, outs, extra=None):
            d = {"constants": self.manifest_constants(),
                 "hash_spec": self.cfg["hash_spec"],
                 "environment": env,
                 "inputs": digests(self.root, self.inputs[name]),
                 "outputs": digests(out_root, outs),
                 "counts": self.counts[name],
                 "commit": commit,
                 "dirty": bool(dirty)}
            d.update(extra or {})
            return d

        return {"positives": section("positives", pos_out),
                "negatives": section("negatives", neg_out,
                                     {"draw": self.draw_counts, "dropped": self.dropped})}

    def emit(self, out_root):
        frames = self.output_frames()
        for rel, df in frames.items():
            write_csv_atomic(df, os.path.join(out_root, rel))
        m = self.build_manifest(out_root, list(frames))
        write_json_atomic(m, os.path.join(out_root, rpath(self.cfg, "split_manifest")))
        return sorted(frames)


def csv_roundtrip(df):
    """Parse a frame exactly as a file written by to_csv would be read."""
    import io
    import pandas as pd
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return pd.read_csv(buf, float_precision="round_trip")


# ==========================================================================
# Full-row comparison
# ==========================================================================
def _is_num(s):
    import pandas as pd
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def mismatch_mask(a, b, tol):
    import numpy as np
    import pandas as pd
    if _is_num(a) and _is_num(b):
        x = a.to_numpy(dtype=float)
        y = b.to_numpy(dtype=float)
        both_nan = np.isnan(x) & np.isnan(y)
        with np.errstate(invalid="ignore"):
            close = (x == y) | (np.abs(x - y) <= tol * np.maximum(np.abs(x), np.abs(y)))
        return ~(both_nan | close)
    if pd.api.types.is_bool_dtype(a) and pd.api.types.is_bool_dtype(b):
        return a.to_numpy() != b.to_numpy()
    an = a.isna().to_numpy()
    bn = b.isna().to_numpy()
    sa = a.astype(object).map(str).to_numpy()
    sb = b.astype(object).map(str).to_numpy()
    return ~((an & bn) | (~an & ~bn & (sa == sb)))


def compare_frames(actual, expected, key, tol, label, decimals=5, limit=3, order_cols=None):
    """Full-row equality with rows matched on `key` ('coord' or a column)."""
    import numpy as np
    problems = []
    ac, ec = list(actual.columns), list(expected.columns)
    if ac != ec:
        problems.append(f"{label}: columns {ac} != replay {ec}")
    if key == "coord":
        ka = key_list(actual, decimals) if {"longitude", "latitude"} <= set(ac) else None
        ke = key_list(expected, decimals)
    else:
        ka = actual[key].astype(str).tolist() if key in ac else None
        ke = expected[key].astype(str).tolist()
    if ka is None:
        problems.append(f"{label}: key columns absent; rows cannot be matched")
        return problems
    if len(set(ka)) != len(ka):
        problems.append(f"{label}: {len(ka) - len(set(ka))} duplicate keys")
    ia = {k: i for i, k in enumerate(ka)}
    ie = {k: i for i, k in enumerate(ke)}
    extra = [k for k in ia if k not in ie]
    lack = [k for k in ie if k not in ia]
    if extra:
        problems.append(f"{label}: {len(extra)} rows not in the replay, e.g. {extra[:limit]}")
    if lack:
        problems.append(f"{label}: {len(lack)} replay rows absent, e.g. {lack[:limit]}")
    common = [k for k in ie if k in ia]
    if common:
        ra = np.array([ia[k] for k in common])
        re_ = np.array([ie[k] for k in common])
        for c in ec:
            if c not in ac:
                continue
            a = actual[c].iloc[ra].reset_index(drop=True)
            b = expected[c].iloc[re_].reset_index(drop=True)
            mm = mismatch_mask(a, b, tol)
            if mm.any():
                i = int(np.argmax(mm))
                problems.append(f"{label}: column '{c}' differs on {int(mm.sum())} rows, e.g. "
                                f"key {common[i]}: {a.iloc[i]!r} vs replay {b.iloc[i]!r}")
    if order_cols is not None:
        problems.extend(canonical_order_problems(actual, order_cols, label))
    return problems


def canonical_order_problems(df, cols, label):
    """GATE (CR-0013 v2.3, R1-R4): the shipped rows are in CR-0012's
    canonical order, i.e. a stable sort by `cols` leaves them in place."""
    import numpy as np
    lack = [c for c in cols if c not in df.columns]
    if lack:
        return [f"{label}: canonical order not checkable (columns {lack} absent)"]
    order = df.sort_values(list(cols), kind="mergesort").index.to_numpy()
    if (order != df.index.to_numpy()).any():
        first = int(np.argmax(order != df.index.to_numpy()))
        return [f"{label}: rows are not in canonical order (stable sort by {list(cols)}); "
                f"first out-of-place data row {first}"]
    return []


# ==========================================================================
# Gate context
# ==========================================================================
class Context:
    def __init__(self, root, cfg, coords="recompute"):
        self.root = os.path.abspath(root)
        self.cfg = cfg
        self.C = cfg["constants"]
        self.regions = list(self.C["REGIONS"])
        self.coords = coords
        self._csv = {}
        self._rep = None
        self.rasters = Rasters(self.root, cfg) if coords == "recompute" else None
        self.input_digests = None
        self.tol = float(cfg["comparison"]["float_rel_tol"])

    def full(self, rel):
        return os.path.join(self.root, rel)

    def exists(self, rel):
        return os.path.exists(self.full(rel))

    def csv(self, rel):
        if rel not in self._csv:
            if not self.exists(rel):
                raise MissingInput(rel)
            self._csv[rel] = read_csv(self.full(rel))
        return self._csv[rel]

    def try_csv(self, rel, missing):
        try:
            return self.csv(rel)
        except MissingInput:
            if rel not in missing:
                missing.append(rel)
            return None

    def xy(self, df):
        if self.coords == "recompute":
            return to_5070(df["longitude"].to_numpy(dtype=float),
                           df["latitude"].to_numpy(dtype=float))
        return df["x_5070"].to_numpy(dtype=float), df["y_5070"].to_numpy(dtype=float)

    def pooled(self, kind, missing):
        import pandas as pd
        frames = []
        for R in self.regions:
            df = self.try_csv(rpath(self.cfg, kind, R), missing)
            if df is not None:
                frames.append(df.assign(_R=R))
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True)

    def manifest(self, missing):
        rel = rpath(self.cfg, "split_manifest")
        if not self.exists(rel):
            missing.append(rel)
            return None
        with open(self.full(rel), encoding="utf-8") as f:
            return json.load(f)

    def replay(self):
        if self._rep is None:
            self._rep = Replay(self.root, self.cfg).run()
        return self._rep


def _fail_unless(problems, missing):
    return not problems and not missing


# ==========================================================================
# GATES
# ==========================================================================
def gate_E0(ctx, sets=("P", "N", "B", "C", "M")):
    problems, missing = [], []
    cols = ctx.cfg["columns"]

    def check(rel, expect):
        if not ctx.exists(rel):
            missing.append(rel)
            return
        header = read_header(ctx.full(rel))
        if header != expect:
            lack = [c for c in expect if c not in header]
            extra = [c for c in header if c not in expect]
            what = []
            if lack:
                what.append(f"missing {lack}")
            if extra:
                what.append(f"unexpected {extra}")
            if not what:
                what.append("column order differs")
            problems.append(f"{rel}: {'; '.join(what)}")

    for R in ctx.regions:
        if "P" in sets:
            for k in P_KINDS:
                check(rpath(ctx.cfg, k, R), cols["positives"])
        if "N" in sets:
            for k in N_KINDS:
                check(rpath(ctx.cfg, k, R), cols["negatives"])
    if "B" in sets:
        check(rpath(ctx.cfg, "block_assignments"), cols["block_assignments"])
    if "C" in sets:
        check(rpath(ctx.cfg, "candidate_pool"), cols["pool"])
    if "M" in sets:
        rel = rpath(ctx.cfg, "split_manifest")
        if not ctx.exists(rel):
            missing.append(rel)
        else:
            try:
                with open(ctx.full(rel), encoding="utf-8") as f:
                    m = json.load(f)
                lack = [s for s in cols["split_manifest_sections"] if s not in m]
                if lack:
                    problems.append(f"{rel}: sections {lack} absent")
            except Exception as e:
                problems.append(f"{rel}: not readable JSON ({e})")
    return problems, missing


def gate_E1(ctx, include_C=True):
    problems, missing = [], []
    present = {"P": set(), "N": set()}
    for R in ctx.regions:
        for cls, kinds in (("P", P_KINDS), ("N", N_KINDS)):
            for k in kinds:
                rel = rpath(ctx.cfg, k, R)
                df = ctx.try_csv(rel, missing)
                if df is None:
                    continue
                bad_s = int((df["state"].astype(str) != R).sum()) if "state" in df else len(df)
                if "state" not in df:
                    problems.append(f"{rel}: no 'state' column")
                elif bad_s:
                    problems.append(f"{rel}: {bad_s} rows with state != {R}")
                if "region" not in df:
                    problems.append(f"{rel}: no 'region' column")
                else:
                    bad_r = int((df["region"].astype(str) != R).sum())
                    if bad_r:
                        problems.append(f"{rel}: {bad_r} rows with region != {R}")
                    if k in (P_KINDS[0], N_KINDS[0]):
                        present[cls] |= set(df["region"].astype(str).unique())
    for cls in ("P", "N"):
        if not missing and present[cls] != set(ctx.regions):
            problems.append(f"{cls}: regions present {sorted(present[cls])} != REGIONS "
                            f"{sorted(ctx.regions)}")
    if include_C:
        rel = rpath(ctx.cfg, "candidate_pool")
        c = ctx.try_csv(rel, missing)
        if c is not None:
            if "region" not in c or "state" not in c:
                problems.append(f"{rel}: region/state columns absent")
            else:
                reg = c["region"].astype(str)
                bad = int((~reg.isin(ctx.regions)).sum())
                if bad:
                    problems.append(f"{rel}: {bad} rows with region not in REGIONS")
                bad = int((c["state"].astype(str) != reg).sum())
                if bad:
                    problems.append(f"{rel}: {bad} rows with state != region")
                if set(reg.unique()) != set(ctx.regions):
                    problems.append(f"{rel}: regions present {sorted(set(reg.unique()))} != "
                                    f"REGIONS {sorted(ctx.regions)}")
    return problems, missing


def gate_E1p(ctx):
    problems, missing = [], []
    for R in ctx.regions:
        for kinds in (P_KINDS, N_KINDS):
            comb = rpath(ctx.cfg, kinds[0], R)
            if not ctx.exists(comb):
                missing.append(comb)
                continue
            h, rows = read_csv_rows(ctx.full(comb))
            if "split" not in h:
                problems.append(f"{comb}: no 'split' column")
                continue
            si = h.index("split")
            other = [r for r in rows if len(r) <= si or r[si] not in SPLITS]
            if other:
                problems.append(f"{comb}: {len(other)} rows whose split is not train/val")
            for s, kind in zip(SPLITS, kinds[1:]):
                part = rpath(ctx.cfg, kind, R)
                if not ctx.exists(part):
                    missing.append(part)
                    continue
                ph, prows = read_csv_rows(ctx.full(part))
                if ph != h:
                    problems.append(f"{part}: header differs from {comb}")
                expect = [r for r in rows if len(r) > si and r[si] == s]
                if prows != expect:
                    i = next((i for i, (a, b) in enumerate(zip(prows, expect)) if a != b),
                             min(len(prows), len(expect)))
                    problems.append(f"{part}: {len(prows)} rows vs {len(expect)} '{s}' rows of "
                                    f"{comb}; first difference at data row {i}")
    return problems, missing


def gate_E2(ctx):
    problems, missing = [], []
    P = ctx.pooled("thinned_positives", missing)
    if P is not None:
        x, y = ctx.xy(P)
        pairs = close_pairs(x, y, ctx.C["MIN_SPACING_M"])
        if len(pairs):
            i, j = pairs[0]
            problems.append(f"{len(pairs)} positive pairs closer than {ctx.C['MIN_SPACING_M']} m "
                            f"(pooled), e.g. {P['_R'][i]} ({P['longitude'][i]}, {P['latitude'][i]}) - "
                            f"{P['_R'][j]} ({P['longitude'][j]}, {P['latitude'][j]})")
    return problems, missing


def _dups_and_pairs(ctx, df, label, problems):
    keys = key_list(df, ctx.C["KEY_DECIMALS"])
    nd = len(keys) - len(set(keys))
    if nd:
        problems.append(f"{label}: {nd} duplicate keys")
    x, y = ctx.xy(df)
    pairs = close_pairs(x, y, ctx.C["MIN_SPACING_M"])
    if len(pairs):
        problems.append(f"{label}: {len(pairs)} pairs closer than {ctx.C['MIN_SPACING_M']} m")


def gate_E3(ctx, include_C=True):
    problems, missing = [], []
    N = ctx.pooled("negatives", missing)
    if N is not None:
        _dups_and_pairs(ctx, N, "N (pooled)", problems)
    if include_C:
        c = ctx.try_csv(rpath(ctx.cfg, "candidate_pool"), missing)
        if c is not None:
            _dups_and_pairs(ctx, c, "C", problems)
    return problems, missing


def gate_E4(ctx):
    problems, missing = [], []
    d = ctx.C["KEY_DECIMALS"]
    allkeys = {}
    for cls, kind in (("P", "thinned_positives"), ("N", "negatives")):
        df = ctx.pooled(kind, missing)
        if df is None:
            continue
        if "split" not in df:
            problems.append(f"{cls}: no 'split' column")
            continue
        keys = key_list(df, d)
        sp = df["split"].astype(str).tolist()
        tr = {k for k, s in zip(keys, sp) if s == "train"}
        va = {k for k, s in zip(keys, sp) if s == "val"}
        both = tr & va
        if both:
            problems.append(f"{cls}: {len(both)} keys in both train and val, e.g. {sorted(both)[:2]}")
        allkeys[cls] = set(keys)
    if "P" in allkeys and "N" in allkeys:
        sh = allkeys["P"] & allkeys["N"]
        if sh:
            problems.append(f"{len(sh)} keys shared by positives and negatives")
    return problems, missing


def gate_E5(ctx):
    problems, missing = [], []
    import numpy as np
    bids, sps = [], []
    for kind in ("thinned_positives", "negatives"):
        df = ctx.pooled(kind, missing)
        if df is None:
            continue
        if "split" not in df:
            problems.append(f"{kind}: no 'split' column")
            continue
        x, y = ctx.xy(df)
        bids.extend(block_ids(x, y, ctx.cfg).tolist())
        sps.extend(df["split"].astype(str).tolist())
    seen = {}
    for b, s in zip(bids, sps):
        seen.setdefault(b, set()).add(s)
    mixed = [b for b, s in seen.items() if len(s) > 1]
    if mixed:
        problems.append(f"{len(mixed)} recomputed blocks hold both train and val records, "
                        f"e.g. {sorted(mixed)[:3]}")
    return problems, missing


def gate_E6(ctx, include_C=True, include_B=True):
    problems, missing = [], []
    frames = []
    for kind in ("thinned_positives", "negatives"):
        for R in ctx.regions:
            rel = rpath(ctx.cfg, kind, R)
            df = ctx.try_csv(rel, missing)
            if df is not None:
                frames.append((rel, df))
    if include_C:
        rel = rpath(ctx.cfg, "candidate_pool")
        c = ctx.try_csv(rel, missing)
        if c is not None:
            frames.append((rel, c))
    for rel, df in frames:
        if "block_id" not in df:
            problems.append(f"{rel}: no 'block_id' column")
            continue
        x, y = ctx.xy(df)
        rec = block_ids(x, y, ctx.cfg)
        got = df["block_id"].astype(str).to_numpy()
        bad = int((got != rec).sum())
        if bad:
            problems.append(f"{rel}: {bad} rows whose block_id differs from the recomputed id")
    if include_B:
        brel = rpath(ctx.cfg, "block_assignments")
        B = ctx.try_csv(brel, missing)
        P = ctx.pooled("thinned_positives", missing)
        if B is not None and P is not None and "split" in P and {"block_id", "split"} <= set(B):
            bs = dict(zip(B["block_id"].astype(str), B["split"].astype(str)))
            x, y = ctx.xy(P)
            pb = block_ids(x, y, ctx.cfg)
            absent = sorted({b for b in pb if b not in bs})
            wrong = sorted({b for b, s in zip(pb, P["split"].astype(str)) if b in bs and bs[b] != s})
            if absent:
                problems.append(f"{brel}: {len(absent)} positive blocks absent, e.g. {absent[:3]}")
            if wrong:
                problems.append(f"{brel}: {len(wrong)} blocks whose split differs from their "
                                f"positives', e.g. {wrong[:3]}")
    return problems, missing


def gate_E7(ctx):
    import numpy as np
    problems, missing = [], []
    S = ctx.pooled("sightings", missing)
    if S is None:
        return problems, missing
    sx, sy = ctx.xy(S)
    b = float(ctx.C["BUFFER_M"])
    targets = []
    N = ctx.pooled("negatives", missing)
    if N is not None:
        targets.append(("N (pooled)", N))
    c = ctx.try_csv(rpath(ctx.cfg, "candidate_pool"), missing)
    if c is not None:
        targets.append(("C", c))
    for label, df in targets:
        x, y = ctx.xy(df)
        d2 = min_d2_within(x, y, sx, sy, b)
        bad = int((d2 <= b * b).sum())
        if bad:
            problems.append(f"{label}: {bad} rows within {ctx.C['BUFFER_M']} m of a sighting")
    return problems, missing


def gate_E13(ctx):
    """CR-0017: edge_m > BUFFER_M for every row of N (combined, pooled) and
    C, with edge_m recomputed from lon/lat against the replay's own D."""
    problems, missing = [], []
    b = float(ctx.C["BUFFER_M"])
    targets = []
    N = ctx.pooled("negatives", missing)
    if N is not None:
        targets.append(("N (pooled)", N))
    c = ctx.try_csv(rpath(ctx.cfg, "candidate_pool"), missing)
    if c is not None:
        targets.append(("C", c))
    if not targets:
        return problems, missing
    try:
        D = acquisition_domain(ctx.root, ctx.cfg)
    except MissingInput as e:
        missing.append(e.relpath)
        return problems, missing
    for label, df in targets:
        x, y = ctx.xy(df)
        e = domain_edge_within(x, y, D, b)
        bad = e <= b
        if bad.any():
            i = int(bad.nonzero()[0][0])
            where = f"{df['_R'].iloc[i]} " if "_R" in df else ""
            problems.append(f"{label}: {int(bad.sum())} rows within {ctx.C['BUFFER_M']} m of the "
                            f"sightings' acquisition-domain edge (edge_m <= BUFFER_M), e.g. {where}"
                            f"({df['longitude'].iloc[i]}, {df['latitude'].iloc[i]}) edge_m={e[i]:.3f}")
    return problems, missing


def _year_values(df):
    """(numeric years, non-null-but-unparsable mask) of df['year']."""
    import pandas as pd
    y = pd.to_numeric(df["year"], errors="coerce")
    return y, (df["year"].notna() & y.isna()).to_numpy()


def _year_set_text(ys):
    return "{" + ", ".join(str(int(v)) if float(v).is_integer() else repr(float(v))
                           for v in sorted(ys)) + "}"


def gate_E14(ctx, include_C=True):
    """CR-0019 section 3. (a) every row of P and N (combined, pooled) has a
    non-null, integral year >= YEAR_MIN; every non-null year of C is >=
    YEAR_MIN. (b) the set of distinct years in P equals the set in N, pooled
    over regions and splits. pandas/numpy only (standing subset)."""
    import numpy as np
    problems, missing = [], []
    ymin = ctx.C["YEAR_MIN"]
    years = {}
    for cls, kind in (("P", "thinned_positives"), ("N", "negatives")):
        df = ctx.pooled(kind, missing)
        if df is None:
            continue
        if "year" not in df:
            problems.append(f"{cls}: no 'year' column")
            continue
        y, unparsable = _year_values(df)
        v = y.to_numpy(dtype=float)
        with np.errstate(invalid="ignore"):
            bad = np.isnan(v) | (v != np.floor(v)) | (v < ymin)
        if bad.any():
            by_r = {R: int((bad & (df["_R"] == R).to_numpy()).sum()) for R in ctx.regions}
            n_null = int((np.isnan(v) & ~unparsable).sum())
            n_frac = int((~np.isnan(v) & (v != np.floor(v))).sum())
            n_low = int((~np.isnan(v) & (v < ymin)).sum())
            i = int(bad.nonzero()[0][0])
            problems.append(f"{cls} (combined, pooled): {int(bad.sum())} rows without an integral "
                            f"year >= YEAR_MIN {ymin} ({', '.join(f'{R} {n}' for R, n in by_r.items() if n)}; "
                            f"year < YEAR_MIN {n_low}, null {n_null}, non-integral {n_frac}, "
                            f"unparsable {int(unparsable.sum())}), e.g. {df['_R'].iloc[i]} "
                            f"({df['longitude'].iloc[i]}, {df['latitude'].iloc[i]}) "
                            f"year={df['year'].iloc[i]}")
        years[cls] = set(float(t) for t in v[~np.isnan(v)])
    if include_C:
        rel = rpath(ctx.cfg, "candidate_pool")
        c = ctx.try_csv(rel, missing)
        if c is not None:
            if "year" not in c:
                problems.append(f"C: {rel} has no 'year' column")
            else:
                y, unparsable = _year_values(c)
                v = y.to_numpy(dtype=float)
                with np.errstate(invalid="ignore"):
                    bad = unparsable | (v < ymin)
                if bad.any():
                    i = int(bad.nonzero()[0][0])
                    problems.append(f"C: {int(bad.sum())} rows with a non-null year < YEAR_MIN {ymin} "
                                    f"(unparsable {int(unparsable.sum())}), e.g. "
                                    f"({c['longitude'].iloc[i]}, {c['latitude'].iloc[i]}) "
                                    f"year={c['year'].iloc[i]}")
    if "P" in years and "N" in years and years["P"] != years["N"]:
        problems.append(f"distinct years differ (P vs N, pooled over regions and splits): "
                        f"P {_year_set_text(years['P'])} vs N {_year_set_text(years['N'])}; "
                        f"only in P {_year_set_text(years['P'] - years['N'])}, "
                        f"only in N {_year_set_text(years['N'] - years['P'])}")
    return problems, missing


def gate_E8(ctx):
    problems, missing = [], []
    targets = []
    for kind in ("thinned_positives", "negatives"):
        for R in ctx.regions:
            rel = rpath(ctx.cfg, kind, R)
            df = ctx.try_csv(rel, missing)
            if df is not None:
                targets.append((rel, R, df))
    crel = rpath(ctx.cfg, "candidate_pool")
    c = ctx.try_csv(crel, missing)
    if c is not None:
        if "region" not in c:
            problems.append(f"{crel}: no 'region' column; rasters cannot be resolved")
        else:
            for R in ctx.regions:
                targets.append((f"{crel}[{R}]", R, c[c["region"].astype(str) == R]))
    for label, R, df in targets:
        try:
            ok = window_mask(df, R, ctx.rasters, ctx.cfg)
        except Exception as e:
            problems.append(f"{label}: window predicate not evaluable ({type(e).__name__}: {e})")
            continue
        bad = int((~ok).sum())
        if bad:
            i = int((~ok).nonzero()[0][0])
            problems.append(f"{label}: {bad} rows fail the {ctx.C['WINDOW_PX']} px window predicate, "
                            f"e.g. ({df['longitude'].iloc[i]}, {df['latitude'].iloc[i]})")
    return problems, missing


def gate_E9(ctx):
    problems, missing = [], []
    c = ctx.try_csv(rpath(ctx.cfg, "candidate_pool"), missing)
    for R in ctx.regions:
        P = ctx.try_csv(rpath(ctx.cfg, "thinned_positives", R), missing)
        N = ctx.try_csv(rpath(ctx.cfg, "negatives", R), missing)
        if P is None or N is None:
            continue
        if "split" not in P or "split" not in N or "is_nonveg" not in N:
            problems.append(f"[{R}] split/is_nonveg columns absent")
            continue
        for s in SPLITS:
            n_pos = int((P["split"].astype(str) == s).sum())
            n = py_round(n_pos * ctx.C["NEG_RATIO"])
            Ns = N[N["split"].astype(str) == s]
            if len(Ns) != n:
                problems.append(f"[{R}/{s}] {len(Ns)} negatives != round(n_pos {n_pos} x NEG_RATIO) = {n}")
            nv = int(bool_array(Ns["is_nonveg"]).sum()) if len(Ns) else 0
            cap = py_round(n * ctx.C["NONVEG_MAX_FRAC"])
            if nv > cap:
                problems.append(f"[{R}/{s}] {nv} NonVeg negatives > cap {cap}")
            if c is not None and {"region", "split", "is_nonveg"} <= set(c):
                cs = c[(c["region"].astype(str) == R) & (c["split"].astype(str) == s)]
                nvp = int(bool_array(cs["is_nonveg"]).sum()) if len(cs) else 0
                n_hab = n - min(cap, nvp)
                if len(cs) - nvp < n_hab:
                    problems.append(f"[{R}/{s}] habitat pool {len(cs) - nvp} < habitat target {n_hab}")
    return problems, missing


def gate_E10(ctx):
    problems, missing = [], []
    try:
        phys = load_crosswalk(ctx.root, ctx.cfg)
    except MissingInput as e:
        missing.append(e.relpath)
        return problems, missing
    targets = []
    for R in ctx.regions:
        rel = rpath(ctx.cfg, "negatives", R)
        df = ctx.try_csv(rel, missing)
        if df is not None:
            targets.append((rel, R, df))
    crel = rpath(ctx.cfg, "candidate_pool")
    c = ctx.try_csv(crel, missing)
    if c is not None and "region" in c:
        for R in ctx.regions:
            targets.append((f"{crel}[{R}]", R, c[c["region"].astype(str) == R]))
    elif c is not None:
        problems.append(f"{crel}: no 'region' column")
    for label, R, df in targets:
        S = ctx.try_csv(rpath(ctx.cfg, "sightings", R), missing)
        M = ctx.try_csv(rpath(ctx.cfg, "envelope_metrics", R), missing)
        if S is None or M is None:
            continue
        need = ["evt", "sclass", "evh", "evt_phys", "envelope_id", "is_nonveg", "weight", "weight_basis"]
        lack = [n for n in need if n not in df]
        if lack:
            problems.append(f"{label}: columns {lack} absent")
            continue
        try:
            exp = annotate(df[["evt", "sclass", "evh"]].reset_index(drop=True), S, M, phys,
                           ctx.cfg, ctx.C)
        except Exception as e:
            problems.append(f"{label}: recomputation failed ({type(e).__name__}: {e})")
            continue
        got = df.reset_index(drop=True)
        for col in ("evt_phys", "envelope_id", "is_nonveg", "weight", "weight_basis"):
            a, b = got[col], exp[col]
            if col == "is_nonveg":
                import pandas as pd
                a = pd.Series(bool_array(a))
                b = pd.Series(bool_array(b))
            mm = mismatch_mask(a, b, ctx.tol)
            if mm.any():
                i = int(mm.nonzero()[0][0])
                problems.append(f"{label}: '{col}' differs from the recomputed value on "
                                f"{int(mm.sum())} rows, e.g. {a.iloc[i]!r} vs {b.iloc[i]!r}")
    return problems, missing


def parse_regions_py(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    vals = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
            value = node.value
        for t in targets:
            try:
                vals[t.id] = ast.literal_eval(value)
            except Exception:
                vals[t.id] = "<not a literal>"
    return vals


def regions_py_path(cfg):
    p = cfg["regions_py"]["path"]
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


def _cfg_lookup(cfg, dotted):
    v = cfg
    for part in dotted.split("."):
        v = v[part]
    return v


def gate_E11(ctx):
    problems, missing = [], []
    cfg = ctx.cfg
    # running environment (stated limit 7)
    env = current_environment()
    cenv = {k: cfg["environment"][k] for k in ENV_KEYS}
    if env != cenv:
        diff = {k: (env.get(k), cenv.get(k)) for k in ENV_KEYS if env.get(k) != cenv.get(k)}
        problems.append(f"running environment differs from the config: {diff}")
    # regions.py
    rp = regions_py_path(cfg)
    if not os.path.exists(rp):
        missing.append(rp)
    else:
        vals = parse_regions_py(rp)
        for cname, pyname in cfg["regions_py"]["names"].items():
            if pyname not in vals:
                problems.append(f"regions.py: {pyname} not defined (config {cname} = "
                                f"{cfg['constants'][cname]!r})")
            elif _norm_json(vals[pyname]) != _norm_json(cfg["constants"][cname]):
                problems.append(f"regions.py: {pyname} = {vals[pyname]!r} != config "
                                f"{cfg['constants'][cname]!r}")
        for pyname, dotted in cfg["regions_py"].get("extra", {}).items():
            want = _cfg_lookup(cfg, dotted)
            if pyname not in vals:
                problems.append(f"regions.py: {pyname} not defined")
            elif _norm_json(vals[pyname]) != _norm_json(want):
                problems.append(f"regions.py: {pyname} = {vals[pyname]!r} != config {want!r}")
    # inputs on disk: S and I
    required = set()
    for R in ctx.regions:
        for k in ("sightings", "envelope_metrics", "gbif_candidates"):
            required.add(rpath(cfg, k, R))
    required.add(cfg["paths"]["crosswalk"]["path"])
    required.add(county_rel(cfg))
    rep = ctx.replay()
    rasters = set(rep.rasters.read) | (set(ctx.rasters.read) if ctx.rasters else set())
    required |= rasters
    disk = {}
    for rel in sorted(required):
        if ctx.exists(rel):
            disk[rel] = sha256_file(ctx.full(rel))
        else:
            missing.append(rel)
    ctx.input_digests = disk
    ctx.raster_inputs = sorted(r for r in rasters if ctx.exists(r))
    M = ctx.manifest(missing)
    if M is None:
        return problems, missing
    digested = digested_paths(cfg)
    m_in, m_out = {}, {}
    for sec in cfg["columns"]["split_manifest_sections"]:
        s = M.get(sec)
        if not isinstance(s, dict):
            problems.append(f"manifest: section '{sec}' absent")
            continue
        for fld, want in (("constants", cfg["constants"]), ("hash_spec", cfg["hash_spec"])):
            if _norm_json(s.get(fld)) != _norm_json(want):
                got = s.get(fld) or {}
                diff = sorted(k for k in set(got) | set(want)
                              if _norm_json(got.get(k)) != _norm_json(want.get(k)))
                problems.append(f"manifest[{sec}].{fld} differs from the config ({diff})")
        senv = {k: v for k, v in (s.get("environment") or {}).items() if k not in ENV_DESCRIPTIVE}
        if senv != cenv:
            diff = {k: (senv.get(k), cenv.get(k)) for k in sorted(set(senv) | set(cenv))
                    if senv.get(k) != cenv.get(k)}
            problems.append(f"manifest[{sec}].environment (as used) differs from the config: {diff}")
        m_in.update(s.get("inputs") or {})
        for rel, h in (s.get("outputs") or {}).items():
            m_out[rel] = h
    if set(m_out) != set(digested):
        problems.append(f"manifest outputs: {len(set(digested) - set(m_out))} digested artifacts "
                        f"not listed, {len(set(m_out) - set(digested))} unexpected entries")
    for rel in digested:
        if not ctx.exists(rel):
            if rel not in missing:
                missing.append(rel)
        elif rel in m_out and m_out[rel] != sha256_file(ctx.full(rel)):
            problems.append(f"manifest output digest of {rel} differs from the file on disk")
    unl = sorted(r for r in disk if r not in m_in)
    if unl:
        problems.append(f"manifest inputs: {len(unl)} files of S/I not listed, e.g. {unl[:3]}")
    for rel, h in m_in.items():
        if rel in disk:
            if disk[rel] != h:
                problems.append(f"input {rel} changed after the manifest (sha256 differs)")
        elif rel in digested:
            if ctx.exists(rel) and sha256_file(ctx.full(rel)) != h:
                problems.append(f"input {rel} differs from the manifest")
        else:
            problems.append(f"manifest lists an input outside S and I: {rel}")
    return problems, missing


def gate_E12(ctx):
    problems, missing = [], []
    targets = []
    for R in ctx.regions:
        rel = rpath(ctx.cfg, "negatives", R)
        df = ctx.try_csv(rel, missing)
        if df is not None:
            targets.append((rel, df))
    crel = rpath(ctx.cfg, "candidate_pool")
    c = ctx.try_csv(crel, missing)
    if c is not None:
        targets.append((crel, c))
    for label, df in targets:
        try:
            bad = verify_partition(df["longitude"].to_numpy(), df["latitude"].to_numpy(),
                                   df["state"].astype(str).tolist(), ctx.root, ctx.cfg)
        except MissingInput as e:
            missing.append(e.relpath)
            continue
        if bad.any():
            i = int(bad.nonzero()[0][0])
            problems.append(f"{label}: verify_partition returns {int(bad.sum())} rows, e.g. "
                            f"{df['state'].iloc[i]} ({df['longitude'].iloc[i]}, {df['latitude'].iloc[i]})")
    M = ctx.manifest(missing)
    rep = ctx.replay()
    exp = None
    if rep.pool_full is not None or rep.dropped:
        exp = rep.dropped
    else:
        try:
            r2 = Replay(ctx.root, ctx.cfg)
            r2.pool_until_partition()
            exp = r2.dropped
        except MissingInput as e:
            missing.append(e.relpath)
        except Exception as e:
            problems.append(f"dropped-list recomputation failed ({type(e).__name__}: {e})")
    if M is not None and exp is not None:
        got = (M.get("negatives") or {}).get("dropped")
        if got is None:
            problems.append("manifest[negatives].dropped absent")
        elif _norm_json(sorted(got)) != _norm_json(exp):
            problems.append(f"manifest dropped list ({len(got)} rows) != recomputation ({len(exp)} rows)")
    return problems, missing


def _replay_stage_problem(rep, stages):
    for s in stages:
        e = rep.errors.get(s)
        if e is not None:
            if isinstance(e, MissingInput):
                return None, e.relpath
            return f"replay stage '{s}' raised {type(e).__name__}: {e}", None
    return None, None


def _check_counts(ctx, M, section, rep_counts, label, problems, extra_key=None):
    if M is None:
        return
    got = (M.get(section) or {}).get(extra_key or "counts")
    if got is None:
        problems.append(f"manifest[{section}].{extra_key or 'counts'} absent")
        return
    if _norm_json(got) != _norm_json(rep_counts):
        diffs = []
        for R in sorted(set(got) | set(rep_counts)):
            a, b = got.get(R, {}), rep_counts.get(R, {})
            for k in sorted(set(a) | set(b), key=str):
                if _norm_json(a.get(k)) != _norm_json(b.get(k)):
                    diffs.append(f"{R}.{k}: {a.get(k)} vs replay {b.get(k)}")
        problems.append(f"{label}: manifest counts differ: {'; '.join(diffs[:6])}")


def _compare_region_files(ctx, kinds, frames_by_R, problems, missing):
    for R in ctx.regions:
        exp_all = frames_by_R.get(R)
        for kind in kinds:
            rel = rpath(ctx.cfg, kind, R)
            act = ctx.try_csv(rel, missing)
            if act is None or exp_all is None:
                continue
            if kind.startswith("train_"):
                exp = exp_all[exp_all["split"] == "train"]
            elif kind.startswith("val_"):
                exp = exp_all[exp_all["split"] == "val"]
            else:
                exp = exp_all
            order = ctx.cfg["row_order"]["positives" if kind in P_KINDS else "negatives"]
            problems.extend(compare_frames(act, csv_roundtrip(exp), "coord", ctx.tol, rel,
                                           ctx.C["KEY_DECIMALS"], order_cols=order))


def gate_R1(ctx):
    problems, missing = [], []
    rep = ctx.replay()
    err, miss = _replay_stage_problem(rep, ["positives"])
    M = ctx.manifest(missing)
    if miss:
        missing.append(miss)
    if err:
        problems.append(err)
    if rep.pos is None:
        return problems, missing
    _compare_region_files(ctx, P_KINDS, rep.pos, problems, missing)
    _check_counts(ctx, M, "positives", rep.counts["positives"], "positives (incl. windowless drop, step 3)",
                  problems)
    return problems, missing


def gate_R2(ctx):
    problems, missing = [], []
    rep = ctx.replay()
    err, miss = _replay_stage_problem(rep, ["positives"])
    if miss:
        missing.append(miss)
    if err:
        problems.append(err)
    if rep.B is None:
        return problems, missing
    rel = rpath(ctx.cfg, "block_assignments")
    act = ctx.try_csv(rel, missing)
    if act is not None:
        problems.extend(compare_frames(act, csv_roundtrip(rep.B), "block_id", ctx.tol, rel,
                                       order_cols=ctx.cfg["row_order"]["block_assignments"]))
    return problems, missing


def gate_R3(ctx):
    problems, missing = [], []
    rep = ctx.replay()
    err, miss = _replay_stage_problem(rep, ["positives", "pool"])
    M = ctx.manifest(missing)
    if miss:
        missing.append(miss)
    if err:
        problems.append(err)
    if rep.pool_full is None:
        return problems, missing
    rel = rpath(ctx.cfg, "candidate_pool")
    act = ctx.try_csv(rel, missing)
    if act is not None:
        problems.extend(compare_frames(act, csv_roundtrip(rep.pool), "coord", ctx.tol, rel,
                                       ctx.C["KEY_DECIMALS"], order_cols=ctx.cfg["row_order"]["pool"]))
    _check_counts(ctx, M, "negatives", rep.counts["negatives"], "pool steps 1-11", problems)
    return problems, missing


def gate_R4(ctx):
    problems, missing = [], []
    rep = ctx.replay()
    err, miss = _replay_stage_problem(rep, ["positives", "pool", "draw"])
    M = ctx.manifest(missing)
    if miss:
        missing.append(miss)
    if err:
        problems.append(err)
    if rep.neg is None:
        return problems, missing
    _compare_region_files(ctx, N_KINDS, rep.neg, problems, missing)
    _check_counts(ctx, M, "negatives", rep.draw_counts, "draw", problems, extra_key="draw")
    return problems, missing


GATES = [("E0", gate_E0), ("E1", gate_E1), ("E1p", gate_E1p), ("E2", gate_E2), ("E3", gate_E3),
         ("E4", gate_E4), ("E5", gate_E5), ("E6", gate_E6), ("E7", gate_E7), ("E8", gate_E8),
         ("E9", gate_E9), ("E10", gate_E10), ("R1", gate_R1), ("R2", gate_R2), ("R3", gate_R3),
         ("R4", gate_R4), ("E11", gate_E11), ("E12", gate_E12), ("E13", gate_E13),
         ("E14", gate_E14)]


def evaluate(fn, ctx, **kw):
    try:
        problems, missing = fn(ctx, **kw)
    except MissingInput as e:
        problems, missing = [], [e.relpath]
    except Exception as e:
        problems = [f"gate not evaluable: {type(e).__name__}: {e}",
                    traceback.format_exc(limit=3).strip().splitlines()[-1]]
        missing = []
    missing = list(dict.fromkeys(missing))
    notes = [p for p in problems if p.startswith("NOTE:")]
    problems = [p for p in problems if not p.startswith("NOTE:")]
    evaluate.notes = notes
    return ("PASS" if _fail_unless(problems, missing) else "FAIL"), problems, missing


def run_gates(root, cfg, only=None):
    ctx = Context(root, cfg)
    results = {}
    for gid, fn in GATES:
        if only and gid not in only:
            continue
        t0 = time.time()
        status, problems, missing = evaluate(fn, ctx)
        results[gid] = {"status": status, "problems": problems, "missing": missing,
                        "notes": list(evaluate.notes), "seconds": round(time.time() - t0, 2)}
    return ctx, results


# ==========================================================================
# OBSERVATIONS (never blocking)
# ==========================================================================
def _hist(labels, weights=None):
    tot = {}
    if weights is None:
        weights = [1.0] * len(labels)
    for l, w in zip(labels, weights):
        k = "<NA>" if l is None or (isinstance(l, float) and math.isnan(l)) else str(l)
        tot[k] = tot.get(k, 0.0) + float(w)
    s = sum(tot.values())
    return {k: v / s for k, v in tot.items()} if s else {}


def _tv(p, q):
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in set(p) | set(q))


def _ks(a, b):
    import numpy as np
    from scipy.stats import ks_2samp
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    return float(ks_2samp(a, b).statistic)


def _smd(a, b):
    import numpy as np
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    sd = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return float(abs(a.mean() - b.mean()) / sd) if sd > 0 else float("nan")


def _nanmax(vals):
    v = [x for x in vals if x == x]
    return max(v) if v else float("nan")


def moran_i(xs, ys, z, k):
    import numpy as np
    from scipy.spatial import cKDTree
    n = len(z)
    if n <= k + 1:
        return float("nan"), None
    _, idx = cKDTree(np.column_stack([xs, ys])).query(np.column_stack([xs, ys]), k=k + 1)
    nb = idx[:, 1:]
    z = np.asarray(z, dtype=float)

    def stat(zz):
        d = zz - zz.mean()
        den = (d * d).sum()
        if den == 0:
            return float("nan")
        return float((d * d[nb].mean(axis=1)).sum() / den)
    return stat(z), stat


class ObsData:
    """The frames O1-O10 read. From the pipeline's files in a full run."""

    def __init__(self, P, N, Cp, cfg):
        self.P, self.N, self.C, self.cfg = P, N, Cp, cfg


def _region_col(df):
    return df["region"].astype(str) if "region" in df else df["_R"].astype(str)


def stats_split(P, split, cont, cfg, regions):
    """O1, O2, O8 (positives) for a given positive split."""
    import numpy as np
    out = {}
    split = np.asarray(split).astype(str)
    x, y = P["_x"].to_numpy(), P["_y"].to_numpy()
    va, tr = split == "val", split == "train"
    d = nearest_dist(x[va], y[va], x[tr], y[tr])
    out["O1.median_m"] = float(np.median(d)) if len(d) else float("nan")
    bids = P["_block"].to_numpy()
    vb = set(bids[va])
    allb = set(bids)
    out["O2.records_per_val_block"] = (float(va.sum()) / len(vb)) if vb else float("nan")
    out["O2.share_gap"] = abs(len(vb) / len(allb) - float(va.mean())) if len(allb) else float("nan")
    reg = _region_col(P).to_numpy()
    for scope in ["pooled"] + list(regions):
        m = np.ones(len(P), bool) if scope == "pooled" else reg == scope
        ks = [_ks(cont[f][m & va], cont[f][m & tr]) for f in cont]
        sm = [_smd(cont[f][m & va], cont[f][m & tr]) for f in cont]
        out[f"O8.pos_ks.{scope}"] = _nanmax(ks)
        out[f"O8.pos_smd.{scope}"] = _nanmax(sm)
    return out


def stats_draw(P, Nsel, Cp, contN, cfg, regions):
    """O5, O6, O8 (negatives) for a given selected set."""
    import numpy as np
    out = {}
    rf = float(cfg["obs"]["RF_M"])
    preg, nreg = _region_col(P).to_numpy(), _region_col(Nsel).to_numpy()
    psp = P["split"].astype(str).to_numpy()
    nsp = Nsel["split"].astype(str).to_numpy()
    nnv = bool_array(Nsel["is_nonveg"]) if "is_nonveg" in Nsel else np.zeros(len(Nsel), bool)
    creg = _region_col(Cp).to_numpy() if Cp is not None else None
    for R in regions:
        pm, nm = preg == R, nreg == R
        d = nearest_dist(P["_x"].to_numpy()[pm], P["_y"].to_numpy()[pm],
                         Nsel["_x"].to_numpy()[nm], Nsel["_y"].to_numpy()[nm])
        out[f"O5.Exc.{R}"] = float(np.mean(np.maximum(0, d - rf)) / 1000) if len(d) else float("nan")
        out[f"O5.S.{R}"] = float(np.mean(d > rf)) if len(d) else float("nan")
        pv, nv_ = pm & (psp == "val"), nm & (nsp == "val")
        d = nearest_dist(P["_x"].to_numpy()[pv], P["_y"].to_numpy()[pv],
                         Nsel["_x"].to_numpy()[nv_], Nsel["_y"].to_numpy()[nv_])
        out[f"O5.Excws_val.{R}"] = float(np.mean(np.maximum(0, d - rf)) / 1000) if len(d) else float("nan")
        out[f"O5.Sws_val.{R}"] = float(np.mean(d > rf)) if len(d) else float("nan")
        sub = Nsel[nm]
        snv, ssp = nnv[nm], nsp[nm]
        tr, va = ssp == "train", ssp == "val"
        out[f"O6.nonveg_val_minus_train.{R}"] = (
            float(snv[va].mean() - snv[tr].mean()) if va.any() and tr.any() else float("nan"))
        if "weight_basis" in sub:
            wb = sub["weight_basis"].tolist()
            out[f"O6.basis_tv_train_val.{R}"] = _tv(_hist([b for b, t in zip(wb, tr) if t]),
                                                    _hist([b for b, v in zip(wb, va) if v]))
        if Cp is not None and "weight" in Cp and "weight_basis" in sub:
            cs = Cp[creg == R]
            cnv = bool_array(cs["is_nonveg"])
            out[f"O6.basis_tv_sel_vs_wpool.{R}"] = _tv(_hist(sub["weight_basis"].tolist()),
                                                       _hist(cs["weight_basis"].tolist(),
                                                             cs["weight"].tolist()))
            ws, wp = sub["weight"].to_numpy()[~snv], cs["weight"].to_numpy()[~cnv]
            out[f"O6.hab_weight_sel_over_pool.{R}"] = (float(ws.mean() / wp.mean())
                                                       if len(ws) and len(wp) else float("nan"))
            out[f"O6.evtphys_tv_nonveg.{R}"] = _tv(_hist(sub["evt_phys"][snv].tolist()),
                                                   _hist(cs["evt_phys"][cnv].tolist()))
            out[f"O6.species_tv.{R}"] = _tv(_hist(sub["common_name"].tolist()),
                                            _hist(cs["common_name"].tolist()))
    for scope in ["pooled"] + list(regions):
        m = np.ones(len(Nsel), bool) if scope == "pooled" else nreg == scope
        tr, va = m & (nsp == "train"), m & (nsp == "val")
        out[f"O8.neg_ks.{scope}"] = _nanmax([_ks(contN[f][va], contN[f][tr]) for f in contN])
        out[f"O8.neghab_ks.{scope}"] = _nanmax([_ks(contN[f][va & ~nnv], contN[f][tr & ~nnv])
                                                for f in contN])
        out[f"O8.neg_smd.{scope}"] = _nanmax([_smd(contN[f][va], contN[f][tr]) for f in contN])
    return out


def stats_fixed(P, Nsel, Cp, cfg, regions, perm=True):
    """O3, O4, O7, O9, O10 (O3/O4 carry their in-run N-perm z)."""
    import numpy as np
    out, zs = {}, {}
    ob = cfg["obs"]
    bs = float(cfg["constants"]["BLOCK_SIZE_M"])
    x0, y0 = cfg["constants"]["BLOCK_ORIGIN_5070"]
    rng = np.random.default_rng(ob["perm_seed"])

    def blocks_val(frames):
        d = {}
        for df in frames:
            for b, s in zip(df["_block"].tolist(), df["split"].astype(str).tolist()):
                d[b] = d.get(b, False) or s == "val"
        return d

    def centres(bl):
        xs, ys = [], []
        for b in bl:
            a, c = b.split("_")
            xs.append((int(a) + 0.5) * bs + x0)
            ys.append((int(c) + 0.5) * bs + y0)
        return np.array(xs), np.array(ys)

    sets = [("O3", "positive blocks", [P])]
    if Nsel is not None:
        sets.append(("O4", "selected-record blocks", [P, Nsel]))
    if Cp is not None:
        sets.append(("O4", "pool blocks", [Cp]))
    for oid, label, frames in sets:
        bv = blocks_val(frames)
        bl = sorted(bv)
        xs, ys = centres(bl)
        z = np.array([1.0 if bv[b] else 0.0 for b in bl])
        for k in ob["moran_k"]:
            I, stat = moran_i(xs, ys, z, k)
            key = f"{oid}.moran_k{k}.{label.replace(' ', '_')}"
            out[key] = I
            if perm and stat is not None and I == I:
                null = np.array([stat(rng.permutation(z)) for _ in range(int(ob["n_perm"]))])
                sd = null.std(ddof=1)
                zs[key] = float((I - null.mean()) / sd) if sd > 0 else float("nan")
    preg = _region_col(P).to_numpy()
    if Cp is not None and "is_nonveg" in Cp:
        creg = _region_col(Cp).to_numpy()
        cnv = bool_array(Cp["is_nonveg"])
        csp = Cp["split"].astype(str).to_numpy()
        psp = P["split"].astype(str).to_numpy()
        for R in regions:
            ratios, pool_n, tgt = [], 0, 0
            for s in SPLITS:
                n = py_round(int(((preg == R) & (psp == s)).sum()) * cfg["constants"]["NEG_RATIO"])
                m = (creg == R) & (csp == s)
                nvp = int((m & cnv).sum())
                n_hab = n - min(py_round(n * cfg["constants"]["NONVEG_MAX_FRAC"]), nvp)
                ratios.append(int((m & ~cnv).sum()) / n_hab if n_hab else float("inf"))
                pool_n += int(m.sum())
                tgt += n
            out[f"O7.hab_pool_over_target_worst.{R}"] = float(min(ratios))
            out[f"O7.pool_over_target.{R}"] = pool_n / tgt if tgt else float("nan")
            pm = preg == R
            px, py = P["_x"].to_numpy()[pm], P["_y"].to_numpy()[pm]
            d = nearest_dist(px, py, Cp["_x"].to_numpy()[creg == R], Cp["_y"].to_numpy()[creg == R])
            cell = [(math.floor(a / ob["sup_cell_m"]), math.floor(b / ob["sup_cell_m"]))
                    for a, b in zip(px, py)]
            bycell = {}
            for c, dd in zip(cell, d):
                bycell.setdefault(c, []).append(dd)
            meds = [float(np.median(v)) for v in bycell.values() if len(v) >= ob["sup_min_positives"]]
            if meds:
                m_ = float(np.median(meds))
                out[f"O7.SUP_O.{R}"] = int((d > ob["sup_factor"] * m_).sum())
                out[f"O7.SUP_R.{R}"] = float(max(meds) / m_) if m_ > 0 else float("nan")
    for cls, df in (("pos", P), ("neg", Nsel)):
        if df is None:
            continue
        reg = _region_col(df).to_numpy()
        for R in regions:
            m = reg == R
            if "year" in df:
                yrs = df["year"][m].dropna().astype(int).value_counts().sort_index()
                out[f"O9.year_hist.{cls}.{R}"] = {str(k): int(v) for k, v in yrs.items()}
            if "split" in df:
                out[f"O10.val_fraction.{cls}.{R}"] = (float((df["split"][m].astype(str) == "val").mean())
                                                      if m.any() else float("nan"))
    return out, zs


def _prep_obs_frame(df, cfg, xy_fn):
    df = df.copy()
    x, y = xy_fn(df)
    df["_x"], df["_y"] = x, y
    df["_block"] = block_ids(x, y, cfg)
    return df


def _cont_values(df, rasters, cfg, regions):
    import numpy as np
    feats = cfg["continuous_features"]
    out = {f: np.full(len(df), np.nan) for f in feats}
    reg = _region_col(df).to_numpy()
    for R in regions:
        m = reg == R
        if not m.any():
            continue
        vals = sample_features(df[m], R, rasters, cfg, feats)
        for f in feats:
            out[f][m] = vals[f]
    return out


def compute_obs(ctx):
    """Values (and in-run N-perm z) of O1-O10 on the pipeline's files."""
    missing = []
    P = ctx.pooled("thinned_positives", missing)
    N = ctx.pooled("negatives", missing)
    Cp = ctx.try_csv(rpath(ctx.cfg, "candidate_pool"), missing)
    notes = {}
    if P is None or "split" not in P:
        return {}, {}, {"all": f"positives unavailable ({missing[:2]})"}
    P = _prep_obs_frame(P, ctx.cfg, ctx.xy)
    N = _prep_obs_frame(N, ctx.cfg, ctx.xy) if N is not None and "split" in N else None
    Cp = _prep_obs_frame(Cp, ctx.cfg, ctx.xy) if Cp is not None and "split" in Cp else None
    vals, zs = {}, {}
    try:
        contP = _cont_values(P, ctx.rasters, ctx.cfg, ctx.regions)
        vals.update(stats_split(P, P["split"], contP, ctx.cfg, ctx.regions))
    except Exception as e:
        notes["split"] = f"{type(e).__name__}: {e}"
    if N is not None:
        try:
            contN = _cont_values(N, ctx.rasters, ctx.cfg, ctx.regions)
            vals.update(stats_draw(P, N, Cp, contN, ctx.cfg, ctx.regions))
        except Exception as e:
            notes["draw"] = f"{type(e).__name__}: {e}"
    try:
        v, z = stats_fixed(P, N, Cp, ctx.cfg, ctx.regions)
        vals.update(v)
        zs.update(z)
    except Exception as e:
        notes["fixed"] = f"{type(e).__name__}: {e}"
    if missing:
        notes["missing"] = ", ".join(missing[:3])
    return vals, zs, notes


def footing_digest(input_digests):
    if not input_digests:
        return None
    blob = json.dumps(sorted(input_digests.items())).encode()
    return hashlib.sha256(blob).hexdigest()


def obs_path(cfg):
    p = cfg["obs"]["obs_path"]
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


def calibrate(ctx, cfg):
    """N-split and N-draw nulls from the script's own replay; writes the
    OBS file. Only called after every GATE passed."""
    import numpy as np
    rep = ctx.replay()
    ob = cfg["obs"]
    regions = ctx.regions
    P = rep.thinned_all.copy()
    P["_x"], P["_y"] = rep.thinned_xy
    P["_block"] = P["block_id"]
    P["_R"] = P["region"]
    contP = _cont_values(P, rep.rasters, cfg, regions)
    rep.pool_full = rep.pool_full.assign(
        _x=rep.pool_full["x_5070"].to_numpy(dtype=float),
        _y=rep.pool_full["y_5070"].to_numpy(dtype=float),
        _block=rep.pool_full["block_id"].to_numpy(),
        _i=np.arange(len(rep.pool_full)))
    pool = rep.pool_full
    contC = _cont_values(pool, rep.rasters, cfg, regions)
    null = {}

    def add(d, kind):
        for k, v in d.items():
            if isinstance(v, (int, float)) and v == v:
                null.setdefault(k, {"kind": kind, "vals": []})["vals"].append(float(v))

    bids = P["block_id"].to_numpy()
    for i in range(int(ob["n_split"])):
        vb = rep.select_val_blocks(bids, seed=ob["null_seed_base"] + i)
        sp = np.array(["val" if b in vb else "train" for b in bids])
        add(stats_split(P, sp, contP, cfg, regions), "N-split")
    for i in range(int(ob["n_draw"])):
        sel = rep.draw_select(seed=ob["null_seed_base"] + 1_000_000 + i, record=False)
        idx = sel["_i"].to_numpy()
        contN = {f: v[idx] for f, v in contC.items()}
        add(stats_draw(P, sel, pool, contN, cfg, regions), "N-draw")
    refs = {}
    for k, d in null.items():
        v = np.array(d["vals"])
        refs[k] = {"null": d["kind"], "n": int(len(v)), "mean": float(v.mean()),
                   "sd": float(v.std(ddof=1)) if len(v) > 1 else float("nan")}
    vals, zs, notes = compute_obs(ctx)
    obj = {"cr": "CR-0013", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "config_sha256": cfg["_sha256"], "footing": footing_digest(ctx.input_digests),
           "references": refs, "values_at_calibration": vals}
    write_json_atomic(obj, obs_path(cfg))
    return obj


def load_obs_refs(cfg):
    p = obs_path(cfg)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def obs_report(vals, zs, notes, cfg, refs, footing, prev):
    """One line per O-row; each carries OBS."""
    lines = []
    zlim = float(cfg["obs"]["OBS_Z"])
    stale = None
    if refs is None:
        stale = "no references (not calibrated)"
    elif refs.get("footing") != footing:
        stale = "references stale (footing changed)"
    flags = []
    for oid in OBS_IDS:
        items = [(k, v) for k, v in vals.items() if k.split(".")[0] == oid]
        parts = []
        for k, v in sorted(items):
            name = k[len(oid) + 1:]
            if isinstance(v, dict):
                parts.append(f"{name}={json.dumps(v, separators=(',', ':'))}")
                continue
            s = f"{name}={v:.4g}" if isinstance(v, float) else f"{name}={v}"
            z = zs.get(k)
            if z is None and refs and not stale and k in refs.get("references", {}):
                r = refs["references"][k]
                if r["sd"] and r["sd"] == r["sd"] and r["sd"] > 0:
                    z = (v - r["mean"]) / r["sd"]
            if z is not None and z == z:
                s += f" (z={z:+.2f}{' FLAG' if abs(z) > zlim else ''})"
                if abs(z) > zlim:
                    flags.append(k)
            elif prev and k in prev and isinstance(prev[k], (int, float)) and isinstance(v, (int, float)):
                s += f" (delta={v - prev[k]:+.4g})"
            parts.append(s)
        if not parts:
            parts = ["n/a" + (f" ({'; '.join(f'{a}: {b}' for a, b in notes.items())})" if notes else "")]
        lines.append(f"{oid:<4} OBS   " + "; ".join(parts))
    head = f"OBS references: {stale or 'current'}; flags |z| > {zlim:g}: {len(flags)}"
    return [head] + lines, flags


# ==========================================================================
# Record and standing checks
# ==========================================================================
def write_record(ctx, cfg, obs_vals):
    commit, dirty = git_commit()
    op = obs_path(cfg)
    rec = {
        "cr": "CR-0013",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config_path": cfg["_path"],
        "config_sha256": cfg["_sha256"],
        "obs_sha256": sha256_file(op) if os.path.exists(op) else None,
        "artifacts": {rel: sha256_file(ctx.full(rel)) for rel in digested_paths(cfg)},
        "inputs": ctx.input_digests,
        "rasters": [[rel, os.stat(ctx.full(rel)).st_size, os.stat(ctx.full(rel)).st_mtime_ns]
                    for rel in ctx.raster_inputs],
        "commit": commit,
        "dirty": dirty,
        "obs": obs_vals,
    }
    full = ctx.full(rpath(cfg, "acceptance_record"))
    write_json_atomic(rec, full)
    return full, sha256_file(full)


def standing_checks(img_size, jitter, augment, *, data_root=None, config=None):
    """CR-0013 standing subset, called by train.build_datasets (CR-0012
    section 5). Imports only numpy, pandas and scipy. Raises
    AcceptanceError listing every failure."""
    import numpy   # noqa: F401  (the only third-party imports allowed here)
    import pandas  # noqa: F401
    import scipy   # noqa: F401
    cfg = load_config(config)
    root = os.path.abspath(data_root or REPO_ROOT)
    failures = []
    W = int(cfg["constants"]["WINDOW_PX"])
    pad = int(jitter) if augment else 0
    if int(img_size) + 2 * pad > W:
        failures.append(f"window: img_size {img_size} + 2 x pad {pad} > WINDOW_PX {W}")
    rec_rel = rpath(cfg, "acceptance_record")
    rec_full = os.path.join(root, rec_rel)
    if not os.path.exists(rec_full):
        failures.append(f"no acceptance record at {rec_full}: run acceptance_split.py")
    else:
        with open(rec_full, encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("config_sha256") != cfg["_sha256"]:
            failures.append("acceptance record was made under a different config")
        arts = rec.get("artifacts") or {}
        for rel in standing_csv_paths(cfg):
            full = os.path.join(root, rel)
            if not os.path.exists(full):
                failures.append(f"missing {rel}")
            elif arts.get(rel) != sha256_file(full):
                failures.append(f"{rel}: sha256 differs from the acceptance record")
        for rel, size, mtime in rec.get("rasters") or []:
            full = os.path.join(root, rel)
            if not os.path.exists(full):
                failures.append(f"raster missing: {rel}")
                continue
            st = os.stat(full)
            if (st.st_size, st.st_mtime_ns) != (size, mtime):
                failures.append(f"raster changed since acceptance: {rel}")
    ctx = Context(root, cfg, coords="columns")
    for gid, fn, kw in (("E0", gate_E0, {"sets": ("P", "N")}), ("E1", gate_E1, {"include_C": False}),
                        ("E1p", gate_E1p, {}), ("E3", gate_E3, {"include_C": False}),
                        ("E4", gate_E4, {}), ("E5", gate_E5, {}),
                        ("E6", gate_E6, {"include_C": False, "include_B": False}),
                        ("E14", gate_E14, {"include_C": False})):
        status, problems, missing = evaluate(fn, ctx, **kw)
        if status != "PASS":
            failures.extend(f"{gid}: missing {m}" for m in missing)
            failures.extend(f"{gid}: {p}" for p in problems)
    if failures:
        raise AcceptanceError("standing checks failed (CR-0013):\n  " + "\n  ".join(failures))
    return True


# ==========================================================================
# CLI
# ==========================================================================
def format_gate(gid, r):
    head = f"{gid:<4} {r['status']}"
    if r["missing"]:
        head += f"  (missing {r['missing'][0]}" + (f" +{len(r['missing']) - 1} more" if len(r["missing"]) > 1 else "") + ")"
    lines = [head]
    for m in r["missing"][1:]:
        lines.append(f"       missing {m}")
    for p in r["problems"][:12]:
        lines.append(f"       - {p}")
    if len(r["problems"]) > 12:
        lines.append(f"       ... {len(r['problems']) - 12} more")
    for n in r.get("notes", [])[:3]:
        lines.append(f"       {n}")
    return lines


def full_run(root, cfg, do_obs=True, do_calibrate=False, out=print):
    t0 = time.time()
    commit, dirty = git_commit()
    out(f"CR-0013 acceptance_split.py report")
    out(f"data root : {os.path.abspath(root)}")
    out(f"config    : {cfg['_path']} (sha256 {cfg['_sha256']})")
    out(f"commit    : {commit} (dirty tracked .py: {dirty})")
    out(f"started   : {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    out("")
    ctx, results = run_gates(root, cfg)
    out("GATES (exact)")
    for gid in GATE_IDS:
        for line in format_gate(gid, results[gid]):
            out(line)
    ok = all(results[g]["status"] == "PASS" for g in GATE_IDS)
    out("")
    vals, zs = {}, {}
    if do_obs:
        out("OBSERVATIONS (reported, never blocking)")
        try:
            vals, zs, notes = compute_obs(ctx)
            refs = load_obs_refs(cfg)
            prev = None
            rec_full = ctx.full(rpath(cfg, "acceptance_record"))
            if os.path.exists(rec_full):
                try:
                    with open(rec_full, encoding="utf-8") as f:
                        prev = json.load(f).get("obs")
                except Exception:
                    prev = None
            lines, _ = obs_report(vals, zs, notes, cfg, refs, footing_digest(ctx.input_digests), prev)
            for line in lines:
                out(line)
        except Exception as e:
            out(f"OBS computation failed ({type(e).__name__}: {e}); every O-row n/a")
            for oid in OBS_IDS:
                out(f"{oid:<4} OBS   n/a")
        out("")
    npass = sum(results[g]["status"] == "PASS" for g in GATE_IDS)
    out(f"SUMMARY: {npass}/{len(GATE_IDS)} GATEs pass; "
        f"FAIL: {', '.join(g for g in GATE_IDS if results[g]['status'] != 'PASS') or 'none'}")
    if ok:
        if do_calibrate:
            calibrate(ctx, cfg)
            out(f"calibration written: {obs_path(cfg)}")
        path, h = write_record(ctx, cfg, {k: v for k, v in vals.items()})
        out(f"ACCEPTED. record written: {path}")
        out(f"record sha256: {h}")
    else:
        if do_calibrate:
            out("calibration refused: not every GATE passes")
        out("REJECTED. no record written.")
    out(f"runtime: {time.time() - t0:.1f} s")
    return (0 if ok else 1), results


def main(argv=None):
    ap = argparse.ArgumentParser(description="CR-0013 acceptance gates for CR-0012's split and draw.")
    ap.add_argument("--data-root", default=REPO_ROOT)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--emit-reference", metavar="DIR")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--standing", action="store_true")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
    except ConfigError as e:
        print(f"config refused: {e}")
        return 2
    if a.standing:
        s = cfg["standing"]
        try:
            standing_checks(s["img_size_default"], s["jitter_default"], s["augment_default"],
                            data_root=a.data_root, config=a.config)
        except AcceptanceError as e:
            print(e)
            return 1
        print("standing checks: pass")
        return 0
    if a.emit_reference:
        rep = Replay(a.data_root, cfg)
        rep.run(stop_on_error=True)
        written = rep.emit(a.emit_reference)
        for rel in written:
            print(f"wrote {os.path.join(a.emit_reference, rel)}")
        print(f"wrote {os.path.join(a.emit_reference, rpath(cfg, 'split_manifest'))}")
        return 0
    code, _ = full_run(a.data_root, cfg, do_obs=True, do_calibrate=a.calibrate)
    return code


if __name__ == "__main__":
    sys.exit(main())
