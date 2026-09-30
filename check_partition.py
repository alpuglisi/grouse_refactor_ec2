#!/usr/bin/env python3
"""CR-0007 acceptance checks P1-P8 (read-only).

Usage:
    python check_partition.py                 # acceptance run, repo root
    python check_partition.py --only P1 P2    # a subset (never an acceptance run)
    python check_partition.py --assume regions.REGIONS='["ME","NH","VT"]'

The checks are specified in
docs/quality/change-requests/CR-0007-record-partition-and-global-split.md
(section "Acceptance"). This script is independent of the code under test:

* it never imports analyze_grouse.py or calls regions.verify_partition /
  regions.in_state;
* constants are read by `ast.literal_eval` of the named top-level
  assignments in regions.py, analyze_grouse.py and grouse_data.py (their
  single definitions), so no value is duplicated here (PA-0001);
* sampling, the vintage rule, the duplicate-location collapse, the
  polygon test and the KDE are re-implemented below.

`--assume` supplies a constant that the tree does not define yet (e.g.
before CR-0007 deliverable 2). Any run that uses it, or `--only`, prints
NOT AN ACCEPTANCE RUN and exits 2 even when every check passes.

Exit status: 0 all checks pass (acceptance run); 1 a check failed;
2 not an acceptance run.
"""
import argparse
import ast
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

# Geographic lon/lat encoding of the GBIF sighting files (a property of the
# source data). Listed in the CRS-literal inventory of CR-0007's deferred
# CRS BUG; the analysis CRS itself is read from the evaluated files'
# x_<epsg> column name, never written here.
LONLAT_EPSG = 4326

# ---------------------------------------------------------------------------
# P7 lists (CR-0007 "P7"). Paths relative to the repo root.
# ---------------------------------------------------------------------------
# Every module CR-0007 edits, plus the live modules that import regions.
P7_IMPORT = [
    "regions.py", "grouse_data.py", "analyze_grouse.py",
    "predict.py", "download_treemap.py", "download_tcc_nlcd.py",
    "diagnose_road_bias.py", "generate_negatives.py",
    "prepare_training_data.py", "repair_coverage_rasters.py",
    "check_exotic.py", "diagnose_water_bias.py", "dupe_check.py",
    "tune.py", "tune_bins.py", "bench_pipeline.py", "calibrate.py",
    "diagnose_training.py", "diagnose_wetland.py", "pretrain.py",
    "train.py", "check_raster.py", "sightings.py", "get_negatives.py",
    "ebird.py", "generate_road_distance.py", "check_road_dist.py",
    "download_rev.py",
]
# Stale copies CR-0007 guards (section 3): the guard is the module's first
# statement after its docstring, so running or importing the file stops
# before any import. They are not import-smoked.
P7_GUARDED = ["legacy/audit.py", "legacy/download.py", "legacy/download_more.py",
              # CR-0007 v9.2 (BUG-0048, PA-0026 sweep)
              "legacy/download_landfire.py", "legacy/download_landfire_2.py",
              "legacy/download_landfire_3.py"]
GUARD_TAG = "BUG-0031"

REGION_CONSTS = ["REGIONS", "STATE_FIPS", "STATE_NAMES", "TIGER_YEAR",
                 "COUNTY_POLYGONS_YEAR", "MIN_SPACING_M", "BLOCK_SIZE_M",
                 "BUFFER_M", "BOXES"]
ANALYZE_CONSTS = ["BACKGROUND_N", "REQUIRED_FEATURES", "COORD_ROUND_DECIMALS",
                  "KDE_MODE", "STRATIFY_BY", "MIN_STRATUM_FOR_KDE",
                  "KDE_BANDWIDTH_M", "RASTER_DIR"]
GROUSE_DATA_CONSTS = ["NODATA_SENTINELS", "PATH_TEMPLATES"]

ZONE_MID = "Moderate Density (10-90%)"
ZONE_COLD = "Coldest 10%"
ZONE_HOT = "Hotspot 10%"
KDE_RTOL = 1e-6


class Missing(Exception):
    """A constant or input the check needs does not exist."""


# ---------------------------------------------------------------------------
# constant sources
# ---------------------------------------------------------------------------
def literal_assignments(path):
    """{name: value} for every top-level `NAME = <literal>` in `path`."""
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    out = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            if isinstance(t, ast.Name):
                try:
                    out[t.id] = ast.literal_eval(value)
                except ValueError:
                    pass
    return out


class Consts:
    def __init__(self, root, assume=None):
        self.root = root
        self.assumed = dict(assume or {})
        self._src = {
            "regions": literal_assignments(os.path.join(root, "regions.py")),
            "analyze_grouse": literal_assignments(
                os.path.join(root, "analyze_grouse.py")),
            "grouse_data": literal_assignments(
                os.path.join(root, "grouse_data.py")),
        }

    def get(self, module, name):
        key = f"{module}.{name}"
        if key in self.assumed:
            return self.assumed[key]
        src = self._src[module]
        if name not in src:
            raise Missing(f"{module}.py defines no literal {name}")
        return src[name]

    def path(self, template, **kw):
        key = f"path.{template}"
        if key in self.assumed:
            p = self.assumed[key]
        else:
            tpl = self.get("grouse_data", "PATH_TEMPLATES")
            if template not in tpl:
                raise Missing(f"grouse_data.PATH_TEMPLATES has no '{template}'")
            p = tpl[template]
        return p.format(**kw)

    def regions(self):
        return tuple(self.get("regions", "REGIONS"))


# ---------------------------------------------------------------------------
# raw sightings, collapse, sampling (re-implementations; see CR-0007 P3)
# ---------------------------------------------------------------------------
FNAME_RE = re.compile(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$")


def load_raw(c, data_root):
    """All raw sightings in sorted-path order, as analyze_grouse loads them:
    first column containing 'lon'/'lat', state from the file stem, year from
    the file name, rows lacking a coordinate dropped, then the
    west-hemisphere sign flip."""
    tpl = c.path("sightings", state_lower="*", year="*")
    frames = []
    for f in sorted(glob.glob(os.path.join(data_root, tpl))):
        m = FNAME_RE.match(os.path.basename(f))
        if not m:
            continue
        df = pd.read_csv(f)
        lon = next((x for x in df.columns if "lon" in x.lower()), None)
        lat = next((x for x in df.columns if "lat" in x.lower()), None)
        if not (lon and lat):
            continue
        frames.append(pd.DataFrame({
            "longitude": df[lon].values, "latitude": df[lat].values,
            "state": m.group(1).upper(), "year": int(m.group(2))}))
    if not frames:
        raise Missing(f"no raw sighting files match {tpl}")
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["longitude"].notna() & raw["latitude"].notna()]
    raw = raw.reset_index(drop=True)
    if (raw["longitude"] > 0).mean() > 0.9:
        boxes = c.get("regions", "BOXES")
        hits = sum(int(in_box(-raw["longitude"], raw["latitude"], b).sum())
                   for b in boxes.values())
        if hits > 0:
            raw["longitude"] = -raw["longitude"]
    return raw


def in_box(lon, lat, box):
    a, b, cc, d = box
    return (lon >= a) & (lon <= cc) & (lat >= b) & (lat <= d)


def add_keys(df, decimals):
    df = df.copy()
    df["_klon"] = np.round(df["longitude"].to_numpy(dtype=float), decimals)
    df["_klat"] = np.round(df["latitude"].to_numpy(dtype=float), decimals)
    return df


def key_set(df):
    return set(zip(df["_klon"], df["_klat"]))


def collapse(df):
    """One row per key: the first row, in input order, of the key's most
    recent year (stable sort, then keep-first)."""
    order = np.argsort(-df["year"].to_numpy(), kind="stable")
    s = df.iloc[order]
    return s.drop_duplicates(["_klon", "_klat"], keep="first")


def available_years(c, data_root, region, feature):
    rdir = os.path.join(data_root, c.get("analyze_grouse", "RASTER_DIR"))
    pat = re.compile(rf"^{re.escape(region)}_(\d{{4}})_{re.escape(feature)}\.tif$")
    years = set()
    for p in glob.glob(os.path.join(rdir, f"{region}_*_{feature}.tif")):
        m = pat.match(os.path.basename(p))
        if m:
            years.add(int(m.group(1)))
    return sorted(years)


def pick_year(year, years):
    """Nearest vintage; on a tie the earlier one."""
    best = None
    for y in years:
        k = (abs(y - year), y)
        if best is None or k < best[0]:
            best = (k, y)
    return best[1]


def sample(c, tif, lons, lats):
    """Value at each point, NaN where the point is outside the raster's
    (inclusive) bounds, equals the file's nodata, or equals a
    grouse_data.NODATA_SENTINELS value."""
    import rasterio
    from pyproj import Transformer
    out = np.full(len(lons), np.nan)
    if not os.path.exists(tif):
        return out
    sentinels = c.get("grouse_data", "NODATA_SENTINELS")
    with rasterio.open(tif) as src:
        t = Transformer.from_crs(LONLAT_EPSG, src.crs, always_xy=True)
        xs, ys = t.transform(np.asarray(lons, float), np.asarray(lats, float))
        xs, ys = np.asarray(xs), np.asarray(ys)
        b = src.bounds
        ok = (xs >= b.left) & (xs <= b.right) & (ys >= b.bottom) & (ys <= b.top)
        idx = np.flatnonzero(ok)
        if len(idx):
            v = np.array([p[0] for p in src.sample(zip(xs[idx], ys[idx]))],
                         dtype=float)
            if src.nodata is not None:
                v[v == src.nodata] = np.nan
            for s in sentinels:
                v[v == s] = np.nan
            out[idx] = v
    return out


def extract(c, data_root, region, pts, features):
    """Sample `features` for each row at the vintage nearest its year."""
    rdir = os.path.join(data_root, c.get("analyze_grouse", "RASTER_DIR"))
    res = pd.DataFrame(index=pts.index)
    for feat in features:
        years = available_years(c, data_root, region, feat)
        if not years:
            raise Missing(f"no {region} rasters for '{feat}' in {rdir}")
        col = np.full(len(pts), np.nan)
        for yr in sorted(pts["year"].unique()):
            m = (pts["year"] == yr).to_numpy()
            tif = os.path.join(rdir, f"{region}_{pick_year(int(yr), years)}_{feat}.tif")
            col[m] = sample(c, tif, pts.loc[m, "longitude"].values,
                            pts.loc[m, "latitude"].values)
        res[feat] = col
    return res


def evt_phys_map(c, data_root):
    rdir = os.path.join(data_root, c.get("analyze_grouse", "RASTER_DIR"))
    files = sorted(glob.glob(os.path.join(rdir, "attribute_tables", "LF*_EVT.csv")))
    if not files:
        return None
    t = pd.read_csv(files[-1])
    t.columns = [x.upper().strip() for x in t.columns]
    return dict(zip(t["VALUE"].astype(int), t["EVT_PHYS"].astype(str)))


# ---------------------------------------------------------------------------
# shared context: everything a check reads, built lazily and cached
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, root, data_root, assume=None):
        self.c = Consts(root, assume)
        self.root = root
        self.data_root = data_root
        self._cache = {}

    def once(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def dec(self):
        return self.c.get("analyze_grouse", "COORD_ROUND_DECIMALS")

    def raw(self):
        return self.once("raw", lambda: add_keys(load_raw(self.c, self.data_root),
                                                 self.dec()))

    def csv(self, template, region):
        def load():
            p = os.path.join(self.data_root, self.c.path(template, region=region))
            if not os.path.exists(p):
                raise Missing(f"{p} does not exist")
            df = pd.read_csv(p)
            if {"longitude", "latitude"} <= set(df.columns):
                df = add_keys(df, self.dec())
            return df
        return self.once(("csv", template, region), load)

    def polygons(self):
        def load():
            import geopandas as gpd
            import shapely
            fips = self.c.get("regions", "STATE_FIPS")
            year = self.c.get("regions", "COUNTY_POLYGONS_YEAR")
            p = os.path.join(self.data_root, self.c.path("tiger_county", year=year))
            if not os.path.exists(p):
                raise Missing(f"{p} does not exist")
            codes = ",".join(f"'{v}'" for v in sorted(fips.values()))
            g = gpd.read_file(p, where=f"STATEFP IN ({codes})").to_crs(LONLAT_EPSG)
            out = {}
            for region, fp in fips.items():
                geom = shapely.union_all(g.loc[g["STATEFP"] == fp].geometry.values)
                shapely.prepare(geom)
                out[region] = geom
            return out
        return self.once("polygons", load)

    def polygon_state(self, lon, lat):
        """Region whose dissolved county polygon contains each point, or ''."""
        import shapely
        lon = np.asarray(lon, float)
        lat = np.asarray(lat, float)
        out = np.full(len(lon), "", dtype=object)
        for region, geom in self.polygons().items():
            inside = shapely.contains_xy(geom, lon, lat)
            clash = inside & (out != "")
            if clash.any():
                raise RuntimeError(f"{int(clash.sum())} points in two states' polygons")
            out[inside] = region
        return out

    def box_source(self, region):
        """S_R: the region's box-clipped raw records (any state), collapsed
        to one row per key, with every REQUIRED_FEATURES value present on
        the region's rasters. Also returns the collapsed box set before the
        nodata drop."""
        def build():
            raw = self.raw()
            box = self.c.get("regions", "BOXES")[region]
            inb = raw[in_box(raw["longitude"], raw["latitude"], box)]
            col = collapse(inb)
            req = list(self.c.get("analyze_grouse", "REQUIRED_FEATURES"))
            feats = req + (["evt"] if "evt" not in req else [])
            vals = extract(self.c, self.data_root, region, col, feats)
            col = col.join(vals)
            src = col.dropna(subset=req).copy()
            return col, src
        return self.once(("box_source", region), build)


# ---------------------------------------------------------------------------
# checks: each returns (ok, [detail lines])
# ---------------------------------------------------------------------------
def check_p1(x):
    lines, ok = [], True
    for r in x.c.regions():
        for tpl in ("evaluated", "nonveg_flagged"):
            df = x.csv(tpl, r)
            if "region" not in df.columns:
                ok = False
                lines.append(f"{tpl}_{r}: no 'region' column ({len(df):,} rows)")
                bad = int((df["state"] != r).sum())
            else:
                bad = int(((df["state"] != r) | (df["region"] != r)).sum())
            ok &= bad == 0
            lines.append(f"{tpl}_{r}: {bad:,} of {len(df):,} rows with state or region != {r}")
    return ok, lines


def check_p2(x):
    regs = x.c.regions()
    keys = {r: key_set(x.csv("evaluated", r)) for r in regs}
    lines, total = [], 0
    for i, a in enumerate(regs):
        for b in regs[i + 1:]:
            n = len(keys[a] & keys[b])
            total += n
            lines.append(f"{a} & {b}: {n:,} shared keys")
    return total == 0, lines


def check_p3(x):
    lines, ok = [], True
    raw = x.raw()
    multi = raw.groupby(["_klon", "_klat"])["state"].nunique()
    n_multi = int((multi > 1).sum())
    lines.append(f"keys filed under two states: {n_multi} (a representative "
                 f"could then be the foreign record; CR-0007 A5)")
    ok &= n_multi == 0
    req = list(x.c.get("analyze_grouse", "REQUIRED_FEATURES"))
    for r in x.c.regions():
        own = raw[raw["state"] == r]
        k_r = key_set(own)
        box = x.c.get("regions", "BOXES")[r]
        outside = key_set(own[~in_box(own["longitude"], own["latitude"], box)])
        col, src = x.box_source(r)
        e_r = key_set(src[src["state"] == r])
        ev = x.csv("evaluated", r)
        got = key_set(ev)
        dup = len(ev) - len(got)
        extra, missing = got - e_r, e_r - got
        dropped = k_r - e_r - outside
        # feature agreement on the rows both sides hold
        m = ev.merge(src[["_klon", "_klat"] + req], on=["_klon", "_klat"],
                     suffixes=("", "_chk"))
        mism = sum(int((~np.isclose(m[f], m[f + "_chk"], rtol=0, atol=0,
                                    equal_nan=True)).sum()) for f in req)
        r_ok = not (extra or missing or outside or dup or mism)
        ok &= r_ok
        lines.append(
            f"{r}: |K_R|={len(k_r):,} |E_R|={len(e_r):,} evaluated={len(got):,} "
            f"extra={len(extra):,} missing={len(missing):,} "
            f"own-state keys outside BOXES[{r}]={len(outside):,} "
            f"duplicate keys={dup:,} feature mismatches={mism:,} "
            f"(K_R keys with nodata, correctly absent: {len(dropped):,})")
    return ok, lines


def check_p4(x):
    raw = x.raw()
    regs = set(x.c.regions())
    bad_code = int((~raw["state"].isin(regs)).sum())
    poly = x.polygon_state(raw["longitude"], raw["latitude"])
    nowhere = int((poly == "").sum())
    wrong = int(((poly != "") & (poly != raw["state"].to_numpy())).sum())
    n = bad_code + nowhere + wrong
    return n == 0, [f"{n:,} of {len(raw):,} raw records violate the partition "
                    f"(state not in REGIONS {bad_code}, inside no state "
                    f"polygon {nowhere}, inside another state's polygon {wrong})"]


def check_p5(x):
    lines, ok = [], True
    bg_n = x.c.get("analyze_grouse", "BACKGROUND_N")
    for r in x.c.regions():
        ev = x.csv("evaluated", r)
        em = x.csv("envelope_metrics", r)
        hab = ev[~ev["nonveg_landcover"].astype(bool)]
        used_s = hab["envelope_id"].value_counts()
        # P5c: Sightings
        s_file = em.set_index("Envelope")["Sightings"]
        s_exp = used_s.reindex(s_file.index, fill_value=0)
        bad_s = int((s_file != s_exp).sum()) + len(set(used_s.index) - set(s_file.index))
        ok &= bad_s == 0
        lines.append(f"{r} P5c: {bad_s} envelopes whose Sightings != evaluated "
                     f"habitat value_counts ({len(s_file)} envelope rows)")
        dup = int(em["Envelope"].duplicated().sum())
        ok &= dup == 0
        if dup:
            lines.append(f"{r} P5d: {dup} duplicate Envelope rows")
        try:
            av = x.csv("availability_sample", r)
        except Missing as e:
            ok = False
            lines.append(f"{r} P5a/P5b: {e}")
            continue
        need = {"longitude", "latitude", "used", "envelope_id"}
        if not need <= set(av.columns):
            ok = False
            lines.append(f"{r} P5a: columns {sorted(need - set(av.columns))} missing")
            continue
        used = av["used"].astype(bool)
        inbox = in_box(av["longitude"], av["latitude"],
                       x.c.get("regions", "BOXES")[r])
        inpoly = x.polygon_state(av["longitude"], av["latitude"]) == r
        id_ok = int((used & av["envelope_id"].isna()).sum()
                    + (~used & av["envelope_id"].notna()).sum())
        a_ok = len(av) == bg_n and inbox.all() and inpoly.all() and id_ok == 0
        ok &= bool(a_ok)
        lines.append(f"{r} P5a: rows {len(av):,} (BACKGROUND_N {bg_n:,}); outside "
                     f"box {int((~inbox).sum())}; outside {r} polygon "
                     f"{int((~inpoly).sum())}; used/envelope_id inconsistent {id_ok}")
        if "Avail_N" not in em.columns:
            ok = False
            lines.append(f"{r} P5b: envelope_metrics has no Avail_N")
            continue
        vc = av.loc[used, "envelope_id"].value_counts()
        a_file = em.set_index("Envelope")["Avail_N"]
        a_exp = vc.reindex(a_file.index, fill_value=0)
        bad_a = int((a_file != a_exp).sum()) + len(set(vc.index) - set(a_file.index))
        tot = int(a_file.sum()) == int(used.sum())
        extra = set(a_file.index) - set(vc.index) - set(used_s.index)
        b_ok = bad_a == 0 and tot and not extra
        ok &= b_ok
        lines.append(f"{r} P5b: sum(Avail_N) {int(a_file.sum()):,} vs used rows "
                     f"{int(used.sum()):,}; {bad_a} envelopes whose Avail_N != used "
                     f"value_counts; {len(extra)} envelope rows in neither set")
    return ok, lines


def kde_density(src_xy, q_xy, h, chunk=2000):
    """Gaussian KDE, 2-D, normalised (matches sklearn's 'gaussian' kernel)."""
    norm = 1.0 / (len(src_xy) * 2.0 * np.pi * h * h)
    out = np.empty(len(q_xy))
    for i in range(0, len(q_xy), chunk):
        q = q_xy[i:i + chunk]
        d2 = ((q[:, None, :] - src_xy[None, :, :]) ** 2).sum(-1)
        out[i:i + chunk] = np.exp(-d2 / (2.0 * h * h)).sum(1) * norm
    return out


def zones(d, p10, p90):
    z = np.full(len(d), ZONE_MID, dtype=object)
    z[d <= p10] = ZONE_COLD
    z[d >= p90] = ZONE_HOT
    return z


def check_p8(x):
    from pyproj import Transformer
    mode = x.c.get("analyze_grouse", "KDE_MODE")
    if mode not in ("stratified", "spatial"):
        return False, [f"KDE_MODE '{mode}' is not reproduced by this check"]
    by = x.c.get("analyze_grouse", "STRATIFY_BY")
    min_n = x.c.get("analyze_grouse", "MIN_STRATUM_FOR_KDE")
    bw = x.c.get("analyze_grouse", "KDE_BANDWIDTH_M")
    phys = evt_phys_map(x.c, x.data_root)
    lines, ok = [], True
    for r in x.c.regions():
        if r not in bw:
            ok = False
            lines.append(f"{r}: no KDE_BANDWIDTH_M entry")
            continue
        h = float(bw[r])
        ev = x.csv("evaluated", r)
        xcol = [cname for cname in ev.columns if re.fullmatch(r"x_\d+", cname)]
        if len(xcol) != 1:
            ok = False
            lines.append(f"{r}: cannot find one x_<epsg> column")
            continue
        epsg = int(xcol[0][2:])
        _, src = x.box_source(r)
        src = src.copy()
        if phys is None:
            src["evt_phys"] = "Unmapped"
        else:
            src["evt_phys"] = src["evt"].astype(int).map(phys).fillna("Unmapped")
        t = Transformer.from_crs(LONLAT_EPSG, epsg, always_xy=True)
        sx, sy = t.transform(src["longitude"].values, src["latitude"].values)
        src["_x"], src["_y"] = sx, sy
        src["_d"] = np.nan
        src["_z"] = ZONE_MID
        src["_p10"] = np.nan
        src["_p90"] = np.nan
        groups = src.groupby(by) if mode == "stratified" else [("all", src)]
        for _, g in groups:
            if mode == "stratified" and len(g) < min_n:
                continue
            xy = g[["_x", "_y"]].to_numpy()
            d = kde_density(xy, xy, h)
            p10, p90 = np.percentile(d, 10), np.percentile(d, 90)
            src.loc[g.index, "_d"] = d
            src.loc[g.index, "_z"] = zones(d, p10, p90)
            src.loc[g.index, "_p10"] = p10
            src.loc[g.index, "_p90"] = p90
        m = ev.merge(src[["_klon", "_klat", "evt_phys", "_d", "_z", "_p10", "_p90"]],
                     on=["_klon", "_klat"], how="left", suffixes=("", "_chk"))
        unmatched = int(m["_z"].isna().sum())
        phys_bad = int((m[by] != m[by + "_chk"]).sum()) if by + "_chk" in m else 0
        dens_bad = int((~np.isclose(m["spatial_density"], m["_d"], rtol=KDE_RTOL,
                                    atol=0, equal_nan=True)).sum())
        near = (np.isclose(m["_d"], m["_p10"], rtol=KDE_RTOL, atol=0)
                | np.isclose(m["_d"], m["_p90"], rtol=KDE_RTOL, atol=0))
        zone_bad = int(((m["spatial_zone"] != m["_z"]) & ~near).sum())
        r_ok = unmatched == 0 and phys_bad == 0 and dens_bad == 0 and zone_bad == 0
        ok &= r_ok
        lines.append(f"{r}: KDE source {len(src):,} rows (own-state "
                     f"{int((src['state'] == r).sum()):,}); evaluated rows not in "
                     f"source {unmatched}; {by} mismatches {phys_bad}; density "
                     f"mismatches {dens_bad}; zone mismatches {zone_bad}")
    return ok, lines


# ---------------------------------------------------------------------------
# P6: shared constants (scanner used by tests/test_shared_constants.py)
# ---------------------------------------------------------------------------
P6_NAMES = ("REGIONS", "STATE_FIPS", "STATE_NAMES", "TIGER_YEAR",
            "COUNTY_POLYGONS_YEAR", "MIN_SPACING_M", "BLOCK_SIZE_M",
            "BUFFER_M", "BOXES",
            # CR-0012 section 1 (PA-0025: names grow with each constant)
            "BLOCK_ORIGIN_5070", "VAL_FRACTION", "SPLIT_SEED", "WINDOW_PX")

# path -> reason. Each entry is named in CR-0007 "P6"; nothing else is exempt.
P6_EXEMPT = {
    "regions.py": "the single definition",
    "clean.py": "stale copy; runtime guard is CR-0012 section 6",
    "legacy/gen_negs.py": "stale copy; runtime guard is CR-0012 section 6",
    "legacy/audit.py": "stale copy; runtime guard is CR-0007 section 3",
    "legacy/download.py": "stale copy; runtime guard is CR-0007 section 3",
    "legacy/download_more.py": "stale copy; runtime guard is CR-0007 section 3",
}


def p6_scanned_files(root):
    """git-tracked *.py, minus inv_*/res_* scratch, minus tests/, minus
    docs/quality/evidence/ (frozen review evidence, never run as pipeline
    code - CR-0007 v9.1)."""
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    files = []
    for p in out.split():
        base = os.path.basename(p)
        if (base.startswith(("inv_", "res_")) or p.startswith("tests/")
                or p.startswith("docs/quality/evidence/")):
            continue
        files.append(p)
    return sorted(files)


def _has_constant(node):
    return any(isinstance(n, ast.Constant) for n in ast.walk(node))


def _str_elts(node):
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        if node.elts and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                             for e in node.elts):
            return [e.value for e in node.elts]
    return None


def scan_source(text, path, region_codes):
    """Violations in one file: (path, line, what)."""
    names = set(P6_NAMES) | {n + "_DEFAULT" for n in P6_NAMES}
    codes = {s.upper() for s in region_codes}
    tree = ast.parse(text, filename=path)
    out, seen = [], set()

    def add(node, what):
        k = (node.lineno, what)
        if k not in seen:
            seen.add(k)
            out.append((path, node.lineno, what))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for tn in ast.walk(t):
                    nm = tn.id if isinstance(tn, ast.Name) else (
                        tn.attr if isinstance(tn, ast.Attribute) else None)
                    if nm in names and node.value is not None and _has_constant(node.value):
                        add(node, f"literal assigned to {nm}")
        elts = _str_elts(node)
        if elts is not None and len(elts) == len(codes) \
                and {e.upper() for e in elts} == codes:
            add(node, "region-code sequence literal")
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str)
                for k in node.keys) and all(
                isinstance(v, ast.Constant) and isinstance(v.value, str)
                for v in node.values):
            ks = {k.value.upper() for k in node.keys}
            vs = {v.value.upper() for v in node.values}
            if len(node.keys) == len(codes) and (ks == codes or vs == codes):
                add(node, "region-keyed or region-valued dict literal")
    return out


def scan_repository(root, region_codes, files=None, exempt=None):
    exempt = P6_EXEMPT if exempt is None else exempt
    files = p6_scanned_files(root) if files is None else files
    out = []
    for p in files:
        if p in exempt:
            continue
        with open(os.path.join(root, p)) as f:
            out += scan_source(f.read(), p, region_codes)
    return out


def load_p6_expected(root):
    path = os.path.join(root, "tests", "test_shared_constants.py")
    spec = importlib.util.spec_from_file_location("_p6_pins", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.EXPECTED_REGIONS, mod.EXPECTED_PATH_TEMPLATES


def p6_problems(root):
    """Every P6 failure: pinned values, then scan violations."""
    exp_r, exp_p = load_p6_expected(root)
    got_r = literal_assignments(os.path.join(root, "regions.py"))
    got_p = literal_assignments(os.path.join(root, "grouse_data.py")).get(
        "PATH_TEMPLATES", {})
    probs = []
    for k, v in exp_r.items():
        if k not in got_r:
            probs.append(f"regions.{k} not defined as a literal")
        elif got_r[k] != v:
            probs.append(f"regions.{k} = {got_r[k]!r}, pinned {v!r}")
    for k, v in exp_p.items():
        if got_p.get(k) != v:
            probs.append(f"grouse_data.PATH_TEMPLATES['{k}'] = {got_p.get(k)!r}, "
                         f"pinned {v!r}")
    codes = exp_r["REGIONS"]
    by_line = {}
    for p, line, what in scan_repository(root, codes):
        by_line.setdefault((p, line), []).append(what)
    for (p, line), whats in sorted(by_line.items()):
        probs.append(f"{p}:{line}: {'; '.join(whats)}")
    return probs


def check_p6(x):
    probs = p6_problems(x.root)
    return not probs, [f"{len(probs)} problem(s)"] + probs


def guard_first(path):
    """True iff the module's first statement after an optional docstring is
    `raise SystemExit(...)`."""
    with open(path) as f:
        body = ast.parse(f.read(), filename=path).body
    if body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], "value", None), ast.Constant) and isinstance(
            body[0].value.value, str):
        body = body[1:]
    if not body or not isinstance(body[0], ast.Raise):
        return False
    exc = body[0].exc
    fn = exc.func if isinstance(exc, ast.Call) else exc
    return isinstance(fn, ast.Name) and fn.id == "SystemExit"


DOCS_PREFIX = "docs"
_PATH_LOADERS = {"spec_from_file_location", "run_path", "SourceFileLoader"}


def docs_import_problems(root, files=None):
    """CR-0007 v9.2: P6 skips docs/quality/evidence/, which is safe only if
    no scanned module runs code from docs/. Report every import of a
    `docs...` module, every sys.path.insert/append, and every path-based
    loader (importlib spec_from_file_location, runpy.run_path,
    SourceFileLoader) whose argument mentions docs/."""
    files = p6_scanned_files(root) if files is None else files
    out = []
    for p in files:
        with open(os.path.join(root, p)) as f:
            tree = ast.parse(f.read(), filename=p)
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                mods = [n.module]
            for m in mods:
                if m == DOCS_PREFIX or m.startswith(DOCS_PREFIX + "."):
                    out.append(f"{p}:{n.lineno}: imports {m}")
            if isinstance(n, ast.Call):
                fn = n.func
                name = fn.attr if isinstance(fn, ast.Attribute) else (
                    fn.id if isinstance(fn, ast.Name) else "")
                is_syspath = (isinstance(fn, ast.Attribute)
                              and fn.attr in ("insert", "append", "extend")
                              and ast.unparse(fn.value) == "sys.path")
                if is_syspath or name in _PATH_LOADERS:
                    args = " ".join(ast.unparse(a) for a in n.args)
                    if re.search(rf"\b{DOCS_PREFIX}\b", args):
                        out.append(f"{p}:{n.lineno}: {ast.unparse(fn)}({args})")
    return out


def check_p7(x):
    lines, ok = [], True
    docs = docs_import_problems(x.root)
    if docs:
        ok = False
        lines += [f"loads code from docs/: {d}" for d in docs]
    code = ("import importlib.util, sys; sys.path.insert(0, '.'); "
            "s = importlib.util.spec_from_file_location('_p7', sys.argv[1]); "
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)")
    n_imp = 0
    for p in P7_IMPORT:
        r = subprocess.run([sys.executable, "-c", code, p], cwd=x.root,
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            ok = False
            last = (r.stderr.strip().splitlines() or ["?"])[-1]
            lines.append(f"{p}: import FAILED: {last}")
        else:
            n_imp += 1
    for p in P7_GUARDED:
        first = guard_first(os.path.join(x.root, p))
        fired = False
        if first:   # never execute an unguarded copy: it would run for real
            r = subprocess.run([sys.executable, p], cwd=x.root,
                               capture_output=True, text=True, timeout=60)
            fired = r.returncode != 0 and GUARD_TAG in r.stderr
        if not (first and fired):
            ok = False
            lines.append(f"{p}: guard first statement {first}; run exits "
                         f"non-zero naming {GUARD_TAG} {fired}")
    lines.insert(0, f"{n_imp} of {len(P7_IMPORT)} modules import; "
                    f"{len(P7_GUARDED)} guarded copies checked; "
                    f"{len(docs)} scanned modules load code from docs/")
    return ok, lines


CHECKS = {"P1": check_p1, "P2": check_p2, "P3": check_p3, "P4": check_p4,
          "P5": check_p5, "P6": check_p6, "P7": check_p7, "P8": check_p8}


def run(root, data_root, only=None, assume=None, out=print):
    x = Ctx(root, data_root, assume)
    results = {}
    for cid, fn in CHECKS.items():
        if only and cid not in only:
            continue
        try:
            ok, lines = fn(x)
        except Missing as e:
            ok, lines = False, [f"cannot evaluate: {e}"]
        results[cid] = ok
        out(f"{cid}: {'PASS' if ok else 'FAIL'}")
        for ln in lines:
            out(f"    {ln}")
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=HERE)
    ap.add_argument("--data-root", default=None,
                    help="directory holding data/ (default: --root)")
    ap.add_argument("--only", nargs="+", choices=list(CHECKS))
    ap.add_argument("--assume", action="append", default=[],
                    metavar="MODULE.NAME=JSON",
                    help="e.g. regions.REGIONS='[\"ME\",\"NH\",\"VT\"]' or "
                         "path.tiger_county='data/roads/tl_{year}_us_county.zip'")
    a = ap.parse_args(argv)
    assume = {}
    for s in a.assume:
        k, v = s.split("=", 1)
        try:
            assume[k] = json.loads(v)
        except json.JSONDecodeError:
            assume[k] = v
    if "regions.BOXES" in assume:
        assume["regions.BOXES"] = {k: tuple(v) for k, v in assume["regions.BOXES"].items()}
    res = run(a.root, a.data_root or a.root, a.only, assume)
    acceptance = not a.only and not assume
    if not acceptance:
        print("NOT AN ACCEPTANCE RUN (--only or --assume used)")
    if not all(res.values()):
        return 1
    return 0 if acceptance else 2


if __name__ == "__main__":
    sys.exit(main())
