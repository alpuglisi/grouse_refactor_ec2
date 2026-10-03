"""Single source of truth for the project's spatial and region-domain
constants (PA-0001; CR-0007 section 1). Every other module imports these;
tests/test_shared_constants.py pins the values and scans the tree for
literal copies.

BOXES: (min_lon, min_lat, max_lon, max_lat), ~0.1 deg buffer around each
state's observed sighting extent. See BUG-0001 for why this exists as its
own module instead of being duplicated per-script (it previously drifted to
two different NH max_lon values across 7 files).

BOXES are RASTER REQUEST EXTENTS, not region membership. The boxes overlap
(neighbouring states' records fall inside each other's box), so a sighting
record's region is its `state` column, checked against the county polygons
by `verify_partition` / `in_state` below (CR-0007; BUG-0027).

NOTE: the NH max_lon value below (-70.600) was chosen as the majority
value across the prior duplicated copies, not verified against the real
sighting-data extent (no data/ tree was available in the environment that
made this fix). Confirm against real NH sighting data before relying on
this for a production run; update here (one place) if it needs to change.
"""
import hashlib

import numpy as np

REGIONS = ("ME", "NH", "VT")

STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}

STATE_NAMES = {"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"}

# TIGER/Line roads vintage; the value is owned by CR-0014.
TIGER_YEAR = 2023

# Vintage of the TIGER county polygons used for region membership. Pinned
# independently of TIGER_YEAR (CR-0007 section 1).
COUNTY_POLYGONS_YEAR = 2023

# Minimum spacing between kept points when thinning (metres).
MIN_SPACING_M = 30

# Spatial block edge for train/val block assignment (metres); matches
# analyze_grouse.KDE_BANDWIDTH_M.
BLOCK_SIZE_M = 3000

# Exclusion radius around every grouse location for candidate negatives
# (metres).
BUFFER_M = 300

# CR-0012 section 1: the one global block grid and the pooled split.
# Origin of the global block grid in EPSG:5070 metres.
BLOCK_ORIGIN_5070 = (0.0, 0.0)

# Target share of pooled thinned positives placed in validation blocks.
VAL_FRACTION = 0.2

# The only seed source of the split/thin/draw hashes; no CLI seed.
SPLIT_SEED = 42

# Side of the square window every training record must have in bounds on
# every feature raster (train.IMG_SIZE + 2 x default jitter 0).
WINDOW_PX = 64

# CR-0019 section 2: the one year floor for BOTH label classes, applied at
# selection (positives step 2, before thinning; pool step 1). It is the
# first year both classes were acquired (get_negatives.py fetches from it),
# and the first year with every FEATURE_SPEC raster within train.py's
# default --max-year-gap of 2. Positive ACQUISITION (sightings.py/ebird.py
# START_YEAR) stays earlier: the buffer and the envelope metrics still use
# every sighting year. train.filter_by_year_gap refuses, never drops, so a
# tolerance change needs a reviewed change of this constant (which
# regenerates the split files).
YEAR_MIN = 2020

# CR-0021 section 2 B: the year strata of the negative draw. Each (region,
# split) draws, per stratum, as many negatives as it has positives, so the
# two classes' year distributions are equal per stratum. A pure literal
# (E11 reads it with ast.literal_eval): increasing, contiguous, from
# YEAR_MIN. The value is the pre-registration's choice (S1, single years;
# docs/quality/evidence/CR-0021/preregister.txt); changing it is a reviewed
# change that regenerates the negatives.
YEAR_STRATA = ((2020,), (2021,), (2022,), (2023,), (2024,))


def year_stratum(year):
    """Index of the YEAR_STRATA stratum holding `year`; ValueError for any
    other year (a year outside the strata fails closed)."""
    for i, stratum in enumerate(YEAR_STRATA):
        if year in stratum:
            return i
    raise ValueError(f"year {year!r} lies in no stratum of YEAR_STRATA "
                     f"{YEAR_STRATA} (CR-0021)")

BOXES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.600, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}

# CRS of the TIGER county file (NAD83), of the lon/lat inputs (WGS84) and
# of the analysis grid (CONUS Albers). _ANALYSIS_EPSG is used only for
# domain D; to_5070 below still hard-codes its own "EPSG:5070" target, and
# the two must stay equal (tests/test_cr0017.py pins this; wiring to_5070
# to a shared constant is CR-0007 item (d)).
_COUNTY_FILE_EPSG = 4269
_LONLAT_EPSG = 4326
_ANALYSIS_EPSG = 5070

# Dissolved state polygons, {region: GeoDataFrame row}, read once.
_STATE_POLYGONS = {}


def _county_polygons():
    """(path, GeoDataFrame) of the TIGER COUNTY_POLYGONS_YEAR county
    polygons whose STATEFP is in STATE_FIPS, in the FILE CRS (EPSG:4269
    if the file has none). The one reader of the county file: both
    _state_polygons() and the CR-0017 domain D use it."""
    import geopandas as gpd
    from grouse_data import PATH_TEMPLATES
    path = PATH_TEMPLATES["tiger_county"].format(year=COUNTY_POLYGONS_YEAR)
    codes = ",".join(f"'{v}'" for v in sorted(STATE_FIPS.values()))
    counties = gpd.read_file(path, where=f"STATEFP IN ({codes})")
    if counties.crs is None:
        counties = counties.set_crs(_COUNTY_FILE_EPSG)
    return path, counties


def _state_polygons():
    """GeoDataFrame, one dissolved (multi)polygon per STATEFP in
    STATE_FIPS, in EPSG:4326, with a `region` column. Cached."""
    if "gdf" not in _STATE_POLYGONS:
        path, counties = _county_polygons()
        states = counties[["STATEFP", "geometry"]].dissolve(by="STATEFP")
        states = states.to_crs(_LONLAT_EPSG).reset_index()
        by_fips = {v: k for k, v in STATE_FIPS.items()}
        states["region"] = states["STATEFP"].map(by_fips)
        missing = set(STATE_FIPS) - set(states["region"])
        if missing:
            raise RuntimeError(f"{path}: no county polygons for {sorted(missing)}")
        _STATE_POLYGONS["gdf"] = states[["region", "geometry"]]
    return _STATE_POLYGONS["gdf"]


def _polygon_region(lon, lat):
    """Region whose dissolved county polygon contains each point (predicate
    `within`), or None where the point lies in no polygon."""
    import geopandas as gpd
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    pts = gpd.GeoDataFrame(
        {"_i": np.arange(len(lon))},
        geometry=gpd.points_from_xy(lon, lat), crs=_LONLAT_EPSG)
    hit = gpd.sjoin(pts, _state_polygons(), how="left", predicate="within")
    if hit["_i"].duplicated().any():
        raise RuntimeError("points inside two states' county polygons")
    reg = hit.sort_values("_i")["region"]
    return np.array([r if isinstance(r, str) else None for r in reg], dtype=object)


# CR-0017 section 2: the sightings' acquisition domain D in EPSG:5070,
# built once.
_DOMAIN_5070 = {}


def _domain_5070():
    """Domain D (CR-0017 section 2): the union of the STATE_FIPS county
    polygons, projected from the file CRS straight to EPSG:5070 (no
    EPSG:4326 step). Raises if a STATE_FIPS state has no county or D has
    no area. Cached."""
    if "geom" not in _DOMAIN_5070:
        import shapely
        path, counties = _county_polygons()
        missing = set(STATE_FIPS.values()) - set(counties["STATEFP"])
        if missing:
            raise RuntimeError(f"{path}: no county polygons for STATEFP "
                               f"{sorted(missing)}")
        geom = shapely.union_all(
            counties.to_crs(_ANALYSIS_EPSG).geometry.to_numpy())
        if geom.is_empty or geom.area <= 0:
            raise RuntimeError(f"{path}: domain D is empty")
        _DOMAIN_5070["geom"] = geom
    return _DOMAIN_5070["geom"]


def domain_edge_m(x, y, *, domain=None):
    """edge_m of each EPSG:5070 point (CR-0017 section 2): its distance
    to the boundary of domain D if D contains it, else 0.0. x, y must
    come from to_5070 of lon/lat. `domain` (a shapely polygon in EPSG:5070
    metres) replaces D - the test seam; None builds D from the county
    file. Returns a float64 array."""
    import shapely
    x = np.atleast_1d(np.asarray(x, dtype=np.float64))
    y = np.atleast_1d(np.asarray(y, dtype=np.float64))
    if x.shape != y.shape:
        raise ValueError(f"x and y differ in shape: {x.shape} vs {y.shape}")
    geom = _domain_5070() if domain is None else domain
    out = np.zeros(x.shape, dtype=np.float64)
    if x.size == 0:
        return out
    shapely.prepare(geom)
    inside = shapely.contains_xy(geom, x, y)
    if inside.any():
        edge = geom.boundary
        shapely.prepare(edge)
        pts = shapely.points(x[inside], y[inside])
        out[inside] = shapely.distance(pts, edge)
    return out


def verify_partition(lon, lat, state):
    """Records whose county-polygon state differs from `state`, or that lie
    in no county polygon, as a DataFrame (longitude, latitude, state,
    polygon_state; index = position in the input). Empty when every record
    lies inside its own state's polygons."""
    import pandas as pd
    state = np.asarray(state, dtype=object)
    poly = _polygon_region(lon, lat)
    bad = np.array([p is None or p != s for p, s in zip(poly, state)],
                   dtype=bool)
    idx = np.flatnonzero(bad)
    return pd.DataFrame({
        "longitude": np.asarray(lon, dtype=float)[idx],
        "latitude": np.asarray(lat, dtype=float)[idx],
        "state": state[idx],
        "polygon_state": poly[idx],
    }, index=idx)


def in_state(lon, lat, region):
    """Boolean array: point lies inside `region`'s county polygons (same
    polygons and predicate as verify_partition)."""
    poly = _polygon_region(lon, lat)
    return np.array([p == region for p in poly], dtype=bool)


# ---------------------------------------------------------------------------
# CR-0012 section 1 helpers: block ids, hash order, window predicate.
# ---------------------------------------------------------------------------
def block_ids(x, y):
    """Global block id of each EPSG:5070 point:
    f"{floor((x-x0)/BLOCK_SIZE_M)}_{floor((y-y0)/BLOCK_SIZE_M)}" with
    (x0, y0) = BLOCK_ORIGIN_5070. The only block-id function (CR-0012
    section 1). Accepts scalars or array-likes; returns a list of str."""
    x = np.atleast_1d(np.asarray(x, dtype=np.float64))
    y = np.atleast_1d(np.asarray(y, dtype=np.float64))
    x0, y0 = BLOCK_ORIGIN_5070
    bx = np.floor((x - x0) / BLOCK_SIZE_M).astype(np.int64)
    by = np.floor((y - y0) / BLOCK_SIZE_M).astype(np.int64)
    return [f"{a}_{b}" for a, b in zip(bx.tolist(), by.tolist())]


# The one EPSG:4326 -> EPSG:5070 transform (CR-0015 section 1; PA-0001).
_TO_5070 = {}


def to_5070(lon, lat):
    """EPSG:4326 lon/lat -> EPSG:5070 (x, y), float64 arrays (always_xy).
    The transform behind every x_5070/y_5070, distance and block id
    (CR-0015 section 1). Accepts scalars or array-likes."""
    if "t" not in _TO_5070:
        from pyproj import Transformer
        _TO_5070["t"] = Transformer.from_crs("EPSG:4326", "EPSG:5070",
                                             always_xy=True)
    x, y = _TO_5070["t"].transform(np.asarray(lon, dtype=np.float64),
                                   np.asarray(lat, dtype=np.float64))
    return (np.atleast_1d(np.asarray(x, dtype=np.float64)),
            np.atleast_1d(np.asarray(y, dtype=np.float64)))


def block_split(block_ids, assignments):
    """"train"/"val" per block id (CR-0015 section 1): the block's split
    in `assignments` (the block_assignments.csv DataFrame, columns
    block_id and split) if the block is listed there; otherwise "val" iff
    int(md5(f"{SPLIT_SEED}:{block_id}"), 16) % 10_000 < vf * 10_000, with
    vf = (assignments.split == "val").mean(). No file I/O. Returns an
    object array, one entry per block id."""
    split = dict(zip(assignments["block_id"], assignments["split"]))
    vf = float((assignments["split"] == "val").mean())
    out = []
    for b in block_ids:
        if b in split:
            out.append(split[b])
            continue
        h = int(hashlib.md5(f"{SPLIT_SEED}:{b}".encode()).hexdigest(), 16)
        out.append("val" if (h % 10_000) < vf * 10_000 else "train")
    return np.array(out, dtype=object)


def coord_text(lon, lat):
    """The hash text of a coordinate: f"{lon:.6f},{lat:.6f}"."""
    return f"{float(lon):.6f},{float(lat):.6f}"


def order_key(text):
    """Seeded 64-bit hash order of `text` (CR-0012 section 1):
    int.from_bytes(blake2b(f"{SPLIT_SEED}:{text}", digest_size=8), "big")."""
    return int.from_bytes(
        hashlib.blake2b(f"{SPLIT_SEED}:{text}".encode(),
                        digest_size=8).digest(), "big")


def window_in_bounds(src, x, y):
    """True where the WINDOW_PX x WINDOW_PX window centred as dataset.py
    centres it lies inside raster `src` (CR-0012 section 1). x, y are in
    the raster's own CRS. (row, col) = rowcol(src.transform, x, y),
    rounding down as dataset.py's src.index does; h = WINDOW_PX // 2; the
    window is [row-h, row-h+WINDOW_PX) x [col-h, col-h+WINDOW_PX). Nodata
    inside the window is not considered. Returns a bool array."""
    from rasterio.transform import rowcol
    x = np.atleast_1d(np.asarray(x, dtype=np.float64))
    y = np.atleast_1d(np.asarray(y, dtype=np.float64))
    if len(x) == 0:
        return np.zeros(0, dtype=bool)
    rows, cols = rowcol(src.transform, x, y)
    rows = np.asarray(rows, dtype=np.int64)
    cols = np.asarray(cols, dtype=np.int64)
    h = WINDOW_PX // 2
    r0, c0 = rows - h, cols - h
    return ((r0 >= 0) & (r0 + WINDOW_PX <= src.height)
            & (c0 >= 0) & (c0 + WINDOW_PX <= src.width))
