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

BOXES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.600, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}

# CRS of the TIGER county file (NAD83) and of the lon/lat inputs (WGS84).
_COUNTY_FILE_EPSG = 4269
_LONLAT_EPSG = 4326

# Dissolved state polygons, {region: GeoDataFrame row}, read once.
_STATE_POLYGONS = {}


def _state_polygons():
    """GeoDataFrame, one dissolved (multi)polygon per STATEFP in
    STATE_FIPS, in EPSG:4326, with a `region` column. Cached."""
    if "gdf" not in _STATE_POLYGONS:
        import geopandas as gpd
        from grouse_data import PATH_TEMPLATES
        path = PATH_TEMPLATES["tiger_county"].format(year=COUNTY_POLYGONS_YEAR)
        codes = ",".join(f"'{v}'" for v in sorted(STATE_FIPS.values()))
        counties = gpd.read_file(path, where=f"STATEFP IN ({codes})")
        if counties.crs is None:
            counties = counties.set_crs(_COUNTY_FILE_EPSG)
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
