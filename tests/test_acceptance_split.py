"""
tests/test_acceptance_split.py - CR-0013 deliverable 4.

A synthetic three-region fixture (rasters, county polygons, sightings,
envelope metrics, GBIF candidates, crosswalk, regions.py) is built once.
`acceptance_split.Replay` emits the reference artifacts into it (the
`--emit-reference` path), which must pass every GATE unmutated. Every row
of CR-0013 section "Attacks" is then applied to a clone of that output,
either as a wrong pipeline (a Replay subclass that emits its own,
internally consistent artifacts and manifest) or as a file mutation, and
must fail the gate(s) the row names. Unit tests cover the normative
re-implementations; the shuffle test checks order-freedom.

Run: python -m unittest tests.test_acceptance_split -v
"""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import acceptance_split as A  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_CONFIG = os.path.join(REPO, "docs", "quality", "acceptance_split.json")

LAT = (44.0, 44.2)
REG_LON = {"VT": (-72.6, -72.4), "NH": (-72.4, -72.2), "ME": (-72.2, -72.0)}
FIPS = {"ME": "23", "NH": "33", "VT": "50"}
MARGIN = 0.03
ME_EAST_MARGIN = 0.004            # tight east edge on ME: windowless records
VT_CRS = ("+proj=aea +lat_1=43 +lat_2=45 +lat_0=44 +lon_0=-72.5 +x_0=0 +y_0=0 "
          "+datum=NAD83 +units=m +no_defs")
EVT_CODES = {7001: "Conifer", 7002: "Hardwood", 7003: "Conifer-Hardwood",
             7004: "Shrubland", 7005: "Open Water", 7006: "Developed-Low Intensity",
             7007: "Agriculture"}
EVT_P = [(7001, .25), (7002, .25), (7003, .2), (7004, .1), (7005, .07), (7006, .06),
         (7007, .04), (7999, .03)]
SPECIES = ["Blue Jay", "Black-capped Chickadee", "American Robin", "Common Raven",
           "Red-eyed Vireo", "Hermit Thrush"]
# Reserved spots: an NH-filed candidate inside ME, kept clear of others.
NH_IN_ME = (-72.198, 44.117)
OUTSIDE = {"ME": (-72.1, 44.205), "VT": (-72.605, 44.1)}

S_COLS = ["longitude", "latitude", "state", "year", "n_visits", "first_year", "last_year",
          "x_5070", "y_5070", "evt", "evh", "evc", "sclass", "fdist", "ch", "cc", "evt_phys",
          "evt_group", "nonveg_landcover", "spatial_density", "spatial_zone", "region",
          "env_zone", "envelope_id"]
G_COLS = ["common_name", "scientific_name", "longitude", "latitude", "obs_date", "year",
          "month", "state", "gbif_id", "how_many", "coord_uncertainty_m"]
RASTER_YEARS = {"evt": [2022, 2023], "evh": [2022, 2023], "sclass": [2021, 2022, 2023]}
with open(PROD_CONFIG, encoding="utf-8") as _f:
    YEAR_MIN = json.load(_f)["constants"]["YEAR_MIN"]      # CR-0019
# CR-0019 (review A4): fixture years are set deterministically. Both classes
# cycle over the same years >= YEAR_MIN, so the correct tree's pooled P and N
# year sets are equal by construction (asserted in TestYearFloorUnits); a
# few sightings and candidates carry LOW_YEAR (< YEAR_MIN) for the attacks.
FIX_YEARS = [YEAR_MIN + k for k in range(4)]
LOW_YEAR = YEAR_MIN - 1
REGIONS_PY = '''"""fixture regions.py (CR-0007/CR-0012/CR-0019 constants)."""
REGIONS = ("ME", "NH", "VT")
STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}
MIN_SPACING_M = 30
BLOCK_SIZE_M = 3000
BUFFER_M = 300
COUNTY_POLYGONS_YEAR = 2023
BLOCK_ORIGIN_5070 = (0.0, 0.0)
VAL_FRACTION = 0.2
SPLIT_SEED = 42
WINDOW_PX = 64
''' + f"YEAR_MIN = {YEAR_MIN}\n"


def _seed(*parts):
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:4], "big")


def _dist_m(lon1, lat1, lon2, lat2):
    x1, y1 = A.to_5070([lon1], [lat1])
    x2, y2 = A.to_5070([lon2], [lat2])
    return float(math.hypot(x1[0] - x2[0], y1[0] - y2[0]))


# --------------------------------------------------------------------------
# Fixture builder
# --------------------------------------------------------------------------
def _write_rasters(root):
    import rasterio
    from pyproj import Transformer
    from rasterio.transform import from_origin
    feats = ["evt", "evh", "evc", "sclass", "fdist", "ch", "cc", "tcc", "nlcd", "road_dist",
             "tsd", "balive", "tpa_live", "qmd", "carbon_dwn"]
    os.makedirs(os.path.join(root, "data", "landfire"), exist_ok=True)
    for R, (lo0, lo1) in REG_LON.items():
        crs = VT_CRS if R == "VT" else "EPSG:5070"
        t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        east = ME_EAST_MARGIN if R == "ME" else MARGIN
        lons = np.concatenate([np.linspace(lo0 - MARGIN, lo1 + east, 40)] * 2 +
                              [np.full(40, lo0 - MARGIN), np.full(40, lo1 + east)])
        lats = np.concatenate([np.full(40, LAT[0] - MARGIN), np.full(40, LAT[1] + MARGIN),
                               np.linspace(LAT[0] - MARGIN, LAT[1] + MARGIN, 40)] * 1 +
                              [np.linspace(LAT[0] - MARGIN, LAT[1] + MARGIN, 40)])
        xs, ys = t.transform(lons, lats)
        minx, maxx = math.floor(min(xs)), math.ceil(max(xs))
        miny, maxy = math.floor(min(ys)), math.ceil(max(ys))
        if R == "ME":
            # tight east edge: the edge itself at lon1 + ME_EAST_MARGIN (mid-latitude)
            ex, _ = t.transform([lo1 + east], [sum(LAT) / 2])
            maxx = math.ceil(ex[0])
        w = int(math.ceil((maxx - minx) / 30))
        h = int(math.ceil((maxy - miny) / 30))
        tr = from_origin(minx, maxy, 30, 30)
        rng = np.random.default_rng(_seed("patch", R))

        def patches(size, choices, probs=None):
            small = rng.choice(choices, size=(h // size + 1, w // size + 1), p=probs)
            return np.repeat(np.repeat(small, size, 0), size, 1)[:h, :w]

        evt = patches(25, [c for c, _ in EVT_P], [p for _, p in EVT_P]).astype(np.int16)
        scl = patches(30, [1, 2, 3, 4, 5]).astype(np.int16)
        scl[evt == 7005] = 111
        dev = (evt == 7006) & (patches(10, [0, 1], [0.7, 0.3]) == 1)
        scl[dev] = 120
        scl[patches(15, [0, 1], [0.97, 0.03]) == 1] = 132
        evh = patches(20, np.arange(101, 126)).astype(np.int16)
        evh[patches(12, [0, 1], [0.95, 0.05]) == 1] = -9999
        base = {"evt": evt, "sclass": scl, "evh": evh}
        for f in feats:
            years = RASTER_YEARS.get(f, [2020])
            for yr in years:
                if f in base:
                    arr = base[f].copy()
                    if yr == 2023 and f == "evh":
                        arr[arr > 0] = np.minimum(arr[arr > 0] + 1, 125)
                    if f == "sclass" and yr == 2021:
                        arr[:] = -9999           # empty vintage: fails validation
                else:
                    arr = patches(8, np.arange(0, 1000)).astype(np.int16)
                path = os.path.join(root, "data", "landfire", f"{R}_{yr}_{f}.tif")
                with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=1,
                                   dtype="int16", crs=crs, transform=tr, nodata=-9999,
                                   compress="deflate", tiled=True) as dst:
                    dst.write(arr, 1)


def _write_counties(root):
    import geopandas as gpd
    from shapely.geometry import box
    rows = []
    for R, (lo0, lo1) in REG_LON.items():
        mid = (LAT[0] + LAT[1]) / 2
        rows.append({"STATEFP": FIPS[R], "COUNTYFP": "001", "geometry": box(lo0, LAT[0], lo1, mid)})
        rows.append({"STATEFP": FIPS[R], "COUNTYFP": "003", "geometry": box(lo0, mid, lo1, LAT[1])})
    rows.append({"STATEFP": "36", "COUNTYFP": "001", "geometry": box(-72.8, LAT[0], -72.6, LAT[1])})
    g = gpd.GeoDataFrame(rows, crs="EPSG:4269")
    tmp = tempfile.mkdtemp()
    g.to_file(os.path.join(tmp, "tl_2023_us_county.shp"), engine="pyogrio")
    os.makedirs(os.path.join(root, "data", "roads"), exist_ok=True)
    zp = os.path.join(root, "data", "roads", "tl_2023_us_county.zip")
    with zipfile.ZipFile(zp, "w") as z:
        for fn in sorted(os.listdir(tmp)):
            z.write(os.path.join(tmp, fn), fn)
    shutil.rmtree(tmp)
    return zp


def _write_crosswalks(root):
    d = os.path.join(root, "data", "landfire", "attribute_tables")
    os.makedirs(d, exist_ok=True)
    rows = [{"VALUE": -9999, "EVT_NAME": "Fill-NoData", "EVT_PHYS": "Fill-NoData",
             "EVT_GP_N": "Fill-NoData"}]
    for v, p in EVT_CODES.items():
        rows.append({"VALUE": v, "EVT_NAME": f"name {v}", "EVT_PHYS": p, "EVT_GP_N": f"group {p}"})
    pd.DataFrame(rows).to_csv(os.path.join(d, "LF2025_EVT.csv"), index=False)
    old = pd.DataFrame(rows)
    old["EVT_PHYS"] = "Old"
    old.to_csv(os.path.join(d, "LF2024_EVT.csv"), index=False)
    return os.path.join(d, "LF2025_EVT.csv")


def _uniform(rng, R, n, pad=0.002):
    lo0, lo1 = REG_LON[R]
    return rng.uniform(lo0 + pad, lo1 - pad, n), rng.uniform(LAT[0] + pad, LAT[1] - pad, n)


def _clear_of(lons, lats, spots, radius_deg):
    ok = np.ones(len(lons), bool)
    for (a, b) in spots:
        ok &= np.hypot((lons - a) * 0.72, lats - b) > radius_deg
    return ok


def _thin_key(lon, lat, seed=42):
    """The seeded thin order key (config hash_spec), computed here with
    hashlib directly, independently of acceptance_split."""
    return int.from_bytes(hashlib.blake2b(f"{seed}:{lon:.6f},{lat:.6f}".encode(),
                                          digest_size=8).digest(), "big")


def _sighting_years(lon, lat):
    """CR-0019 fixture years: FIX_YEARS by position; LOW_YEAR on (i) the
    member of each near pair (i, 110 + i) that is first in thin order and
    (ii) some isolated rows (10, 13, 16, 19: the 300 m buffer candidates
    are built around rows 0-19; and every row 25, 35, ..., 105)."""
    n = len(lon)
    year = np.array([FIX_YEARS[i % len(FIX_YEARS)] for i in range(n)])
    low = [10, 13, 16, 19] + list(range(25, 110, 10))
    for i in range(8):
        j = 110 + i
        low.append(i if _thin_key(lon[i], lat[i]) < _thin_key(lon[j], lat[j]) else j)
    year[low] = LOW_YEAR
    return year


def _write_sightings(root):
    out = {}
    spots = [NH_IN_ME] + list(OUTSIDE.values())
    for R in REG_LON:
        rng = np.random.default_rng(_seed("S", R))
        lon, lat = _uniform(rng, R, 150)
        keep = _clear_of(lon, lat, spots, 0.008)
        lon, lat = list(lon[keep][:110]), list(lat[keep][:110])
        for i in range(8):                               # near pairs (< 30 m)
            lon.append(lon[i] + 0.00012)
            lat.append(lat[i] + 0.00005)
        if R == "ME":                                    # windowless (east edge)
            for i in range(4):
                lon.append(-72.0035)
                lat.append(44.03 + 0.03 * i)
        # cross-border pairs at the NH|ME (-72.2) and VT|NH (-72.4) borders
        for border, (w, e) in ((-72.2, ("NH", "ME")), (-72.4, ("VT", "NH"))):
            for j in range(3):
                la = (44.04, 44.09, 44.16)[j]
                if R == w:
                    lon.append(border - 0.0001)
                    lat.append(la)
                if R == e:
                    lon.append(border + 0.0001)
                    lat.append(la)
        n = len(lon)
        lon, lat = np.array(lon), np.array(lat)
        x, y = A.to_5070(lon, lat)
        evt = rng.choice([7001, 7002, 7003, 7004], n)
        nonveg = rng.random(n) < 0.1
        nonveg[-6:] = False                              # border pairs are habitat
        nonveg[110:118] = False
        rng.integers(2019, 2024, n)                      # consumed: keeps the other columns' draws
        year = _sighting_years(lon, lat)                 # CR-0019: deterministic
        df = pd.DataFrame({
            "longitude": lon, "latitude": lat, "state": R, "year": year, "n_visits": 1,
            "first_year": year, "last_year": year, "x_5070": x, "y_5070": y,
            "evt": evt, "evh": rng.integers(101, 126, n).astype(float),
            "evc": rng.integers(110, 190, n).astype(float),
            "sclass": rng.integers(1, 6, n).astype(float),
            "fdist": -1.0, "ch": rng.integers(0, 300, n).astype(float),
            "cc": rng.integers(0, 100, n).astype(float),
            "evt_phys": [EVT_CODES[int(v)] for v in evt], "evt_group": "grp",
            "nonveg_landcover": nonveg, "spatial_density": rng.random(n),
            "spatial_zone": "Moderate Density (10-90%)", "region": R,
            "env_zone": "Proportional Envelope", "envelope_id": "EVT_PHYS:Conifer|SCLASS:1|EVH:Q1"})
        df = df[S_COLS]
        df.to_csv(os.path.join(root, "data", "pipeline", f"evaluated_sightings_{R}.csv"), index=False)
        out[R] = df
    return out


def _write_metrics(root):
    for R in REG_LON:
        rng = np.random.default_rng(_seed("M", R))
        rows = []
        for p in ["Conifer", "Hardwood", "Conifer-Hardwood", "Shrubland"]:
            for sc in range(1, 6):
                for q in ("Q1", "Q2"):
                    if rng.random() < 0.1:
                        continue
                    ratio = float(np.exp(rng.normal(0, 1.2)))
                    if rng.random() < 0.05:
                        ratio = float("nan")
                    cls = rng.choice(["Selected", "Avoided", "Proportional",
                                      "Landscape-Rare (availability < 15)"])
                    rows.append({"Envelope": f"EVT_PHYS:{p}|SCLASS:{sc}|EVH:{q}", "Sightings": 5,
                                 "Avail_N": 20, "Used_Pct": 1.0, "Avail_Pct": 1.0,
                                 "Selection_Ratio": ratio, "Classification": cls})
        pd.DataFrame(rows).to_csv(os.path.join(root, "data", "pipeline",
                                               f"envelope_metrics_{R}.csv"), index=False)


def _write_candidates(root, S):
    ids = iter(np.random.default_rng(7).permutation(np.arange(100000, 110000)).tolist())
    spots = [NH_IN_ME] + list(OUTSIDE.values())
    for R in REG_LON:
        rng = np.random.default_rng(_seed("G", R))
        lon, lat = _uniform(rng, R, 700, pad=0.001)
        keep = _clear_of(lon, lat, spots, 0.001)
        lon, lat = list(lon[keep][:650]), list(lat[keep][:650])
        s = S[R]
        for i in range(20):                              # inside the 300 m buffer
            ang = rng.uniform(0, 2 * np.pi)
            dist = rng.uniform(100, 250)
            lon.append(s["longitude"].iloc[i] + dist * np.cos(ang) / 80000)
            lat.append(s["latitude"].iloc[i] + dist * np.sin(ang) / 111000)
        for i in range(12):                              # near pairs
            lon.append(lon[40 + i] + 0.0001)
            lat.append(lat[40 + i] + 0.00004)
        if R in OUTSIDE:
            lon.append(OUTSIDE[R][0])
            lat.append(OUTSIDE[R][1])
        if R == "NH":
            lon.append(NH_IN_ME[0])
            lat.append(NH_IN_ME[1])
        n = len(lon)
        rng.integers(2019, 2024, n)                      # consumed: keeps the other columns' draws
        yr = np.array([FIX_YEARS[i % len(FIX_YEARS)] for i in range(n)])     # CR-0019
        yr[[i for i in range(min(n, 650)) if i % 13 == 6]] = LOW_YEAR       # pool step 1 drops these
        unc = rng.choice([10.0, 50.0, 250.0, np.nan], n)
        unc[rng.random(n) < 0.04] = 5000.0
        if R == "NH":
            unc[-1] = 10.0
        if R in OUTSIDE:
            unc[-1 - (R == "NH")] = 10.0
        sp = rng.choice(SPECIES, n)
        df = pd.DataFrame({"common_name": sp, "scientific_name": [f"sci {v}" for v in sp],
                           "longitude": lon, "latitude": lat,
                           "obs_date": [f"{y}-05-01" for y in yr], "year": yr, "month": 5,
                           "state": R, "gbif_id": [next(ids) for _ in range(n)],
                           "how_many": rng.choice([1.0, 2.0, np.nan], n),
                           "coord_uncertainty_m": unc})
        if R == "VT":                                    # CR-0017 attack rows (section 3)
            pair = _edge_band_pair(S, df)
            west = _west_edge_rows(S, df)
            pts = pair + west
            df = pd.concat([df, pd.DataFrame({
                "common_name": ["Edge Pair"] * len(pair) + ["West Edge"] * len(west),
                "scientific_name": "sci edge",
                "longitude": [a for a, _ in pts], "latitude": [b for _, b in pts],
                "obs_date": "2022-05-01", "year": 2022, "month": 5, "state": "VT",
                "gbif_id": list(range(200001, 200001 + len(pts))), "how_many": 1.0,
                "coord_uncertainty_m": 10.0})], ignore_index=True)
        # exact-key duplicates later in file order, some with SMALLER gbif_id
        dup = df.iloc[100:140].copy()
        dup["gbif_id"] = [next(ids) - (50000 if k % 2 else 0) for k in range(len(dup))]
        dup["year"] = [FIX_YEARS[k % len(FIX_YEARS)] for k in range(len(dup))]   # CR-0019
        dup["common_name"] = "Duplicate Pin"
        df = pd.concat([df, dup], ignore_index=True)[G_COLS]
        df.to_csv(os.path.join(root, "data", "negatives", f"gbif_negatives_{R}.csv"), index=False)


def fixture_domain_5070(dissolve=True):
    """The fixture's acquisition domain (ME, NH, VT county boxes; not the
    non-domain county 36) in EPSG:5070, built with shapely/pyproj directly,
    independently of acceptance_split's domain code."""
    from pyproj import Transformer
    from shapely.geometry import box
    from shapely.ops import transform, unary_union
    t = Transformer.from_crs("EPSG:4269", "EPSG:5070", always_xy=True)
    mid = (LAT[0] + LAT[1]) / 2
    states = []
    for R, (lo0, lo1) in REG_LON.items():
        polys = [transform(t.transform, box(lo0, LAT[0], lo1, mid)),
                 transform(t.transform, box(lo0, mid, lo1, LAT[1]))]
        states.append(unary_union(polys))
    return unary_union(states) if dissolve else states


def shapely_edge_m(lons, lats, dissolve=True):
    """Reference edge_m (CR-0017 section 2) with shapely: distance to the
    boundary for contained points, else 0."""
    import shapely
    x, y = A.to_5070(np.asarray(lons, float), np.asarray(lats, float))
    pts = shapely.points(x, y)
    geoms = [fixture_domain_5070(True)] if dissolve else fixture_domain_5070(False)
    out = np.full(len(x), np.inf)
    inside = np.zeros(len(x), bool)
    for g in geoms:
        inside |= shapely.contains(g, pts)
        out = np.minimum(out, shapely.distance(g.boundary, pts))
    return np.where(inside, out, 0.0)


def _edge_band_pair(S, cand):
    """Two VT candidates 20 m apart (< MIN_SPACING_M) straddling edge_m =
    BUFFER_M at the south domain edge, the in-band one first in the seeded
    thin order, > 400 m from every sighting and > 100 m from every other
    candidate. Deterministic scan."""
    import shapely
    allS = pd.concat(list(S.values()))
    sx, sy = A.to_5070(allS["longitude"].to_numpy(), allS["latitude"].to_numpy())
    cx, cy = A.to_5070(cand["longitude"].to_numpy(), cand["latitude"].to_numpy())
    edge = fixture_domain_5070().boundary
    seed = 42
    for lon in np.round(np.arange(-72.58, -72.42, 0.0007), 6):
        pts = []
        for target in (290.0, 310.0):
            lat = LAT[0] + target / 111000.0
            for _ in range(6):                      # Newton on the true edge distance
                x, y = A.to_5070([lon], [lat])
                d = shapely.distance(edge, shapely.points(x[0], y[0]))
                lat = round(lat + (target - d) / 111000.0, 6)
            pts.append((float(lon), float(lat)))
        (a_lon, a_lat), (b_lon, b_lat) = pts
        ka = A.order_key(A.coord_text(a_lon, a_lat), seed)
        kb = A.order_key(A.coord_text(b_lon, b_lat), seed)
        if ka >= kb:
            continue
        x, y = A.to_5070([a_lon, b_lon], [a_lat, b_lat])
        if math.hypot(x[1] - x[0], y[1] - y[0]) >= 30:
            continue
        if np.hypot(sx - x[0], sy - y[0]).min() < 400 or np.hypot(sx - x[1], sy - y[1]).min() < 400:
            continue
        if np.hypot(cx - x[0], cy - y[0]).min() < 100:
            continue
        return pts
    raise RuntimeError("fixture: no edge-band thin pair found")


def _west_edge_rows(S, cand):
    """VT candidates about 200 m inside the VT west domain edge, beyond
    which lies only the non-domain county 36: > 400 m from every sighting,
    > 100 m from every other candidate and from each other."""
    allS = pd.concat(list(S.values()))
    sx, sy = A.to_5070(allS["longitude"].to_numpy(), allS["latitude"].to_numpy())
    cx, cy = A.to_5070(cand["longitude"].to_numpy(), cand["latitude"].to_numpy())
    out = []
    for lat in np.round(np.arange(LAT[0] + 0.012, LAT[1] - 0.011, 0.006), 6):
        lon = REG_LON["VT"][0] + 0.0025
        x, y = A.to_5070([lon], [lat])
        if np.hypot(sx - x[0], sy - y[0]).min() < 400 or np.hypot(cx - x[0], cy - y[0]).min() < 100:
            continue
        out.append((float(lon), float(lat)))
    return out


def build_inputs(root):
    for d in ("data/pipeline", "data/negatives", "data/landfire", "data/roads"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    _write_rasters(root)
    zp = _write_counties(root)
    cw = _write_crosswalks(root)
    S = _write_sightings(root)
    _write_metrics(root)
    _write_candidates(root, S)
    with open(os.path.join(root, "regions.py"), "w") as f:
        f.write(REGIONS_PY)
    return zp, cw


def make_config(tmpdir, root, name="config.json", **over):
    with open(PROD_CONFIG) as f:
        cfg = json.load(f)
    cfg["paths"]["crosswalk"]["sha256"] = A.sha256_file(
        os.path.join(root, cfg["paths"]["crosswalk"]["path"]))
    cfg["paths"]["county_polygons"]["sha256"] = A.sha256_file(
        os.path.join(root, cfg["paths"]["county_polygons"]["path"]))
    cfg["regions_py"]["path"] = os.path.join(root, "regions.py")
    cfg["obs"]["obs_path"] = os.path.join(tmpdir, name + ".obs.json")
    cfg["obs"].update({"n_split": 12, "n_draw": 12, "n_perm": 30})
    for k, v in over.items():
        cfg[k] = v
    path = os.path.join(tmpdir, name)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=1)
    return path


def clone(src, dst, copy_rasters=False):
    def cp(s, d):
        if s.endswith(".tif") and not copy_rasters:
            os.symlink(os.path.realpath(s), d)
        else:
            shutil.copy2(s, d)
    shutil.copytree(src, dst, copy_function=cp)
    return dst


# --------------------------------------------------------------------------
# Module fixture
# --------------------------------------------------------------------------
TMP = None
BASE = None
CFG_PATH = None
CFG = None


def setUpModule():
    global TMP, BASE, CFG_PATH, CFG
    TMP = tempfile.mkdtemp(prefix="acc_split_test_")
    BASE = os.path.join(TMP, "base")
    os.makedirs(BASE)
    build_inputs(BASE)
    CFG_PATH = make_config(TMP, BASE)
    CFG = A.load_config(CFG_PATH)
    rep = A.Replay(BASE, CFG).run(stop_on_error=True)
    rep.emit(BASE)


def tearDownModule():
    if TMP and os.path.isdir(TMP):
        shutil.rmtree(TMP)


_N = [0]


def fresh(copy_rasters=False):
    _N[0] += 1
    return clone(BASE, os.path.join(TMP, f"case{_N[0]}"), copy_rasters=copy_rasters)


def emit_attack(root, cls, **kw):
    rep = cls(root, CFG, **kw)
    rep.run(stop_on_error=True)
    rep.emit(root)
    return rep


def refresh_manifest(root, cfg=None):
    """A consistent (wrong) pipeline records its own output digests."""
    cfg = cfg or CFG
    mp = os.path.join(root, A.rpath(cfg, "split_manifest"))
    with open(mp) as f:
        m = json.load(f)
    for sec in m.values():
        for rel in list(sec.get("outputs", {})):
            sec["outputs"][rel] = A.sha256_file(os.path.join(root, rel))
    with open(mp, "w") as f:
        json.dump(m, f, indent=1)


def read(root, kind, R=None):
    return pd.read_csv(os.path.join(root, A.rpath(CFG, kind, R)), float_precision="round_trip")


def write_set(root, kinds, R, comb):
    comb.to_csv(os.path.join(root, A.rpath(CFG, kinds[0], R)), index=False)
    for s, k in zip(A.SPLITS, kinds[1:]):
        comb[comb["split"] == s].to_csv(os.path.join(root, A.rpath(CFG, k, R)), index=False)


def gates(root, only=None, cfg=None):
    _, res = A.run_gates(root, cfg or CFG, only=only)
    return res


# --------------------------------------------------------------------------
# Wrong pipelines (attack rows)
# --------------------------------------------------------------------------
class PerRegionThin(A.Replay):
    def thin(self, lons, lats, xs, ys, frame=None):
        keep = np.zeros(len(lons), bool)
        reg = frame["region"].astype(str).to_numpy()
        for R in self.regions:
            m = np.nonzero(reg == R)[0]
            keep[m] = A.thin_mask(lons[m], lats[m], xs[m], ys[m], self.seed(), self.C["MIN_SPACING_M"])
        return keep


class FileOrderThin(A.Replay):
    def thin(self, lons, lats, xs, ys, frame=None):
        ms2 = float(self.C["MIN_SPACING_M"]) ** 2
        keep = np.zeros(len(lons), bool)
        kept = []
        for i in range(len(lons)):
            if all((xs[i] - a) ** 2 + (ys[i] - b) ** 2 >= ms2 for a, b in kept):
                keep[i] = True
                kept.append((xs[i], ys[i]))
        return keep


def _greedy(order, counts, target):
    val, running = set(), 0
    for b in order:
        if running >= target:
            break
        val.add(b)
        running += counts[b]
    return val


class _BlockDraw(A.Replay):
    def select_val_blocks(self, bids, seed=None, frame=None):
        from collections import Counter
        counts = Counter(list(bids))
        target = A.py_round(self.C["VAL_FRACTION"] * len(bids))
        return _greedy(self.block_order(list(bids), counts), counts, target)


class FileOrderBlocks(_BlockDraw):
    def block_order(self, bids, counts):
        return list(dict.fromkeys(bids))


class SortedBlocks(_BlockDraw):          # dropped shuffle
    def block_order(self, bids, counts):
        return sorted(counts)


class EasternBlocks(_BlockDraw):
    def block_order(self, bids, counts):
        return sorted(counts, key=lambda b: -int(b.split("_")[0]))


class DenseFirstBlocks(_BlockDraw):
    def block_order(self, bids, counts):
        return sorted(counts, key=lambda b: (-counts[b], b))


class NeighbourBlocks(A.Replay):
    def select_val_blocks(self, bids, seed=None, frame=None):
        from collections import Counter
        counts = Counter(list(bids))
        target = A.py_round(self.C["VAL_FRACTION"] * len(bids))
        order = sorted(counts, key=lambda b: A.order_key(b, self.seed()))
        xy = {b: tuple(map(int, b.split("_"))) for b in counts}
        val, running = set(), 0
        while running < target:
            nb = [b for b in order if b not in val and any(
                abs(xy[b][0] - xy[v][0]) <= 1 and abs(xy[b][1] - xy[v][1]) <= 1 for v in val)]
            b = nb[0] if nb else next(b for b in order if b not in val)
            val.add(b)
            running += counts[b]
        return val


class TwoOrigins(A.Replay):
    OFF = {"ME": (1500.0, 1500.0), "NH": (0.0, 0.0), "VT": (700.0, 2200.0)}

    def block_ids_for(self, x, y, frame=None):
        reg = frame["region"].astype(str).to_numpy()
        bs = self.C["BLOCK_SIZE_M"]
        out = []
        for xi, yi, r in zip(x, y, reg):
            ox, oy = self.OFF[r]
            out.append(f"{math.floor((xi - ox) / bs)}_{math.floor((yi - oy) / bs)}")
        return np.array(out, dtype=object)


class _DrawSkew(A.Replay):
    def es_take(self, sub, k, seed):
        sub = self.restrict(sub, k)
        return A.Replay.es_take(self, sub, k, seed)


class SouthernHalfDraw(_DrawSkew):
    def restrict(self, sub, k):
        s = sub[sub["latitude"] <= sub["latitude"].median()]
        return s if len(s) >= k else sub


class NHOnlySkew(A.Replay):
    def draw_scores(self, sub, seed):
        keys, scores = A.Replay.draw_scores(self, sub, seed)
        if len(sub) and (sub["region"] == "NH").all():
            lat = sub["latitude"].to_numpy()
            f = np.exp(40 * (lat - lat.min()))
            scores = [s / fi for s, fi in zip(scores, f)]
        return keys, scores


class SortedIdSplit(A.Replay):
    def assign_split(self, bids, sub=None):
        bsplit = dict(zip(self.B["block_id"].astype(str), self.B["split"].astype(str)))
        vf = float((self.B["split"] == "val").mean())
        free = sorted({b for b in bids if b not in bsplit})
        nval = A.py_round(vf * len(free))
        val = set(free[:nval])
        return np.array([bsplit.get(b) or ("val" if b in val else "train") for b in bids], dtype=object)


class InterRegionSkew(A.Replay):
    def draw_targets(self, R, s):
        n = A.Replay.draw_targets(self, R, s)
        if s == "train":
            n += {"ME": 3, "NH": -3}.get(R, 0)
        return n


class FeatureExtremumSplit(A.Replay):
    def assign_split(self, bids, sub=None):
        bsplit = dict(zip(self.B["block_id"].astype(str), self.B["split"].astype(str)))
        vf = float((self.B["split"] == "val").mean())
        evh = pd.Series(sub["evh"].to_numpy(), index=list(bids)).groupby(level=0).mean()
        free = [b for b in evh.index if b not in bsplit]
        free.sort(key=lambda b: -evh[b])
        val = set(free[:A.py_round(vf * len(free))])
        return np.array([bsplit.get(b) or ("val" if b in val else "train") for b in bids], dtype=object)


class NorthDropped(A.Replay):
    def post_annotate(self, cand):
        return cand[cand["latitude"] <= 44.15].copy()


class NonVegTopUp(A.Replay):
    def draw_select(self, seed=None, record=True):
        orig = self.C["NONVEG_MAX_FRAC"]
        self.C["NONVEG_MAX_FRAC"] = 0.6
        try:
            return A.Replay.draw_select(self, seed, record)
        finally:
            self.C["NONVEG_MAX_FRAC"] = orig


class PoolStrip(A.Replay):
    def post_annotate(self, cand):
        lo = cand["longitude"]
        a, b = lo.quantile(0.45), lo.quantile(0.55)
        return cand[~lo.between(a, b)].copy()


class WeightCollapse(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        cand["weight"] = 1.0
        return cand


class SpeciesMonoculture(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        cand["weight"] = np.where(cand["common_name"] == SPECIES[0], 1e3, 1e-3)
        return cand


class NonVegMonoculture(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        nv = A.bool_array(cand["is_nonveg"])
        cand.loc[nv, "weight"] = np.where(cand.loc[nv, "evt_phys"] == "Open Water", 1e4, 1e-4)
        return cand


class PoolWeightSuppression(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        m = cand["latitude"] > 44.1
        cand.loc[m, "weight"] = cand.loc[m, "weight"] * 0.5
        return cand


class BuildWeightChanged(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        hab = ~A.bool_array(cand["is_nonveg"])
        w = cand["weight"].to_numpy(dtype=float)
        cand["weight"] = np.where(hab, np.clip(w, 0.5, 2.0), w)
        return cand


class WeightScale(A.Replay):
    def post_annotate(self, cand):
        cand = cand.copy()
        cand["weight"] = cand["weight"] * 1.005
        return cand


class NoBuffer(A.Replay):
    def sighting_buffer_mask(self, cand):
        return np.zeros(len(cand), bool)


# --- CR-0017 section 3: domain-edge attack pipelines ------------------------
class NoDomainEdge(A.Replay):
    """No domain-edge filter (pool step 6 rule (b) absent)."""
    def domain_edge_mask(self, cand):
        return np.zeros(len(cand), bool)


class EveryCountyDomain(A.Replay):
    """D = every county in the file (no STATEFP filter): the edge is only
    the outer (national) border, so the non-domain county 36 counts as data."""
    def domain(self):
        import geopandas as gpd
        cp = self.cfg["paths"]["county_polygons"]
        g = gpd.read_file(os.path.join(self.root, cp["path"]), engine="pyogrio")
        g = g.to_crs("EPSG:5070")
        return gpd.GeoSeries([g.geometry.union_all()], crs="EPSG:5070")


class UndissolvedDomain(A.Replay):
    """D not dissolved: per-state polygons, so the lines between states are edges."""
    def domain(self):
        import geopandas as gpd
        g = A.county_dissolved(self.root, self.cfg).to_crs("EPSG:5070")
        return gpd.GeoSeries(list(g.geometry), crs="EPSG:5070")


class HalfEdgeRadius(A.Replay):
    """Edge radius BUFFER_M / 2."""
    def domain_edge_mask(self, cand):
        b = float(self.C["BUFFER_M"]) / 2
        e = A.domain_edge_within(cand["x_5070"].to_numpy(), cand["y_5070"].to_numpy(),
                                 self.domain(), b)
        return e <= b


class EdgeBeforeThin(A.Replay):
    """The edge filter applied before thinning (after step 4), not in step 6."""
    def pool_until_partition(self):
        cand = A.Replay.pool_until_partition(self)
        x, y = A.to_5070(cand["longitude"].to_numpy(dtype=float),
                         cand["latitude"].to_numpy(dtype=float))
        at_edge = A.Replay.domain_edge_mask(self, cand.assign(x_5070=x, y_5070=y))
        return cand[~at_edge].copy()

    def domain_edge_mask(self, cand):
        return np.zeros(len(cand), bool)


class WithReplacement(A.Replay):
    def es_take(self, sub, k, seed):
        if k <= 0 or len(sub) == 0:
            return sub.iloc[0:0]
        rng = np.random.default_rng(0)
        p = sub["weight"].to_numpy(dtype=float)
        idx = rng.choice(len(sub), size=k, replace=True, p=p / p.sum())
        return sub.iloc[np.sort(idx)]


class NearGrouseX20(A.Replay):
    def es_take(self, sub, k, seed):
        if k <= 0 or len(sub) == 0:
            return sub.iloc[0:0]
        P = pd.concat(list(self.pos.values()))
        px, py = A.to_5070(P["longitude"].to_numpy(), P["latitude"].to_numpy())
        d = A.nearest_dist(sub["x_5070"].to_numpy(), sub["y_5070"].to_numpy(), px, py)
        near = sub[d < 1000]
        rep = pd.concat([sub] + [near] * 19, ignore_index=True)
        return A.Replay.es_take(self, rep, k, seed)


class ValNearValThinned(A.Replay):
    def post_split(self, cand):
        P = pd.concat(list(self.pos.values()))
        P = P[P["split"] == "val"]
        px, py = A.to_5070(P["longitude"].to_numpy(), P["latitude"].to_numpy())
        d = A.nearest_dist(cand["x_5070"].to_numpy(), cand["y_5070"].to_numpy(), px, py)
        return cand[~((cand["split"] == "val").to_numpy() & (d < 500))].copy()


class PartitionExceptionKept(A.Replay):
    def partition_drop(self, cand):
        out = A.Replay.partition_drop(self, cand)
        keep = cand[(np.round(cand["longitude"], 5) == NH_IN_ME[0]) &
                    (np.round(cand["latitude"], 5) == NH_IN_ME[1])]
        self.dropped = [d for d in self.dropped if (round(d[0], 5), round(d[1], 5)) != NH_IN_ME]
        return pd.concat([out, keep])


class WindowlessKept(A.Replay):
    def window_filter(self, R, df):
        return df.copy()


# --- CR-0019 section 3: year-floor attack pipelines -------------------------
class NoYearFloor(A.Replay):
    """Positives step 2 unchanged (no year floor)."""
    def year_floor(self, df):
        return np.ones(len(df), bool)


class FloorAfterThin(A.Replay):
    """The floor applied after thinning (step 4), not at step 2."""
    def year_floor(self, df):
        return np.ones(len(df), bool)

    def thin(self, lons, lats, xs, ys, frame=None):
        keep = A.Replay.thin(self, lons, lats, xs, ys, frame)
        if frame is not None and "nonveg_landcover" in frame.columns:      # positives only
            keep = keep & (frame["year"] >= self.C["YEAR_MIN"]).to_numpy()
        return keep


class FloorOffByOne(A.Replay):
    """year > YEAR_MIN instead of year >= YEAR_MIN."""
    def year_floor(self, df):
        return (df["year"] > self.C["YEAR_MIN"]).to_numpy()


class SourceLevelFloor(A.Replay):
    """The floor applied to evaluated_sightings itself (a source-level cut):
    every consumer, the 300 m buffer included, sees only year >= YEAR_MIN."""
    def sightings(self, R, section):
        S = A.Replay.sightings(self, R, section)
        return S[S["year"] >= self.C["YEAR_MIN"]].copy()


class TrainOnlyFloor(A.Replay):
    """The floor applied to the train split only (after the split)."""
    def year_floor(self, df):
        return np.ones(len(df), bool)

    def run_positives(self):
        A.Replay.run_positives(self)
        for R in self.regions:
            p = self.pos[R]
            self.pos[R] = p[~((p["split"] == "train") & (p["year"] < self.C["YEAR_MIN"]))]


class NoPoolFloor(A.Replay):
    """Pool step 1 unchanged (no candidate year floor)."""
    def pool_year_floor(self, cand):
        return cand


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
class TestReference(unittest.TestCase):
    def test_reference_passes_every_gate(self):
        root = fresh()
        res = gates(root)
        bad = {g: (r["missing"], r["problems"]) for g, r in res.items() if r["status"] != "PASS"}
        self.assertEqual(bad, {})
        self.assertEqual(set(res), set(A.GATE_IDS))

    def test_fixture_exercises_the_edge_cases(self):
        """The reference run meets what the attacks rely on."""
        rep = A.Replay(BASE, CFG).run(stop_on_error=True)
        c = rep.counts
        self.assertLess(c["positives"]["ME"]["3"], c["positives"]["ME"]["2"])   # windowless drop
        pooled = sum(c["positives"][R]["3"] for R in CFG["constants"]["REGIONS"])
        thinned = sum(c["positives"][R]["4"] for R in CFG["constants"]["REGIONS"])
        self.assertLess(thinned, pooled)                                           # thinning bites
        n = c["negatives"]
        for R in ("ME", "NH", "VT"):
            self.assertLess(n[R]["2"], n[R]["1"])       # uncertainty filter
            self.assertLess(n[R]["3"], n[R]["2"])       # dedup
            self.assertLess(n[R]["6"], n[R]["5"])       # buffer
            self.assertLess(n[R]["7"], n[R]["6"])       # extraction nodata
        self.assertLess(n["ME"]["8"], n["ME"]["7"])     # pool window drop
        self.assertIn(list(NH_IN_ME), rep.dropped)      # NH-filed record inside ME
        for spot in OUTSIDE.values():                   # inside no (in-scope) polygon
            self.assertIn(list(spot), rep.dropped)
        self.assertTrue(any(v for v in rep.pool_full["split"] == "val"))
        # dedup kept the smallest gbif_id for some keys that appear later in file order
        g = read(BASE, "gbif_candidates", "ME")
        dup = g[g["common_name"] == "Duplicate Pin"]
        self.assertTrue(len(dup))

    def test_every_gate_and_obs_row_reported_once(self):
        root = fresh()
        lines = []
        code, _ = A.full_run(root, CFG, do_obs=True, out=lines.append)
        self.assertEqual(code, 0)
        text = "\n".join(lines)
        for g in A.GATE_IDS:
            self.assertEqual(sum(1 for l in lines if l.split()[:1] == [g]), 1, g)
        for o in A.OBS_IDS:
            ol = [l for l in lines if l.split()[:1] == [o]]
            self.assertEqual(len(ol), 1, o)
            self.assertIn(" OBS ", ol[0])
        self.assertIn("ACCEPTED", text)
        self.assertTrue(os.path.exists(os.path.join(root, A.rpath(CFG, "acceptance_record"))))

    def test_calibrate_writes_references_and_z(self):
        root = fresh()
        cfgp = make_config(TMP, root, name="calib.json")
        cfg = A.load_config(cfgp)
        code, _ = A.full_run(root, cfg, do_obs=True, do_calibrate=True, out=lambda s: None)
        self.assertEqual(code, 0)
        obs = A.load_obs_refs(cfg)
        self.assertTrue(obs["references"])
        self.assertTrue(any(r["null"] == "N-draw" for r in obs["references"].values()))
        self.assertTrue(any(r["null"] == "N-split" for r in obs["references"].values()))
        lines = []
        A.full_run(root, cfg, do_obs=True, out=lines.append)
        o5 = [l for l in lines if l.startswith("O5")][0]
        self.assertIn("z=", o5)
        self.assertTrue(any("OBS references: current" in l for l in lines))
        self.assertEqual(A.sha256_file(cfgp), cfg["_sha256"])     # config untouched

    def test_calibrate_refused_when_a_gate_fails(self):
        root = fresh()
        os.remove(os.path.join(root, A.rpath(CFG, "candidate_pool")))
        cfgp = make_config(TMP, root, name="calib2.json")
        cfg = A.load_config(cfgp)
        lines = []
        code, _ = A.full_run(root, cfg, do_obs=False, do_calibrate=True, out=lines.append)
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(A.obs_path(cfg)))
        self.assertIn("calibration refused: not every GATE passes", lines)

    def test_missing_artifact_is_named_fail_and_every_gate_reported(self):
        root = fresh()
        rel = A.rpath(CFG, "candidate_pool")
        os.remove(os.path.join(root, rel))
        lines = []
        code, res = A.full_run(root, CFG, do_obs=False, out=lines.append)
        self.assertEqual(code, 1)
        for g in ("E0", "E1", "E3", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14", "R3"):
            self.assertEqual(res[g]["status"], "FAIL", g)
            self.assertIn(rel, res[g]["missing"], g)
        self.assertTrue(any(l.startswith("E0   FAIL  (missing") for l in lines))
        self.assertFalse(os.path.exists(os.path.join(root, A.rpath(CFG, "acceptance_record"))))
        for g in A.GATE_IDS:
            self.assertEqual(sum(1 for l in lines if l.split()[:1] == [g]), 1)

    def test_pre_cr_shaped_files_fail_expected_gates(self):
        """Pre-CR shape: no region column, per-region box-anchored blocks,
        no B/C/M. The CR's expected-FAIL list must fail."""
        root = fresh()
        for R in ("ME", "NH", "VT"):
            for kinds in (A.P_KINDS, A.N_KINDS):
                df = read(root, kinds[0], R).drop(columns=["region"])
                df["block_id"] = df["block_id"].astype(str) + "x"
                write_set(root, kinds, R, df)
        for k in ("block_assignments", "candidate_pool", "split_manifest"):
            os.remove(os.path.join(root, A.rpath(CFG, k)))
        res = gates(root)
        for g in ("E0", "E1", "E6", "E11", "E12", "R1", "R2", "R3", "R4"):
            self.assertEqual(res[g]["status"], "FAIL", g)


class TestAttacks(unittest.TestCase):
    """CR-0013 section Attacks: each row must fail its named gate(s)."""

    def assertFails(self, root, reasons, cfg=None):
        """reasons: {gate: substring that must appear in one of its problems}.
        Checks the gate FAILs for the intended reason (review follow-up A-R3-2)."""
        res = gates(root, only=set(reasons), cfg=cfg)
        for g, why in reasons.items():
            self.assertEqual(res[g]["status"], "FAIL", f"{g} passed under the attack: {res[g]}")
            self.assertTrue(any(why in x for x in res[g]["problems"]),
                            f"{g} failed, but not for {why!r}: {res[g]['problems'][:4]} "
                            f"missing={res[g]['missing']}")
        return res

    # --- membership ---------------------------------------------------------
    def test_box_clipped_membership(self):
        root = fresh()
        nh = read(root, "thinned_positives", "NH")
        near = nh[nh["longitude"] > -72.26].head(6).copy()
        self.assertGreater(len(near), 0)
        near["region"] = "ME"
        near["split"] = np.where(near["split"] == "val", "train", "val")
        me = pd.concat([read(root, "thinned_positives", "ME"), near], ignore_index=True)
        me = A.sort_canonical(me, ["longitude", "latitude"])
        write_set(root, A.P_KINDS, "ME", me)
        refresh_manifest(root)
        self.assertFails(root, {"E1": "rows with state != ME", "E4": "keys in both train and val",
                               "E5": "hold both train and val records"})

    def test_train_rows_copied_into_val(self):
        root = fresh()
        tr = read(root, "train_positives", "ME").head(3)
        va = pd.concat([read(root, "val_positives", "ME"), tr], ignore_index=True)
        va.to_csv(os.path.join(root, A.rpath(CFG, "val_positives", "ME")), index=False)
        refresh_manifest(root)
        self.assertFails(root, {"E1p": "'val' rows of"})

    def test_val_positive_year_nan(self):
        root = fresh()
        me = read(root, "thinned_positives", "ME")
        idx = me.index[me["split"] == "val"][:2]
        me["year"] = me["year"].astype(float)
        me.loc[idx, "year"] = np.nan
        write_set(root, A.P_KINDS, "ME", me)
        refresh_manifest(root)
        self.assertFails(root, {"R1": "column 'year' differs"})

    def test_positive_weight_02(self):
        root = fresh()
        me = read(root, "thinned_positives", "ME")
        me["weight"] = 1.0
        me.loc[me.index[0], "weight"] = 0.2
        write_set(root, A.P_KINDS, "ME", me)
        refresh_manifest(root)
        self.assertFails(root, {"R1": "!= replay"})

    def test_column_dropped(self):
        root = fresh()
        for R in ("ME", "NH", "VT"):
            write_set(root, A.P_KINDS, R, read(root, "thinned_positives", R).drop(columns=["evt_group"]))
        refresh_manifest(root)
        self.assertFails(root, {"E0": "missing ['evt_group']"})

    def test_column_added(self):
        root = fresh()
        for R in ("ME", "NH", "VT"):
            write_set(root, A.N_KINDS, R, read(root, "negatives", R).assign(foo=1))
        refresh_manifest(root)
        self.assertFails(root, {"E0": "unexpected ['foo']"})

    # --- thinning -------------------------------------------------------------
    def test_per_region_thin_then_pool(self):
        root = fresh()
        emit_attack(root, PerRegionThin)
        self.assertFails(root, {"E2": "positive pairs closer than 30 m", "R1": "rows not in the replay"})

    def test_thin_at_60m(self):
        root = fresh()
        emit_attack(root, A.Replay, constants={"MIN_SPACING_M": 60})
        self.assertFails(root, {"R1": "replay rows absent", "E11": "MIN_SPACING_M"})

    def test_order_dependent_thinner(self):
        root = fresh()
        emit_attack(root, FileOrderThin)
        self.assertFails(root, {"R1": "not in the replay"})

    # --- block draw -------------------------------------------------------------
    def test_order_dependent_block_draw(self):
        root = fresh()
        emit_attack(root, FileOrderBlocks)
        self.assertFails(root, {"R2": "column 'split' differs"})

    def test_dropped_shuffle(self):
        root = fresh()
        emit_attack(root, SortedBlocks)
        self.assertFails(root, {"R2": "column 'split' differs"})

    def test_eastern_half_val_draw(self):
        root = fresh()
        emit_attack(root, EasternBlocks)
        self.assertFails(root, {"R2": "column 'split' differs"})

    def test_dense_first_val_draw(self):
        root = fresh()
        emit_attack(root, DenseFirstBlocks)
        self.assertFails(root, {"R2": "column 'split' differs"})

    def test_neighbour_preferring_draw(self):
        root = fresh()
        emit_attack(root, NeighbourBlocks)
        self.assertFails(root, {"R2": "column 'split' differs"})

    def test_two_origins_ids_from_column(self):
        root = fresh()
        emit_attack(root, TwoOrigins)
        self.assertFails(root, {"E5": "hold both train and val records",
                               "E6": "block_id differs from the recomputed id"})

    # --- negative draw ------------------------------------------------------------
    def test_southern_half_draw(self):
        root = fresh()
        emit_attack(root, SouthernHalfDraw)
        self.assertFails(root, {"R4": "rows not in the replay"})

    def test_nh_only_skew_break1(self):
        root = fresh()
        emit_attack(root, NHOnlySkew)
        self.assertFails(root, {"R4": "rows not in the replay"})

    def test_sorted_id_positive_free_split_break2(self):
        root = fresh()
        emit_attack(root, SortedIdSplit)
        self.assertFails(root, {"R3": "column 'split' differs"})

    def test_inter_region_skew_10A(self):
        root = fresh()
        emit_attack(root, InterRegionSkew)
        self.assertFails(root, {"R4": "rows not in the replay"})

    def test_feature_extremum_split_10B(self):
        root = fresh()
        emit_attack(root, FeatureExtremumSplit)
        self.assertFails(root, {"R3": "column 'split' differs"})

    def test_northern_candidates_dropped_by_pipeline_10A2(self):
        root = fresh()
        emit_attack(root, NorthDropped)
        self.assertFails(root, {"R3": "replay rows absent"})

    def test_nonveg_top_up_10C(self):
        root = fresh()
        emit_attack(root, NonVegTopUp)
        self.assertFails(root, {"E9": "NonVeg negatives > cap", "R4": "rows not in the replay"})

    def test_pool_strip(self):
        root = fresh()
        emit_attack(root, PoolStrip)
        self.assertFails(root, {"R3": "replay rows absent"})

    def test_weight_collapse(self):
        root = fresh()
        emit_attack(root, WeightCollapse)
        self.assertFails(root, {"E10": "'weight' differs from the recomputed", "R4": "rows not in the replay"})

    def test_species_monoculture(self):
        root = fresh()
        emit_attack(root, SpeciesMonoculture)
        self.assertFails(root, {"E10": "'weight' differs from the recomputed", "R4": "rows not in the replay"})

    def test_nonveg_monoculture(self):
        root = fresh()
        emit_attack(root, NonVegMonoculture)
        self.assertFails(root, {"E10": "'weight' differs from the recomputed", "R4": "rows not in the replay"})

    def test_pool_weight_suppression(self):
        root = fresh()
        emit_attack(root, PoolWeightSuppression)
        self.assertFails(root, {"E10": "'weight' differs from the recomputed"})

    def test_build_weight_changed(self):
        root = fresh()
        emit_attack(root, BuildWeightChanged)
        self.assertFails(root, {"E10": "'weight' differs from the recomputed"})

    def test_no_300m_buffer(self):
        root = fresh()
        emit_attack(root, NoBuffer)
        self.assertFails(root, {"E7": "within 300 m of a sighting", "R3": "rows not in the replay"})

    def test_with_replacement(self):
        root = fresh()
        emit_attack(root, WithReplacement)
        self.assertFails(root, {"E3": "duplicate keys", "R4": "duplicate keys"})

    def test_x20_near_grouse(self):
        root = fresh()
        emit_attack(root, NearGrouseX20)
        self.assertFails(root, {"E3": "duplicate keys", "R4": "duplicate keys"})

    def test_val_candidates_near_val_positives_thinned(self):
        root = fresh()
        emit_attack(root, ValNearValThinned)
        self.assertFails(root, {"R3": "replay rows absent"})

    def test_duplicate_negatives(self):
        root = fresh()
        for R in ("ME", "NH", "VT"):
            n = read(root, "negatives", R)
            k = max(1, int(round(0.07 * len(n))))
            for s in A.SPLITS:
                idx = n.index[n["split"] == s]
                src, dst = idx[:k // 2 + 1], idx[-(k // 2 + 1):]
                n.loc[dst] = n.loc[src].to_numpy()
            n = A.sort_canonical(n, ["longitude", "latitude"])
            write_set(root, A.N_KINDS, R, n)
        refresh_manifest(root)
        self.assertFails(root, {"E3": "duplicate keys", "R4": "duplicate keys"})

    # --- partition, inputs, regions, windows --------------------------------
    def test_partition_exception_kept(self):
        root = fresh()
        rep = emit_attack(root, PartitionExceptionKept)
        c = rep.pool_full
        self.assertTrue(((np.round(c["longitude"], 5) == NH_IN_ME[0]) & (c["state"] == "NH")).any(),
                        "fixture: the NH-filed record did not survive to the pool")
        self.assertFails(root, {"E12": "verify_partition returns"})

    def test_dropped_list_edited(self):
        root = fresh()
        mp = os.path.join(root, A.rpath(CFG, "split_manifest"))
        with open(mp) as f:
            m = json.load(f)
        m["negatives"]["dropped"] = m["negatives"]["dropped"][1:]
        with open(mp, "w") as f:
            json.dump(m, f)
        self.assertFails(root, {"E12": "dropped list"})

    def test_input_edited_after_manifest(self):
        root = fresh()
        p = os.path.join(root, A.rpath(CFG, "envelope_metrics", "ME"))
        m = pd.read_csv(p)
        m.loc[0, "Selection_Ratio"] = 3.21
        m.to_csv(p, index=False)
        self.assertFails(root, {"E11": "changed after the manifest"})

    def test_regions_subset(self):
        root = fresh()
        emit_attack(root, A.Replay, regions=["ME"])
        self.assertFails(root, {"E1": "regions present ['ME']", "E11": "REGIONS"})

    def test_windowless_record_kept(self):
        root = fresh()
        emit_attack(root, WindowlessKept)
        self.assertFails(root, {"E8": "fail the 64 px window predicate"})

    def test_config_constant_edit_without_regions_py(self):
        """A config edit not mirrored in regions.py fails E11."""
        root = fresh()
        with open(CFG_PATH) as f:
            c = json.load(f)
        c["constants"]["BUFFER_M"] = 250
        p = os.path.join(TMP, "buf.json")
        with open(p, "w") as f:
            json.dump(c, f)
        res = gates(root, only={"E11"}, cfg=A.load_config(p))
        self.assertEqual(res["E11"]["status"], "FAIL")
        self.assertTrue(any("BUFFER_M" in x for x in res["E11"]["problems"]))


BUF = 300.0


def _pooled_neg(rep):
    return pd.concat(list(rep.neg.values()), ignore_index=True)


def _min_sighting_dist(df):
    S = pd.concat([read(BASE, "sightings", R) for R in ("ME", "NH", "VT")], ignore_index=True)
    sx, sy = A.to_5070(S["longitude"].to_numpy(), S["latitude"].to_numpy())
    x, y = A.to_5070(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    return A.nearest_dist(x, y, sx, sy)


def _county36_dist(df):
    import shapely
    from pyproj import Transformer
    from shapely.geometry import box
    from shapely.ops import transform
    t = Transformer.from_crs("EPSG:4269", "EPSG:5070", always_xy=True)
    c36 = transform(t.transform, box(-72.8, LAT[0], -72.6, LAT[1]))
    x, y = A.to_5070(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    return shapely.distance(c36, shapely.points(x, y))


class TestDomainEdgeAttacks(unittest.TestCase):
    """CR-0017 section 3 attack rows. Each asserts the fixture rows it needs
    exist (PA-0021(a): no attack may pass vacuously), then that it fails
    the named gates for the intended reason. edge_m for the precondition is
    the shapely reference (shapely_edge_m), not the code under test."""

    assertFails = TestAttacks.assertFails

    def test_reference_has_no_row_in_the_edge_band(self):
        rep = A.Replay(BASE, CFG).run(stop_on_error=True)
        for df in (rep.pool_full, _pooled_neg(rep)):
            self.assertGreater(shapely_edge_m(df["longitude"], df["latitude"]).min(), BUF)
        # step 6 removes rows on the fixture; that rules (a) and (b) each bite
        # separately is asserted in TestDomainEdgeUnits.test_step6_drops_rule_a_or_rule_b
        self.assertGreater(rep.counts["negatives"]["VT"]["5"] - rep.counts["negatives"]["VT"]["6"], 0)

    def test_no_domain_edge_filter(self):
        root = fresh()
        rep = emit_attack(root, NoDomainEdge)
        N = _pooled_neg(rep)
        e = shapely_edge_m(N["longitude"], N["latitude"])
        need = (e <= BUF) & (_min_sighting_dist(N) > BUF)
        self.assertTrue(need.any(), "fixture: no selected candidate in the edge band, "
                                    "> BUFFER_M from every sighting")
        self.assertFails(root, {"E13": "acquisition-domain edge", "R3": "rows not in the replay",
                                "R4": "rows not in the replay"})

    def test_domain_is_every_us_county(self):
        root = fresh()
        rep = emit_attack(root, EveryCountyDomain)
        N = _pooled_neg(rep)
        e = shapely_edge_m(N["longitude"], N["latitude"])
        d36 = _county36_dist(N)
        need = (e <= BUF) & (np.abs(d36 - e) < 1e-6) & (_min_sighting_dist(N) > BUF)
        self.assertTrue(need.any(), "fixture: no selected edge-band candidate whose nearest "
                                    "outside point is in the non-domain county")
        self.assertFails(root, {"E13": "acquisition-domain edge", "R3": "rows not in the replay",
                                "R4": "rows not in the replay"})

    def test_domain_not_dissolved(self):
        root = fresh()
        ref = A.Replay(BASE, CFG).run(stop_on_error=True)
        C = ref.pool_full
        need = ((shapely_edge_m(C["longitude"], C["latitude"], dissolve=False) <= BUF) &
                (shapely_edge_m(C["longitude"], C["latitude"]) > BUF) & (_min_sighting_dist(C) > BUF))
        self.assertTrue(need.any(), "fixture: no pool row within BUFFER_M of an internal state "
                                    "line, clear of the domain edge and of every sighting")
        emit_attack(root, UndissolvedDomain)
        self.assertFails(root, {"R3": "replay rows absent"})
        self.assertEqual(gates(root, only={"E13"})["E13"]["status"], "PASS")   # over-drop only

    def test_edge_radius_half_buffer(self):
        root = fresh()
        rep = emit_attack(root, HalfEdgeRadius)
        C = rep.pool_full
        e = shapely_edge_m(C["longitude"], C["latitude"])
        self.assertTrue(((e > BUF / 2) & (e <= BUF)).any(),
                        "fixture: no candidate with BUFFER_M/2 < edge_m <= BUFFER_M")
        self.assertFails(root, {"E13": "acquisition-domain edge", "R3": "rows not in the replay"})

    def test_edge_filter_before_thinning(self):
        root = fresh()
        g = read(BASE, "gbif_candidates", "VT")
        pair = g[g["common_name"] == "Edge Pair"]
        self.assertEqual(len(pair), 2, "fixture: the edge-band thin pair is absent")
        e = shapely_edge_m(pair["longitude"], pair["latitude"])
        x, y = A.to_5070(pair["longitude"].to_numpy(), pair["latitude"].to_numpy())
        self.assertLess(math.hypot(x[1] - x[0], y[1] - y[0]), CFG["constants"]["MIN_SPACING_M"])
        inb = int(np.argmin(e))
        self.assertTrue(e[inb] <= BUF < e[1 - inb], "fixture: the pair does not straddle the band edge")
        keys = [A.order_key(A.coord_text(lo, la), CFG["constants"]["SPLIT_SEED"])
                for lo, la in zip(pair["longitude"], pair["latitude"])]
        self.assertLess(keys[inb], keys[1 - inb], "fixture: the in-band member is not first in "
                                                  "the thin order")
        rep = emit_attack(root, EdgeBeforeThin)
        ref = A.Replay(BASE, CFG).run(stop_on_error=True)
        out_key = A.key_list(pair.iloc[[1 - inb]], 5)[0]
        self.assertIn(out_key, A.key_list(rep.pool_full, 5),
                      "fixture: the out-of-band neighbour did not survive steps 7-10")
        self.assertNotIn(out_key, A.key_list(ref.pool_full, 5))
        self.assertFails(root, {"R3": "rows not in the replay"})


class TestDomainEdgeUnits(unittest.TestCase):
    def _square(self, *boxes):
        import geopandas as gpd
        from shapely.geometry import box
        return gpd.GeoSeries([box(*b) for b in boxes], crs="EPSG:5070")

    def test_inside_outside_on_boundary(self):
        D = self._square((0, 0, 10000, 10000))
        e = A.domain_edge_within([5000, 100, -50, 0, 5000, 20000], [5000, 5000, 5000, 5000, 10000, 3],
                                 D, 300)
        self.assertEqual(e[0], np.inf)             # > radius: reported as +inf
        self.assertAlmostEqual(e[1], 100.0, places=9)
        self.assertEqual(list(e[2:]), [0.0, 0.0, 0.0, 0.0])   # outside / on the boundary -> 0

    def test_threshold_inclusive(self):
        D = self._square((0, 0, 10000, 10000))
        e = A.domain_edge_within([300.0, 300.000001], [5000.0, 5000.0], D, 300)
        self.assertEqual(e[0], 300.0)
        self.assertTrue(e[0] <= 300)               # exactly BUFFER_M: dropped
        self.assertGreater(e[1], 300)              # BUFFER_M + 1e-6: kept

    def _edge_rows(self, b):
        """Two rows inside a 10 km square D: edge_m == BUFFER_M exactly and
        BUFFER_M + 1e-6 (x distance to the west side; exact in float64)."""
        return pd.DataFrame({"longitude": [-72.0, -72.1], "latitude": [44.0, 44.1],
                             "x_5070": [b, b + 1e-6], "y_5070": [5000.0, 5000.0]})

    def test_domain_edge_mask_threshold_inclusive(self):
        """Replay.domain_edge_mask (step 6 rule (b)): edge_m == BUFFER_M is
        dropped, BUFFER_M + 1e-6 is kept (CR-0017 F1)."""
        b = float(CFG["constants"]["BUFFER_M"])
        D = self._square((0, 0, 10000, 10000))
        rep = A.Replay.__new__(A.Replay)
        rep.C = {"BUFFER_M": CFG["constants"]["BUFFER_M"]}
        rep.domain = lambda: D
        cand = self._edge_rows(b)
        self.assertEqual(A.domain_edge_within(cand["x_5070"], cand["y_5070"], D, b)[0], b)
        self.assertEqual(list(rep.domain_edge_mask(cand)), [True, False])

    def test_gate_e13_threshold_inclusive(self):
        """gate_E13: a row at edge_m == BUFFER_M FAILs; BUFFER_M + 1e-6 passes
        (CR-0017 F1). The context is a stub; D is monkeypatched."""
        from unittest import mock
        b = float(CFG["constants"]["BUFFER_M"])
        D = self._square((0, 0, 10000, 10000))
        rows = self._edge_rows(b)

        class Ctx:
            def __init__(self, N, C):
                self.C, self.root, self.cfg = {"BUFFER_M": CFG["constants"]["BUFFER_M"]}, BASE, CFG
                self._N, self._C = N, C

            def pooled(self, kind, missing):
                return self._N.assign(_R="VT")

            def try_csv(self, rel, missing):
                return self._C

            def xy(self, df):
                return df["x_5070"].to_numpy(dtype=float), df["y_5070"].to_numpy(dtype=float)

        at, above = rows.iloc[[0]].reset_index(drop=True), rows.iloc[[1]].reset_index(drop=True)
        with mock.patch.object(A, "acquisition_domain", return_value=D):
            problems, missing = A.gate_E13(Ctx(at, above))
            self.assertEqual(missing, [])
            self.assertEqual(len(problems), 1, problems)
            self.assertTrue(problems[0].startswith("N (pooled): 1 rows within"), problems)
            problems, missing = A.gate_E13(Ctx(above, at))
            self.assertEqual(len(problems), 1, problems)
            self.assertTrue(problems[0].startswith("C: 1 rows within"), problems)
            self.assertEqual(A.gate_E13(Ctx(above, above)), ([], []))

    def test_long_segments_are_exact(self):
        """A 10 km side has only two vertices; the nearest point is mid-segment."""
        D = self._square((0, 0, 10000, 10000))
        e = A.domain_edge_within([5000.0, 7321.5], [299.9, 9950.0], D, 300)
        self.assertAlmostEqual(e[0], 299.9, places=9)
        self.assertAlmostEqual(e[1], 50.0, places=9)

    def test_line_between_dissolved_states_is_not_an_edge(self):
        import geopandas as gpd
        parts = self._square((0, 0, 5000, 10000), (5000, 0, 10000, 10000))
        D = gpd.GeoSeries([parts.union_all()], crs="EPSG:5070")
        e = A.domain_edge_within([5005.0, 4990.0], [5000.0, 5000.0], D, 300)
        self.assertEqual(list(e), [np.inf, np.inf])
        e = A.domain_edge_within([5005.0, 4990.0, 5000.0], [5000.0, 5000.0, 5000.0], parts, 300)
        self.assertAlmostEqual(e[0], 5.0, places=9)   # undissolved: the internal line counts
        self.assertAlmostEqual(e[1], 10.0, places=9)
        self.assertEqual(e[2], 0.0)                   # on the internal line: within neither part

    def test_matches_shapely_reference_on_the_fixture(self):
        rng = np.random.default_rng(11)
        lon = rng.uniform(-72.62, -71.98, 4000)
        lat = rng.uniform(43.99, 44.21, 4000)
        x, y = A.to_5070(lon, lat)
        D = A.acquisition_domain(BASE, CFG)
        for radius in (300.0, 1000.0):
            got = A.domain_edge_within(x, y, D, radius)
            ref = shapely_edge_m(lon, lat)
            near = ref <= radius
            self.assertTrue(near.any() and (~near).any())
            np.testing.assert_allclose(got[near], ref[near], rtol=0, atol=1e-6)
            self.assertTrue(np.isinf(got[~near]).all())

    def test_domain_is_the_config_states_only(self):
        D = A.acquisition_domain(BASE, CFG)
        self.assertEqual(len(D), 1)
        self.assertEqual(D.crs.to_string(), "EPSG:5070")
        ref = fixture_domain_5070()
        self.assertLess(D.iloc[0].symmetric_difference(ref).area, 1e-3 * ref.area / 1e6)

    def test_step6_drops_rule_a_or_rule_b(self):
        """Pool step 6: the rows dropped are exactly (a) | (b) of the step-5 pool."""
        seen = {}

        class Spy(A.Replay):
            def buffer_drop(self, cand):
                out = A.Replay.buffer_drop(self, cand)
                seen["in"], seen["out"] = cand, out
                return out

        Spy(BASE, CFG).run(stop_on_error=True)
        cand, out = seen["in"], seen["out"]
        dmin = _min_sighting_dist(cand)
        a = dmin <= BUF
        b = shapely_edge_m(cand["longitude"], cand["latitude"]) <= BUF
        self.assertTrue((a & ~b).any() and (b & ~a).any())
        self.assertEqual(sorted(A.key_list(out, 5)), sorted(A.key_list(cand[~(a | b)], 5)))

    def test_e13_missing_county_file_is_named(self):
        root = fresh()
        rel = CFG["paths"]["county_polygons"]["path"]
        os.remove(os.path.join(root, rel))
        res = gates(root, only={"E13"})
        self.assertEqual(res["E13"]["status"], "FAIL")
        self.assertIn(rel, res["E13"]["missing"])

    def test_e13_catches_one_edge_row_in_C(self):
        root = fresh()
        c = read(root, "candidate_pool")
        row = c.iloc[[0]].copy()
        row["longitude"], row["latitude"] = -72.598, 44.1          # ~160 m inside VT's west edge
        c = A.sort_canonical(pd.concat([c, row], ignore_index=True), CFG["row_order"]["pool"])
        c.to_csv(os.path.join(root, A.rpath(CFG, "candidate_pool")), index=False)
        res = gates(root, only={"E13"})
        self.assertEqual(res["E13"]["status"], "FAIL")
        self.assertTrue(any(x.startswith("C: 1 rows within 300 m") for x in res["E13"]["problems"]),
                        res["E13"]["problems"])

    def test_config_domain_edge_cannot_be_removed_or_repointed(self):
        with open(PROD_CONFIG) as f:
            base = json.load(f)
        muts = {"absent": lambda c: c["paths"].pop("domain_edge"),
                "source": lambda c: c["paths"]["domain_edge"].update(source="data/roads/other.zip"),
                "copied": lambda c: c["paths"]["domain_edge"].update(
                    source=dict(c["paths"]["county_polygons"])),
                "crs": lambda c: c["paths"]["domain_edge"].update(edge_crs="EPSG:4326")}
        for name, mut in muts.items():
            c = copy.deepcopy(base)
            mut(c)
            p = os.path.join(TMP, f"de_{name}.json")
            with open(p, "w") as f:
                json.dump(c, f)
            with self.assertRaises(A.ConfigError, msg=name):
                A.load_config(p)
            out = subprocess.run([sys.executable, os.path.join(REPO, "acceptance_split.py"),
                                  "--config", p, "--data-root", BASE], capture_output=True, text=True)
            self.assertEqual(out.returncode, 2, name)
            self.assertIn("paths.domain_edge", out.stdout, name)

    def test_e13_not_in_standing_subset(self):
        import inspect
        src = inspect.getsource(A.standing_checks)
        self.assertNotIn("E13", src)
        self.assertIn("E13", A.GATE_IDS)
        self.assertEqual(len(A.GATE_IDS), 20)          # CR-0019: + E14


# --------------------------------------------------------------------------
# CR-0019 section 3: E14 and the year floor
# --------------------------------------------------------------------------
REGIONS3 = ("ME", "NH", "VT")


def _files(root, kind):
    """Pooled frame of a per-region file kind, read with pandas directly."""
    return pd.concat([read(root, kind, R).assign(_R=R) for R in REGIONS3], ignore_index=True)


def _keys(df):
    return set(zip(np.round(df["longitude"].to_numpy(float), 5), np.round(df["latitude"].to_numpy(float), 5)))


def _xy(lon, lat):
    """EPSG:4326 -> EPSG:5070 with pyproj directly (not acceptance_split)."""
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    return t.transform(np.asarray(lon, float), np.asarray(lat, float))


def _min_dist(qlon, qlat, rlon, rlat):
    from scipy.spatial import cKDTree
    qx, qy = _xy(qlon, qlat)
    rx, ry = _xy(rlon, rlat)
    if len(rx) == 0:
        return np.full(len(qx), np.inf)
    d, _ = cKDTree(np.column_stack([rx, ry])).query(np.column_stack([qx, qy]))
    return d


class TestYearFloorAttacks(unittest.TestCase):
    """CR-0019 section 3 attack rows. Each first asserts, by a computation
    made here with pandas/pyproj/hashlib on the files (not by the gate
    under test), that the fixture rows the row needs exist (PA-0021(a): no
    attack may pass vacuously); then that the named gates fail for the
    intended reason."""

    assertFails = TestAttacks.assertFails

    def e14_problems(self, root):
        res = gates(root, only={"E14"})
        self.assertEqual(res["E14"]["status"], "FAIL", res["E14"])
        return res["E14"]["problems"]

    def test_no_floor(self):
        root = fresh()
        emit_attack(root, NoYearFloor)
        P, N = _files(root, "thinned_positives"), _files(root, "negatives")
        low = P[P["year"] < YEAR_MIN]
        hab = low[~low["nonveg_landcover"].astype(bool)]
        self.assertGreater(len(hab), 0, "fixture: no habitat positive with year < YEAR_MIN "
                                        "survives the window and the thin")
        self.assertTrue(set(hab["year"]) - set(N["year"]),
                        "fixture: every pre-floor positive year also has a negative")
        self.assertFails(root, {"E14": "distinct years differ", "R1": "rows not in the replay",
                                "R2": "rows not in the replay"})
        self.assertTrue(any(x.startswith("P (combined, pooled)") for x in self.e14_problems(root)))

    def test_floor_after_thinning(self):
        S = _files(BASE, "sightings")
        S = S[~S["nonveg_landcover"].astype(bool)].reset_index(drop=True)
        x, y = _xy(S["longitude"], S["latitude"])
        from scipy.spatial import cKDTree
        pairs = cKDTree(np.column_stack([x, y])).query_pairs(CFG["constants"]["MIN_SPACING_M"] - 1e-9)
        ref_keys = _keys(_files(BASE, "thinned_positives"))
        want = []
        for i, j in pairs:
            for a, b in ((i, j), (j, i)):
                if (S["year"][a] < YEAR_MIN <= S["year"][b] and
                        _thin_key(S["longitude"][a], S["latitude"][a]) <
                        _thin_key(S["longitude"][b], S["latitude"][b]) and
                        _keys(S.iloc[[b]]) <= ref_keys):
                    want.append(b)
        self.assertTrue(want, "fixture: no habitat pair closer than MIN_SPACING_M with the "
                              "year < YEAR_MIN member first in thin order and its >= YEAR_MIN "
                              "partner kept by the correct tree")
        root = fresh()
        emit_attack(root, FloorAfterThin)
        lost = _keys(S.iloc[want]) - _keys(_files(root, "thinned_positives"))
        self.assertTrue(lost, "fixture: the attack kept every such partner")
        self.assertFails(root, {"R1": "replay rows absent"})
        self.assertEqual(gates(root, only={"E14"})["E14"]["status"], "PASS")     # E14 passes

    def test_floor_off_by_one(self):
        P = _files(BASE, "thinned_positives")
        at = P[(P["year"] == YEAR_MIN) & ~P["nonveg_landcover"].astype(bool)]
        self.assertGreater(len(at), 0, "fixture: no habitat positive with year == YEAR_MIN "
                                       "survives the thin")
        root = fresh()
        emit_attack(root, FloorOffByOne)
        self.assertFails(root, {"R1": "replay rows absent", "R2": "replay rows absent"})

    def test_floor_applied_to_the_sightings(self):
        root = fresh()
        rep = emit_attack(root, SourceLevelFloor)
        S = _files(BASE, "sightings")
        lo, hi = S[S["year"] < YEAR_MIN], S[S["year"] >= YEAR_MIN]
        C = rep.pool_full
        only_low = ((_min_dist(C["longitude"], C["latitude"], lo["longitude"], lo["latitude"]) <= BUF) &
                    (_min_dist(C["longitude"], C["latitude"], hi["longitude"], hi["latitude"]) > BUF))
        cand = C[only_low]
        self.assertGreater(len(cand), 0, "fixture: no candidate within BUFFER_M of a year < "
                                         "YEAR_MIN sighting only that survives steps 7-10")
        self.assertFalse(_keys(cand) & _keys(read(BASE, "candidate_pool")))
        self.assertTrue(_keys(cand) & _keys(_files(root, "negatives")),
                        "fixture: no such candidate is drawn")
        self.assertFails(root, {"R3": "rows not in the replay", "R4": "rows not in the replay"})

    def test_floor_on_the_train_split_only(self):
        root = fresh()
        emit_attack(root, TrainOnlyFloor)
        P = _files(root, "thinned_positives")
        low_val = P[(P["year"] < YEAR_MIN) & (P["split"] == "val")]
        self.assertGreater(len(low_val), 0, "fixture: no year < YEAR_MIN positive in a "
                                            "validation block")
        B = read(root, "block_assignments")
        bsplit = dict(zip(B["block_id"].astype(str), B["split"].astype(str)))
        self.assertTrue(all(bsplit.get(b) == "val" for b in low_val["block_id"].astype(str)))
        self.assertFails(root, {"E14": "P (combined, pooled)", "R1": "rows not in the replay",
                                "R2": "rows not in the replay"})

    def test_positives_later_than_every_negative(self):
        """Pipeline right, inputs wrong: habitat positives re-acquired to a
        later year than every candidate (fixture variant)."""
        root = fresh()
        G = pd.concat([read(root, "gbif_candidates", R) for R in REGIONS3], ignore_index=True)
        late = int(G["year"].max()) + 1
        ref = read(BASE, "thinned_positives", "ME")
        pick = _keys(ref[~ref["nonveg_landcover"].astype(bool)].head(3))
        sp = os.path.join(root, A.rpath(CFG, "sightings", "ME"))
        S = pd.read_csv(sp, float_precision="round_trip")
        m = np.array([k in pick for k in zip(np.round(S["longitude"], 5), np.round(S["latitude"], 5))])
        self.assertEqual(int(m.sum()), 3)
        S.loc[m, "year"] = late
        S.to_csv(sp, index=False)
        emit_attack(root, A.Replay)
        P = _files(root, "thinned_positives")
        above = P[(P["year"] > G["year"].max()) & ~P["nonveg_landcover"].astype(bool)]
        self.assertGreater(len(above), 0, "fixture: no habitat positive above every candidate "
                                          "year survives the window and the thin")
        self.assertFails(root, {"E14": "distinct years differ"})
        res = gates(root, only={"E14", "R1"})
        self.assertFalse(any("combined, pooled" in x for x in res["E14"]["problems"]))  # (a) holds
        self.assertEqual(res["R1"]["status"], "PASS", res["R1"])                      # pipeline right

    def test_no_pool_floor(self):
        G = read(BASE, "gbif_candidates", "ME")
        self.assertTrue((G["year"] < YEAR_MIN).any(), "fixture: no raw candidate below YEAR_MIN")
        root = fresh()
        emit_attack(root, NoPoolFloor)
        C = read(root, "candidate_pool")
        self.assertTrue((C["year"] < YEAR_MIN).any(), "fixture: no candidate with year < "
                                                      "YEAR_MIN survives to C")
        self.assertFails(root, {"E14": "C: ", "R3": "rows not in the replay"})


class TestYearFloorUnits(unittest.TestCase):
    def test_reference_year_sets_equal_by_construction(self):
        """Review A4: in the correct tree the pooled P and N year sets are
        equal, and every attack's pre-floor rows exist in the raw inputs."""
        P, N = _files(BASE, "thinned_positives"), _files(BASE, "negatives")
        self.assertEqual(sorted(set(P["year"])), FIX_YEARS)
        self.assertEqual(sorted(set(N["year"])), FIX_YEARS)
        C = read(BASE, "candidate_pool")
        self.assertTrue((C["year"] >= YEAR_MIN).all())
        S = _files(BASE, "sightings")
        self.assertTrue(((S["year"] < YEAR_MIN) & ~S["nonveg_landcover"].astype(bool)).any())
        G = pd.concat([read(BASE, "gbif_candidates", R) for R in REGIONS3])
        self.assertTrue((G["year"] < YEAR_MIN).any())
        self.assertEqual(gates(fresh(), only={"E14"})["E14"]["status"], "PASS")

    def test_step2_floor_is_inclusive(self):
        rep = A.Replay(BASE, CFG)
        df = pd.DataFrame({"year": [YEAR_MIN - 1, YEAR_MIN, YEAR_MIN + 1]})
        self.assertEqual(list(rep.year_floor(df)), [False, True, True])

    def test_pool_step1_drops_below_floor_keeps_null(self):
        rep = A.Replay(BASE, CFG)
        df = pd.DataFrame({"year": [YEAR_MIN - 1, YEAR_MIN, np.nan], "k": [0, 1, 2]})
        self.assertEqual(list(rep.pool_year_floor(df)["k"]), [1, 2])

    def test_pool_step1_count_and_step7_null_drop(self):
        """Count "1" is after the floor; a null-year candidate survives step 1
        and is dropped at step 7 (extraction)."""
        rep = A.Replay(BASE, CFG)
        cand = rep.load_candidates()
        G = pd.concat([read(BASE, "gbif_candidates", R).assign(_R=R) for R in REGIONS3])
        for R in REGIONS3:
            g = G[G["_R"] == R]
            self.assertEqual(rep.counts["negatives"][R]["1"], int((g["year"] >= YEAR_MIN).sum()))
        self.assertTrue((cand["year"] >= YEAR_MIN).all())
        C = read(BASE, "candidate_pool")
        sub = C[C["region"] == "ME"].head(4)[["longitude", "latitude", "year"]].copy()
        sub["year"] = sub["year"].astype(float)
        sub.iloc[0, sub.columns.get_loc("year")] = np.nan
        self.assertEqual(len(rep.pool_year_floor(sub)), 4)
        out = rep.extract("ME", sub)
        self.assertEqual(_keys(out), _keys(sub.iloc[1:]))

    def test_null_year_sighting_raises(self):
        root = fresh()
        sp = os.path.join(root, A.rpath(CFG, "sightings", "NH"))
        S = pd.read_csv(sp, float_precision="round_trip")
        i = S.index[S["nonveg_landcover"].astype(bool)][0]          # a non-habitat row
        S["year"] = S["year"].astype(float)
        S.loc[i, "year"] = np.nan
        S.to_csv(sp, index=False)
        with self.assertRaises(A.ReplayError) as cm:
            A.Replay(root, CFG).run(stop_on_error=True)
        self.assertIn("null year", str(cm.exception))

    def _mutate(self, kind, R, fn):
        root = fresh()
        df = read(root, kind, R)
        df = fn(df)
        if kind == "thinned_positives":
            write_set(root, A.P_KINDS, R, df)
        elif kind == "negatives":
            write_set(root, A.N_KINDS, R, df)
        else:
            df.to_csv(os.path.join(root, A.rpath(CFG, kind, R)), index=False)
        return gates(root, only={"E14"})["E14"]

    def _set_year(self, value, rows=1):
        def fn(df):
            df = df.copy()
            if isinstance(value, float):
                df["year"] = df["year"].astype(float)
            df.loc[df.index[:rows], "year"] = value
            return df
        return fn

    def test_e14a_positives(self):
        for value, what in ((np.nan, "null 1"), (YEAR_MIN + 0.5, "non-integral 1"),
                            (YEAR_MIN - 1, "year < YEAR_MIN 1")):
            r = self._mutate("thinned_positives", "VT", self._set_year(value))
            self.assertEqual(r["status"], "FAIL", value)
            self.assertTrue(any(x.startswith("P (combined, pooled): 1 rows") and what in x
                                for x in r["problems"]), r["problems"])
        r = self._mutate("thinned_positives", "VT", self._set_year(YEAR_MIN))
        self.assertEqual(r["status"], "PASS", r)                  # == YEAR_MIN passes

    def test_e14a_negatives(self):
        r = self._mutate("negatives", "NH", self._set_year(YEAR_MIN - 1))
        self.assertTrue(any(x.startswith("N (combined, pooled): 1 rows") for x in r["problems"]),
                        r["problems"])

    def test_e14a_pool(self):
        r = self._mutate("candidate_pool", None, self._set_year(np.nan))
        self.assertEqual(r["status"], "PASS", r)                  # a null C year is allowed
        r = self._mutate("candidate_pool", None, self._set_year(YEAR_MIN - 1))
        self.assertEqual(r["status"], "FAIL")
        self.assertTrue(any(x.startswith("C: 1 rows with a non-null year < YEAR_MIN")
                            for x in r["problems"]), r["problems"])

    def test_e14b_upper_end_divergence(self):
        """(b): N without its latest year fails, although (a) holds."""
        top = FIX_YEARS[-1]

        def fn(df):
            df = df.copy()
            df.loc[df["year"] == top, "year"] = top - 1
            return df
        root = fresh()
        for R in REGIONS3:
            write_set(root, A.N_KINDS, R, fn(read(root, "negatives", R)))
        r = gates(root, only={"E14"})["E14"]
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["problems"]), 1, r["problems"])
        self.assertIn(f"only in P {{{top}}}", r["problems"][0])

    def test_e14b_negative_only_year(self):
        """(b): P without its latest year fails too — the mirror case, so a
        gate weakened to "P years subset of N years" is caught (CR-0019
        code review B, F1)."""
        top = FIX_YEARS[-1]

        def fn(df):
            df = df.copy()
            df.loc[df["year"] == top, "year"] = top - 1
            return df
        root = fresh()
        for R in REGIONS3:
            write_set(root, A.P_KINDS, R, fn(read(root, "thinned_positives", R)))
        r = gates(root, only={"E14"})["E14"]
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["problems"]), 1, r["problems"])
        self.assertIn(f"only in N {{{top}}}", r["problems"][0])

    def test_e14_in_standing_subset_without_C(self):
        import inspect
        self.assertIn('("E14", gate_E14, {"include_C": False})', inspect.getsource(A.standing_checks))
        root = fresh()
        os.remove(os.path.join(root, A.rpath(CFG, "candidate_pool")))
        ctx = A.Context(root, CFG, coords="columns")
        self.assertEqual(A.evaluate(A.gate_E14, ctx, include_C=False)[0], "PASS")
        self.assertEqual(A.evaluate(A.gate_E14, ctx)[0], "FAIL")

    def test_config_year_min_and_regions_py(self):
        self.assertIsInstance(CFG["constants"]["YEAR_MIN"], int)
        self.assertEqual(CFG["regions_py"]["names"]["YEAR_MIN"], "YEAR_MIN")
        root = fresh()
        rp = os.path.join(TMP, f"regions_ym_{_N[0]}.py")
        with open(rp, "w") as f:
            f.write(REGIONS_PY.replace(f"YEAR_MIN = {YEAR_MIN}", f"YEAR_MIN = {YEAR_MIN - 1}"))
        with open(CFG_PATH) as f:
            c = json.load(f)
        c["regions_py"]["path"] = rp
        p = os.path.join(TMP, "ym.json")
        with open(p, "w") as f:
            json.dump(c, f)
        res = gates(root, only={"E11"}, cfg=A.load_config(p))
        self.assertEqual(res["E11"]["status"], "FAIL")
        self.assertTrue(any("regions.py: YEAR_MIN" in x for x in res["E11"]["problems"]))

    def test_manifest_without_year_min_fails_E11(self):
        root = fresh()
        mp = os.path.join(root, A.rpath(CFG, "split_manifest"))
        with open(mp) as f:
            m = json.load(f)
        for sec in ("positives", "negatives"):
            m[sec]["constants"].pop("YEAR_MIN")
        with open(mp, "w") as f:
            json.dump(m, f)
        res = gates(root, only={"E11"})
        self.assertEqual(res["E11"]["status"], "FAIL")
        self.assertTrue(any("constants differs" in x and "YEAR_MIN" in x for x in res["E11"]["problems"]))


class TestStanding(unittest.TestCase):
    """Standing checks: val file edited after acceptance; pre-CR file
    swapped in; raster touched; --jitter 8 with augmentation."""

    def setUp(self):
        self.root = fresh(copy_rasters=True)
        code, _ = A.full_run(self.root, CFG, do_obs=False, out=lambda s: None)
        self.assertEqual(code, 0)

    def call(self, img=64, jitter=0, augment=False):
        return A.standing_checks(img, jitter, augment, data_root=self.root, config=CFG_PATH)

    def test_passes_after_acceptance(self):
        self.assertTrue(self.call())
        self.assertTrue(self.call(64, 8, False))

    def test_val_file_edited(self):
        p = os.path.join(self.root, A.rpath(CFG, "val_positives", "NH"))
        df = pd.read_csv(p)
        df.loc[0, "year"] = int(df.loc[0, "year"]) - 1
        df.to_csv(p, index=False)
        with self.assertRaises(A.AcceptanceError):
            self.call()

    def test_pre_cr_file_swapped_in(self):
        p = os.path.join(self.root, A.rpath(CFG, "thinned_positives", "ME"))
        pd.read_csv(p).drop(columns=["region"]).to_csv(p, index=False)
        with self.assertRaises(A.AcceptanceError) as cm:
            self.call()
        self.assertIn("E0", str(cm.exception))

    def test_raster_touched(self):
        with open(os.path.join(self.root, A.rpath(CFG, "acceptance_record"))) as f:
            rec = json.load(f)
        rel = rec["rasters"][0][0]
        full = os.path.join(self.root, rel)
        st = os.stat(full)
        os.utime(full, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        with self.assertRaises(A.AcceptanceError) as cm:
            self.call()
        self.assertIn("raster changed", str(cm.exception))

    def test_jitter8_with_augmentation(self):
        with self.assertRaises(A.AcceptanceError) as cm:
            self.call(64, 8, True)
        self.assertIn("WINDOW_PX", str(cm.exception))

    def test_no_record_raises(self):
        os.remove(os.path.join(self.root, A.rpath(CFG, "acceptance_record")))
        with self.assertRaises(A.AcceptanceError):
            self.call()

    def test_imports_only_numpy_pandas_scipy(self):
        code = ("import sys; sys.path.insert(0, %r); import acceptance_split as a; "
                "a.standing_checks(64, 0, False, data_root=%r, config=%r); "
                "print(sorted(m for m in ('pyproj', 'rasterio', 'geopandas', 'shapely', 'fiona', "
                "'pyogrio', 'torch', 'regions', 'train', 'dataset', 'models') if m in sys.modules))"
                % (REPO, self.root, CFG_PATH))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=TMP)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "[]")

    def test_cli_standing(self):
        out = subprocess.run([sys.executable, os.path.join(REPO, "acceptance_split.py"), "--standing",
                              "--data-root", self.root, "--config", CFG_PATH],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class TestShuffle(unittest.TestCase):
    def test_permuted_inputs_and_regions_give_identical_bytes(self):
        root = os.path.join(TMP, "shuffle")
        os.makedirs(root)
        rng = np.random.default_rng(123)
        for dirpath, _, files in os.walk(BASE):
            rel_dir = os.path.relpath(dirpath, BASE)
            os.makedirs(os.path.join(root, rel_dir), exist_ok=True)
            for fn in files:
                src = os.path.join(dirpath, fn)
                dst = os.path.join(root, rel_dir, fn)
                if fn.endswith(".csv") and ("evaluated_sightings" in fn or "envelope_metrics" in fn
                                            or "gbif_negatives" in fn or fn.endswith("_EVT.csv")):
                    df = pd.read_csv(src, float_precision="round_trip")
                    df.iloc[rng.permutation(len(df))].to_csv(dst, index=False)
                elif fn.endswith(".tif") or fn.endswith(".zip") or fn == "regions.py":
                    os.symlink(os.path.realpath(src), dst)
        with open(CFG_PATH) as f:
            c = json.load(f)
        c["constants"]["REGIONS"] = ["VT", "ME", "NH"]
        c["paths"]["crosswalk"]["sha256"] = A.sha256_file(
            os.path.join(root, c["paths"]["crosswalk"]["path"]))
        p = os.path.join(TMP, "shuffle.json")
        with open(p, "w") as f:
            json.dump(c, f)
        cfg = A.load_config(p)
        A.Replay(root, cfg).run(stop_on_error=True).emit(root)
        for rel in A.digested_paths(CFG):
            with open(os.path.join(BASE, rel), "rb") as a, open(os.path.join(root, rel), "rb") as b:
                self.assertEqual(a.read(), b.read(), rel)


# CR-0013 design rule 3, enforced mechanically (review follow-up A-R3-1).
# Every top-level config section that changes what a GATE checks is pinned
# by sha256 of its canonical JSON. Only OBS-only sections are unpinned.
# Editing a pinned section fails TestConfigPin until this table is updated
# in the same, reviewed change.
OBS_ONLY_SECTIONS = {"_comment", "obs", "continuous_features"}
GATE_SECTION_SHA256 = {
    "NODATA_SENTINELS": "68c6d78d4fb31975bbb2690e3b756bff3c672f8a9bcaf7f43e791fea739dee1a",
    "block_id": "1d9284b22bd75dc1206e5ef865fbd0ca260988c69c5340ee9630173ad78f2402",
    "columns": "a2ad2a0c13194c6a17f0a4e845b343f7c205f6f62fa49c50725f1a44e1d46e73",
    "comparison": "84998a87573c00d01683c92413b58c3d848ca6a684e4fe7fb2006c1882999296",
    "constants": "09dc9f9142497863e554a68aac4395868b235f83e7ce2625d9f9864abce73422",   # CR-0019: + YEAR_MIN
    "dedup": "1dd8c5068b95ed5e7bdebcdfae84bf6930d389a93225a372938573d185ccb8a0",
    "distance": "942007efe795b0e9d5725a24582819cdf481eb807e8c4a4c2a7367ee36f02375",
    "envelope": "184dffd4e3a4e7a489db2ecf8de86c0d2a45c56becf1ab7c064a6223d9df0502",
    "environment": "af840e02d1d7d6612a7c1ab4a3d49968db23362cbc16846d58e52c894d548249",
    "feature_spec_keys": "6a19f9b03a49f704a8cb59f2a7bb77f85d3f8e06af56087a14c38f9a1b2e7e43",
    "hash_spec": "b23ed261b2a27647b9cd4dccf71c9638448efc2338d0d2889013807ab44f82e1",
    "manifest_schema": "652b8c0262fec0070c7216e8ceeb9053445c5deef3bb8cd98692e7c8732d3e2a",
    "parsing": "4acb340c20cf9c16404cefd22555a3a626a799808d6d1eee1283e2aa929129b8",
    "paths": "14f974c9fe084aa1db73b74ab038888816f91b7bc17002c215e7f62366355ef5",   # CR-0017: + domain_edge
    "pins": "9957bf9f9161c6a2d61d9573b91d952e5e4e77db26e9f0158adad3725354f0d9",
    "raster": "f05264dd8932f962a54552e8db3a77264158357b5744c4c4029f1aa70173dca8",
    "regions_py": "6359cff9feaa57c7ebbc6479bb06b9609c5b727b749a5390ad12a26b4344acd4",   # CR-0019: + YEAR_MIN
    "rounding": "63aa62dd917e18ec81b13f0ecbf4539db5f3a884d7fe22ee0d366cc79d01e120",
    "row_order": "add25a56f55a254fca815b698cfa3598997e946ec6627b13a70538c0959b91f6",
    "schema_version": "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
    "split_for_unassigned": "4ad4b874fdcfadff6d3e35749a3bd1ec950e3a978c73d7ca66f9b17c50f6947c",
    "standing": "6cde434a29ca6d7ee4a13ecbc86ad96440f37d68d041ea525a79ad54cbd2be4a",
    "window_predicate": "476b7df2ea8928ebada86f2c215b6e2f662146a906ec9a4d60e033bf9f1c1e16",
    "year_fill_feature": "3870d70b65acaccfbe5b59b7fa0195da75711bc6b2888974a1ad9d4aadde5d4d",
}


def _section_sha(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


class TestConfigPin(unittest.TestCase):
    def setUp(self):
        with open(PROD_CONFIG, encoding="utf-8") as f:
            self.cfg = json.load(f)

    def test_float_rel_tol_is_1e12(self):
        self.assertEqual(self.cfg["comparison"]["float_rel_tol"], 1e-12)
        self.assertEqual(A.REQUIRED_FLOAT_REL_TOL, 1e-12)

    def test_every_section_is_pinned_or_obs_only(self):
        self.assertEqual(set(self.cfg) - OBS_ONLY_SECTIONS, set(GATE_SECTION_SHA256),
                         "a config section was added or removed: classify and pin it")

    def test_gate_affecting_sections_unchanged(self):
        changed = sorted(k for k, h in GATE_SECTION_SHA256.items()
                         if k in self.cfg and _section_sha(self.cfg[k]) != h)
        self.assertEqual(changed, [], "gate-affecting config sections edited; a reviewed "
                                      "change must update GATE_SECTION_SHA256")

    def test_pin_covers_the_named_keys(self):
        for k in ("columns", "row_order", "regions_py", "comparison", "hash_spec",
                  "manifest_schema", "constants", "environment", "paths"):
            self.assertIn(k, GATE_SECTION_SHA256)
        self.assertIn("split_manifest_sections", self.cfg["columns"])
        self.assertIn("names", self.cfg["regions_py"])

    def test_loose_tolerance_config_is_rejected(self):
        c = copy.deepcopy(self.cfg)
        c["comparison"]["float_rel_tol"] = 1e-2
        p = os.path.join(TMP, "loose_tol.json")
        with open(p, "w") as f:
            json.dump(c, f)
        with self.assertRaises(A.ConfigError):
            A.load_config(p)
        self.assertNotEqual(_section_sha(c["comparison"]), GATE_SECTION_SHA256["comparison"])
        out = subprocess.run([sys.executable, os.path.join(REPO, "acceptance_split.py"),
                              "--config", p, "--data-root", BASE], capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("config refused", out.stdout)
        with self.assertRaises(A.ConfigError):
            A.standing_checks(64, 0, False, data_root=BASE, config=p)

    def test_loose_tolerance_would_let_an_attack_through(self):
        """Why the pin matters: a 1.005x weight scaling fails E10 at 1e-12."""
        root = fresh()
        emit_attack(root, WeightScale)
        res = gates(root, only={"E10"})
        self.assertEqual(res["E10"]["status"], "FAIL")
        self.assertTrue(any("'weight' differs" in x for x in res["E10"]["problems"]))


class TestUnits(unittest.TestCase):
    def test_order_key_spec(self):
        exp = int.from_bytes(hashlib.blake2b(b"42:-72.100000,44.100000", digest_size=8).digest(), "big")
        self.assertEqual(A.order_key(A.coord_text(-72.1, 44.1), 42), exp)
        self.assertEqual(A.coord_text(-72.1234567, 44.0000004), "-72.123457,44.000000")
        self.assertEqual(A.order_key("neg:" + A.coord_text(1, 2), 42),
                         int.from_bytes(hashlib.blake2b(b"42:neg:1.000000,2.000000",
                                                        digest_size=8).digest(), "big"))

    def test_draw_u(self):
        self.assertEqual(A.draw_u(0), 0.5 / 2**64)
        self.assertLess(A.draw_u(2**64 - 1), 1.0 + 1e-15)

    def test_block_ids_floor(self):
        cfg = {"constants": {"BLOCK_SIZE_M": 3000, "BLOCK_ORIGIN_5070": [0.0, 0.0]}}
        self.assertEqual(list(A.block_ids([-0.5, 2999.999, 3000.0], [0.0, -3000.0, -3000.1], cfg)),
                         ["-1_0", "0_-1", "1_-2"])

    def test_split_for_unassigned(self):
        h = int(hashlib.md5(b"42:5_7").hexdigest(), 16)
        self.assertEqual(A.md5_is_val("5_7", 42, 0.197), (h % 10000) < 0.197 * 10000)

    def test_round_half_even(self):
        self.assertEqual(A.py_round(2.5), 2)
        self.assertEqual(A.py_round(3.5), 4)
        self.assertEqual(A.py_round(0.2 * 12.5), 2)

    def test_thin_keeps_exactly_min_spacing(self):
        keep = A.thin_mask([0, 1], [0, 1], [0.0, 30.0], [0.0, 0.0], 42, 30)
        self.assertTrue(keep.all())
        keep = A.thin_mask([0, 1], [0, 1], [0.0, 29.999], [0.0, 0.0], 42, 30)
        self.assertEqual(keep.sum(), 1)
        k0 = A.order_key(A.coord_text(0, 0), 42)
        k1 = A.order_key(A.coord_text(1, 1), 42)
        self.assertEqual(bool(keep[0]), k0 < k1)

    def test_thin_is_order_free(self):
        rng = np.random.default_rng(3)
        lo, la = rng.uniform(0, 0.01, 300), rng.uniform(0, 0.01, 300)
        x, y = rng.uniform(0, 400, 300), rng.uniform(0, 400, 300)
        k = A.thin_mask(lo, la, x, y, 42, 30)
        p = rng.permutation(300)
        k2 = A.thin_mask(lo[p], la[p], x[p], y[p], 42, 30)
        self.assertTrue((k[p] == k2).all())

    def test_buffer_boundary_inclusive(self):
        d2 = A.min_d2_within([0.0, 0.0], [300.0, 300.0001], [0.0], [0.0], 300)
        self.assertEqual(d2[0], 90000.0)
        self.assertGreater(d2[1], 90000.0)

    def test_raster_path_nearest_and_fallback(self):
        r = A.Rasters(BASE, CFG)
        self.assertTrue(r.raster_path("ME", "evt", 2019).endswith("ME_2022_evt.tif"))
        self.assertTrue(r.raster_path("ME", "evt", 2030).endswith("ME_2023_evt.tif"))
        # sclass 2021 is on disk but empty: nearest (2021) fails validation -> most recent valid
        self.assertTrue(r.raster_path("ME", "sclass", 2019).endswith("ME_2023_sclass.tif"))
        self.assertTrue(r.raster_path("ME", "sclass", 2022).endswith("ME_2022_sclass.tif"))
        with self.assertRaises(A.ReplayError):
            r.raster_path("ME", "nosuchfeature", 2020)

    def test_nearest_year_tie_goes_earlier(self):
        tmp = tempfile.mkdtemp(dir=TMP)
        os.makedirs(os.path.join(tmp, "data", "landfire"))
        for y in (2020, 2022):
            os.symlink(os.path.realpath(os.path.join(BASE, "data/landfire/ME_2022_evt.tif")),
                       os.path.join(tmp, "data", "landfire", f"ME_{y}_evt.tif"))
        r = A.Rasters(tmp, CFG)
        self.assertTrue(r.raster_path("ME", "evt", 2021).endswith("ME_2020_evt.tif"))

    def test_window_predicate_edges(self):
        import rasterio
        r = A.Rasters(BASE, CFG)
        rel = r.raster_path("NH", "evt", 2022)
        with rasterio.open(os.path.join(BASE, rel)) as src:
            tr, w, h = src.transform, src.width, src.height
        from pyproj import Transformer
        inv = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
        # pixel centres at row = 32 (first valid) and row = 31 (first invalid), mid column
        pts = []
        for row in (32, 31, h - 32, h - 31):
            x, y = tr * (w // 2 + 0.5, row + 0.5)
            pts.append(inv.transform(x, y))
        ok = r.window_ok(rel, [p[0] for p in pts], [p[1] for p in pts])
        self.assertEqual(list(ok), [True, False, True, False])

    def test_dedup_smallest_gbif_id_and_two_state_raise(self):
        rep = A.Replay(BASE, CFG)
        df = pd.DataFrame({"longitude": [1.000001, 1.000002, 2.0], "latitude": [1.0, 1.0, 2.0],
                           "state": ["ME", "ME", "NH"], "gbif_id": [9, 3, 5], "region": ["ME", "ME", "NH"]})
        out = rep.dedup(df)
        self.assertEqual(sorted(out["gbif_id"]), [3, 5])
        df.loc[1, "state"] = "NH"
        with self.assertRaises(A.ReplayError):
            rep.dedup(df)

    def test_verify_partition(self):
        bad = A.verify_partition([-72.1, -72.1, -72.1, -72.605], [44.1, 44.1, 44.25, 44.1],
                                 ["ME", "NH", "ME", "VT"], BASE, CFG)
        self.assertEqual(list(bad), [False, True, True, True])

    def test_build_weight_four_bases(self):
        C = CFG["constants"]
        mm = {"a": {"Classification": "Landscape-Rare (x)", "Selection_Ratio": 5.0},
              "b": {"Classification": "Selected", "Selection_Ratio": float("nan")},
              "c": {"Classification": "Avoided", "Selection_Ratio": 0.01}}
        self.assertEqual(A.build_weight("a", mm, True, C), (10.0, "NonVeg (hard negative)"))
        self.assertEqual(A.build_weight("z", mm, False, C), (1.0, "Unknown envelope (neutral)"))
        self.assertEqual(A.build_weight("a", mm, False, C), (1.0, "Landscape-Rare (neutral)"))
        self.assertEqual(A.build_weight("b", mm, False, C), (0.1, "Selected (ratio undefined, min weight)"))
        self.assertEqual(A.build_weight("c", mm, False, C), (10.0, "Avoided"))
        self.assertEqual(sorted(CFG["envelope"]["weight_basis_strings"]),
                         sorted(["NonVeg (hard negative)", "Unknown envelope (neutral)",
                                 "Landscape-Rare (neutral)", "Selected (ratio undefined, min weight)"]))

    def test_envelope_id_and_binners(self):
        S = pd.DataFrame({"evh": [101.0, 110.0, 120.0, 125.0], "nonveg_landcover": [False] * 4})
        b = A.fit_scheme_binners(S, [("evh", "q2")])
        df = pd.DataFrame({"evt_phys": ["Conifer", "Hardwood"], "sclass": [3.0, 1.0],
                           "evh": [101.0, 125.0]})
        ids = A.build_envelope_id(df, [("evt_phys", "raw"), ("sclass", "raw"), ("evh", "q2")], b)
        self.assertEqual(list(ids), ["EVT_PHYS:Conifer|SCLASS:3|EVH:Q1", "EVT_PHYS:Hardwood|SCLASS:1|EVH:Q2"])

    def test_compare_frames_tolerance(self):
        a = pd.DataFrame({"longitude": [1.0], "latitude": [2.0], "w": [1.0 + 1e-13]})
        b = pd.DataFrame({"longitude": [1.0], "latitude": [2.0], "w": [1.0]})
        self.assertEqual(A.compare_frames(a, b, "coord", 1e-12, "t"), [])
        a["w"] = 1.0 + 1e-11
        self.assertTrue(A.compare_frames(a, b, "coord", 1e-12, "t"))

    def test_config_constants_complete(self):
        need = {"REGIONS", "MIN_SPACING_M", "BLOCK_SIZE_M", "BLOCK_ORIGIN_5070", "BUFFER_M",
                "VAL_FRACTION", "SPLIT_SEED", "WINDOW_PX", "NEG_RATIO", "NONVEG_MAX_FRAC",
                "W_FLOOR", "W_CAP", "NEUTRAL_WEIGHT", "NONVEG_WEIGHT", "MAX_COORD_UNCERTAINTY_M",
                "KEY_DECIMALS", "YEAR_MIN"}
        prod = A.load_config(PROD_CONFIG)
        self.assertEqual(set(prod["constants"]), need)
        self.assertEqual(prod["obs"]["OBS_Z"], 4)
        self.assertEqual(len(A.digested_paths(prod)), 20)
        self.assertEqual(len(A.standing_csv_paths(prod)), 18)

    def test_no_escape_flag(self):
        import argparse
        ap_opts = set()
        with open(os.path.join(REPO, "acceptance_split.py")) as f:
            src = f.read()
        for tok in ("--data-root", "--config", "--emit-reference", "--calibrate", "--standing"):
            self.assertIn(f'"{tok}"', src)
        import re
        ap_opts = set(re.findall(r'add_argument\("(--[a-z-]+)"', src))
        self.assertEqual(ap_opts, {"--data-root", "--config", "--emit-reference", "--calibrate",
                                   "--standing"})
        self.assertNotIn("os.environ", src)

    def test_independence_no_forbidden_imports(self):
        import ast
        with open(os.path.join(REPO, "acceptance_split.py")) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        forbidden = {"prepare_training_data", "generate_negatives", "analyze_grouse", "train",
                     "dataset", "models", "regions", "grouse_data"}
        self.assertEqual(mods & forbidden, set())
        third = mods - set(sys.stdlib_module_names)
        self.assertLessEqual(third, {"numpy", "pandas", "scipy", "pyproj", "rasterio", "geopandas"})

    def test_e1p_unit(self):
        root = fresh()
        self.assertEqual(gates(root, only={"E1p"})["E1p"]["status"], "PASS")
        p = os.path.join(root, A.rpath(CFG, "train_negatives", "VT"))
        df = pd.read_csv(p)
        df.iloc[::-1].to_csv(p, index=False)
        self.assertEqual(gates(root, only={"E1p"})["E1p"]["status"], "FAIL")

    def test_noncanonical_order_fails_R4(self):
        """CR-0013 v2.3 (user decision): canonical row order is a GATE in
        R1-R4. Correct rows, consistent parts (E1p passes), reversed order."""
        root = fresh()
        n = read(root, "negatives", "ME")
        write_set(root, A.N_KINDS, "ME", n.iloc[::-1])
        refresh_manifest(root)
        res = gates(root, only={"R4", "E1p"})
        self.assertEqual(res["E1p"]["status"], "PASS")
        self.assertEqual(res["R4"]["status"], "FAIL")
        self.assertTrue(any("canonical order" in x for x in res["R4"]["problems"]))
        self.assertFalse(any("rows not in the replay" in x or "differs" in x
                             for x in res["R4"]["problems"]))

    def test_noncanonical_order_fails_R1_R2_R3(self):
        root = fresh()
        p = read(root, "thinned_positives", "VT")
        # swap the first two rows: same content, one inversion
        p = pd.concat([p.iloc[[1, 0]], p.iloc[2:]], ignore_index=True)
        write_set(root, A.P_KINDS, "VT", p)
        b = read(root, "block_assignments")
        b.iloc[::-1].to_csv(os.path.join(root, A.rpath(CFG, "block_assignments")), index=False)
        c = read(root, "candidate_pool")
        c.sort_values(["longitude", "latitude"], kind="mergesort").to_csv(   # region not first
            os.path.join(root, A.rpath(CFG, "candidate_pool")), index=False)
        refresh_manifest(root)
        res = gates(root, only={"R1", "R2", "R3"})
        for g in ("R1", "R2", "R3"):
            self.assertEqual(res[g]["status"], "FAIL", g)
            self.assertTrue(all("canonical order" in x for x in res[g]["problems"]), res[g])

    def test_canonical_order_helper(self):
        df = pd.DataFrame({"region": ["ME", "ME", "NH"], "longitude": [1.0, 2.0, 0.0],
                           "latitude": [0.0, 0.0, 0.0]})
        self.assertEqual(A.canonical_order_problems(df, ["region", "longitude", "latitude"], "t"), [])
        self.assertTrue(A.canonical_order_problems(df, ["longitude", "latitude"], "t"))

    def test_manifest_environment_differs_from_config(self):
        """CR-0012 v2.2.1: the manifest records the environment actually
        used; E11 fails on any difference from the config."""
        for mutate in (lambda e: e.update(numpy="1.0.0"), lambda e: e.pop("GDAL"),
                       lambda e: e.update(extra_lib="9")):
            root = fresh()
            mp = os.path.join(root, A.rpath(CFG, "split_manifest"))
            with open(mp) as f:
                m = json.load(f)
            mutate(m["negatives"]["environment"])
            with open(mp, "w") as f:
                json.dump(m, f)
            res = gates(root, only={"E11"})
            self.assertEqual(res["E11"]["status"], "FAIL")
            self.assertTrue(any("environment (as used)" in x for x in res["E11"]["problems"]))

    def test_manifest_constants_as_used_differ(self):
        root = fresh()
        mp = os.path.join(root, A.rpath(CFG, "split_manifest"))
        with open(mp) as f:
            m = json.load(f)
        m["positives"]["constants"]["VAL_FRACTION"] = 0.25
        with open(mp, "w") as f:
            json.dump(m, f)
        res = gates(root, only={"E11"})
        self.assertEqual(res["E11"]["status"], "FAIL")
        self.assertTrue(any("VAL_FRACTION" in x for x in res["E11"]["problems"]))

    def test_manifest_environment_matches_measured(self):
        with open(os.path.join(BASE, A.rpath(CFG, "split_manifest"))) as f:
            m = json.load(f)
        self.assertEqual(m["positives"]["environment"], A.current_environment())
        self.assertEqual(set(A.current_environment()),
                         set(CFG["environment"]) - set(A.ENV_DESCRIPTIVE))
        for k in ("rasterio", "GDAL", "geopandas", "shapely", "pyogrio"):
            self.assertIn(k, CFG["environment"])

    def test_regions_py_county_year_checked(self):
        root = fresh()
        rp = os.path.join(TMP, f"regions_{_N[0]}.py")
        with open(rp, "w") as f:
            f.write(REGIONS_PY.replace("COUNTY_POLYGONS_YEAR = 2023", "COUNTY_POLYGONS_YEAR = 2025"))
        with open(CFG_PATH) as f:
            c = json.load(f)
        c["regions_py"]["path"] = rp
        p = os.path.join(TMP, "cy.json")
        with open(p, "w") as f:
            json.dump(c, f)
        res = gates(root, only={"E11"}, cfg=A.load_config(p))
        self.assertEqual(res["E11"]["status"], "FAIL")
        self.assertTrue(any("COUNTY_POLYGONS_YEAR" in x for x in res["E11"]["problems"]))

    def test_county_path_from_template(self):
        self.assertEqual(A.county_rel(CFG), "data/roads/tl_2023_us_county.zip")
        c = copy.deepcopy(CFG)
        c["paths"]["county_polygons"]["year"] = 2024
        with self.assertRaises(A.ReplayError):
            A.county_rel(c)
        c = copy.deepcopy(CFG)
        c["paths"]["county_polygons"]["where"] = "STATEFP IN ('23','33')"
        with self.assertRaises(A.ReplayError):
            A.county_rel(c)

    def test_manifest_counts_checked(self):
        root = fresh()
        mp = os.path.join(root, A.rpath(CFG, "split_manifest"))
        with open(mp) as f:
            m = json.load(f)
        m["positives"]["counts"]["ME"]["3"] += 1
        m["negatives"]["counts"]["NH"]["6"] -= 1
        with open(mp, "w") as f:
            json.dump(m, f)
        res = gates(root, only={"R1", "R3"})
        self.assertEqual(res["R1"]["status"], "FAIL")
        self.assertEqual(res["R3"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
