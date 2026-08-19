import os
import re
import glob
import pandas as pd
import numpy as np
import rasterio
from sklearn.neighbors import KernelDensity
from pyproj import Transformer
import matplotlib.pyplot as plt

# ==========================================
# 1. CONFIGURATION
# ==========================================
DATA_DIR = "./"                  # Directory containing your sighting CSVs
RASTER_DIR = "data/landfire"   # Output folder created by download.py

# Bounding boxes MUST match BOXES_COORDINATES in download.py
# (min_lon, min_lat, max_lon, max_lat)
BOXES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.600, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}

REGIONS_TO_RUN = list(BOXES.keys())

# KDE bandwidth in meters, per region.
KDE_BANDWIDTH_M = {
    "ME": 3000,
    "NH": 3000,
    "VT": 3000,
}

# --- KDE MODE -------------------------------------------------------------
# "spatial"    : classic 2D lon/lat density (previous behavior).
# "stratified" : a SEPARATE spatial KDE per macro habitat class
#                (STRATIFY_BY), with hotspot/coldspot percentiles computed
#                WITHIN each class. "Hotspot" then means "dense relative to
#                other locations of the same habitat type" - the cleanest
#                way to put a macro feature into the density estimate while
#                keeping the result interpretable.
# "joint"      : one multivariate KDE over (x, y, env features). Each env
#                feature is standardized and scaled by JOINT_ENV_SCALE_M,
#                which sets how many meters of spatial separation "equals"
#                one standard deviation of environmental difference. High
#                density then means many locations that are close in space
#                AND environmentally similar.
KDE_MODE = "stratified"
STRATIFY_BY = "evt_phys"              # macro class column for stratified mode
MIN_STRATUM_FOR_KDE = 30              # strata smaller than this get no zones
JOINT_ENV_FEATURES = ["evh", "evc", "ch", "cc"]
JOINT_ENV_SCALE_M = 3000              # 1 SD of env difference == this many meters

# --- ENVELOPE SCHEME ------------------------------------------------------
# Aspect removed per analysis decision (not a meaningful criterion here).
# evt_phys is LANDFIRE's macro physiognomy class (Hardwood, Conifer,
# Grassland, Riparian, ...) mapped from raw EVT codes via the attribute
# tables fetched by download_attribute_tables.py.
#
# Scheme below is the tune_envelope_bins.py winner re-validated AFTER the
# duplicate-location collapse and macro-class columns were added: #1 in ME
# and a near-tied #2 in NH/VT (both within 3% of that region's own top
# score) - the most consistent cross-region result seen across every
# tuning round so far. Re-validate again if the underlying data changes
# materially (more years added, dedup threshold changed, etc.).
# Each entry: (column, variant) where variant is "raw" or "qN" (quantile).
ENVELOPE_SCHEME = [
    ("evt_phys", "raw"),
    ("sclass", "raw"),
    ("evh", "q2"),
]

# --- USED-VS-AVAILABLE SELECTION ANALYSIS ----------------------------------
# Envelope importance is judged by a selection ratio, not raw sighting
# counts: w = (share of sightings in envelope) / (share of LANDSCAPE that
# is that envelope), with availability estimated from random background
# points sampled across the region's rasters. This separates two things
# that raw counts conflate: envelopes with few sightings because the
# habitat barely exists (landscape-rare), vs envelopes with few sightings
# despite abundant habitat (genuinely avoided - "rare to see a grouse").
BACKGROUND_N = 20000        # random background points per region
MIN_AVAIL_BG = 15           # background hits needed to classify selection
SELECT_W_HI = 2.0           # w >= this -> 'Selected'
SELECT_W_LO = 0.5           # w <= this -> 'Avoided'

# Features exactly as named by download.py: {region}_{year}_{feature}.tif
FEATURES = ["evt", "evh", "evc", "sclass", "fdist", "ch", "cc"]

NODATA_SENTINELS = {-9999, -32768, 32767, -1111}
# -1111 confirmed as SClass's nodata value (e.g. Open Water pixels have
# no succession class) - it wasn't in this set, so it passed through
# sample_raster as a literal value instead of becoming NaN. Real
# sightings almost never land on those specific cells, so this was
# invisible on the sightings side; 20,000 random background points hit
# them constantly, manufacturing fake 'SCLASS:-1111' envelopes with 0
# sightings but real availability -> spurious Selection_Ratio=0.00
# entries that dominated the Avoided table without being real avoidance.

COLUMN_FOR_FEATURE = {
    "evt": "evt", "evh": "evh", "evc": "evc", "sclass": "sclass",
    "fdist": "fdist", "ch": "ch", "cc": "cc",
}

# Features a record MUST have to survive extraction. FDist is deliberately
# excluded: in LANDFIRE's fuel-disturbance product, undisturbed areas can
# carry nodata rather than a "no disturbance" class - requiring FDist
# would silently delete every undisturbed location. Instead FDist NaN is
# filled with FDIST_NONE below.
REQUIRED_FEATURES = ["evt", "evh", "evc", "sclass", "ch", "cc"]
FDIST_NONE = -1   # fdist value meaning "no disturbance mapped / nodata"

# LANDFIRE's five fixed non-succession SClass codes (LF SClass Attribute
# Data Dictionary): valid across every BpS model.
NON_VEG_SCLASS_CODES = {111, 112, 120, 132, 180}
NON_VEG_SCLASS_LABELS = {
    111: "Water", 112: "Snow/Ice", 120: "Urban",
    132: "Barren/Sparse", 180: "Agriculture",
}

# EVT_PHYS prefixes that are unambiguously not grouse habitat regardless
# of what raw SClass code happens to accompany them - the SClass-only
# filter above misses these when a record's per-BPS SClass integer isn't
# one of the 5 universal fixed non-veg codes (confirmed real: 'Developed'
# + a non-fixed SClass code was ranking as the MOST SELECTED envelope in
# all three states, which is not plausible grouse ecology). Deliberately
# does NOT include 'Exotic Herbaceous'/'Exotic Tree-Shrub'/'Shrubland'/
# 'Grassland'/'Sparsely Vegetated' - those ARE vegetated and could be
# genuine (if marginal) early-successional/edge habitat; excluding them
# is a judgment call, not a data-quality fix, so it's left to a separate
# explicit decision rather than folded in here silently.
EVT_PHYS_NONVEG_PREFIXES = (
    "Developed", "Open Water", "Barren", "Agriculture",
    "Quarries", "Snow", "Ice",
)


def is_evt_phys_nonveg(evt_phys_series):
    pattern = "|".join(EVT_PHYS_NONVEG_PREFIXES)
    return evt_phys_series.astype(str).str.contains(pattern, case=False, na=False)

# Precision used to identify "the same physical location" (~1.1m).
COORD_ROUND_DECIMALS = 5

# --- MAP RENDERING ---------------------------------------------------------
# State boundary lines: fetched once from the US Census cartographic
# boundary files (1:20m generalized) and cached under MAP_DATA_DIR. Any
# .geojson or .shp you drop into MAP_DATA_DIR yourself is used instead.
# Requires geopandas (pip install geopandas); degrades to no boundaries
# with a warning if unavailable.
MAP_DATA_DIR = "./map_data"
STATE_BOUNDARY_URL = ("https://www2.census.gov/geo/tiger/GENZ2023/shp/"
                      "cb_2023_us_state_20m.zip")
MAP_SURFACE_GRID_N = 150      # density surface resolution (N x N grid)
MAP_SURFACE_ALPHA = 0.5       # opacity of the KDE gradient layer


# ==========================================
# 2. LOAD ALL SIGHTING DATA (once, shared across regions)
# ==========================================
def box_count(lon, lat, box):
    a, b, c, d = box
    return int(((lon >= a) & (lon <= c) & (lat >= b) & (lat <= d)).sum())


def load_all_sightings():
    print("Loading sighting data...")
    all_files = glob.glob(os.path.join(DATA_DIR, "data/sightings/*_sightings_*.csv"))
    fname_re = re.compile(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$")

    df_list = []
    for file in sorted(all_files):
        m = fname_re.match(os.path.basename(file))
        if not m:
            print(f"  [!] Skipping unrecognized filename: {os.path.basename(file)}")
            continue
        state, year = m.group(1).upper(), int(m.group(2))

        df = pd.read_csv(file)
        lon_col = next((c for c in df.columns if 'lon' in c.lower()), None)
        lat_col = next((c for c in df.columns if 'lat' in c.lower()), None)
        if not (lon_col and lat_col):
            print(f"  [!] No lon/lat columns found in {os.path.basename(file)}. Skipping.")
            continue

        df = df.rename(columns={lon_col: 'longitude', lat_col: 'latitude'})
        df['state'] = state
        df['year'] = year
        df_list.append(df[['longitude', 'latitude', 'state', 'year']])

    if not df_list:
        raise SystemExit("No sighting CSVs loaded. Expected files like me_sightings_2016.csv")

    sightings = pd.concat(df_list, ignore_index=True).dropna(subset=['longitude', 'latitude'])
    print(f"Loaded {len(sightings):,} total sightings across all files.")

    if (sightings['longitude'] > 0).mean() > 0.9:
        flipped_hits = sum(box_count(-sightings['longitude'], sightings['latitude'], b)
                           for b in BOXES.values())
        if flipped_hits > 0:
            print("[~] Longitudes are positive but match the boxes when negated - "
                 "assuming west-hemisphere data and flipping sign.")
            sightings['longitude'] = -sightings['longitude']

    return sightings


def clip_to_region(sightings, region):
    min_lon, min_lat, max_lon, max_lat = BOXES[region]
    in_box = (
        sightings['longitude'].between(min_lon, max_lon) &
        sightings['latitude'].between(min_lat, max_lat)
    )
    n_in = int(in_box.sum())
    print(f"{n_in:,} sightings fall inside {region} "
          f"({min_lon} {min_lat} {max_lon} {max_lat}).")

    if n_in == 0:
        lon, lat = sightings['longitude'], sightings['latitude']
        print("\nDIAGNOSTICS - no sightings matched the box:")
        print(f"  Sighting data extent: lon [{lon.min():.4f}, {lon.max():.4f}], "
              f"lat [{lat.min():.4f}, {lat.max():.4f}]")
        for name, box in BOXES.items():
            print(f"  {name} {box}: {box_count(lon, lat, box):,} inside | "
                  f"{box_count(-lon, lat, box):,} if lon sign flipped | "
                  f"{box_count(lat, lon, box):,} if lat/lon swapped")
        print(f"\n  Skipping {region} - no overlap with sighting data.\n")
        return None

    return sightings[in_box].reset_index(drop=True)


def collapse_duplicate_locations(sightings, round_decimals=COORD_ROUND_DECIMALS):
    """Collapse repeated visits to the same coordinate into one record per
    unique location (confirmed reused-pin artifact: 59-76% of records in
    each state were repeat visits; within KDE hotspots, 97-98%). The
    representative record per location is its most recent year. n_visits/
    first_year/last_year are kept as metadata, unused for weighting."""
    coords = sightings[['longitude', 'latitude']].round(round_decimals)
    group_key = coords['longitude'].astype(str) + "," + coords['latitude'].astype(str)

    sightings = sightings.copy()
    sightings['_loc_key'] = group_key

    visit_stats = sightings.groupby('_loc_key')['year'].agg(
        n_visits='count', first_year='min', last_year='max')

    rep_idx = sightings.groupby('_loc_key')['year'].idxmax()
    collapsed = sightings.loc[rep_idx].copy()
    collapsed = collapsed.merge(visit_stats, left_on='_loc_key', right_index=True)
    collapsed = collapsed.drop(columns=['_loc_key']).reset_index(drop=True)

    n_before, n_after = len(sightings), len(collapsed)
    pct = 100 * (n_before - n_after) / n_before if n_before else 0.0
    print(f"  Collapsing repeated visits to the same location: "
         f"{n_before:,} records -> {n_after:,} unique locations "
         f"({pct:.1f}% were repeat visits to an already-seen coordinate).")
    return collapsed


# ==========================================
# 3. RASTER + ATTRIBUTE-TABLE HELPERS
# ==========================================
def available_years(region, feature):
    years = []
    pattern = re.compile(rf"^{region}_(\d{{4}})_{feature}\.tif$")
    for p in glob.glob(os.path.join(RASTER_DIR, f"{region}_*_{feature}.tif")):
        m = pattern.match(os.path.basename(p))
        if m:
            years.append(int(m.group(1)))
    return sorted(set(years))


def pick_raster_year(sighting_year, years_on_disk):
    return min(years_on_disk, key=lambda y: (abs(y - sighting_year), y))


_transformers = {}
def _get_transformer(crs):
    key = crs.to_string()
    if key not in _transformers:
        _transformers[key] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return _transformers[key]


def sample_raster(tif_path, lons, lats):
    out = np.full(len(lons), np.nan)
    if not os.path.exists(tif_path):
        return out
    with rasterio.open(tif_path) as src:
        xs, ys = _get_transformer(src.crs).transform(np.asarray(lons), np.asarray(lats))
        xs, ys = np.asarray(xs), np.asarray(ys)
        b = src.bounds
        inside = (xs >= b.left) & (xs <= b.right) & (ys >= b.bottom) & (ys <= b.top)
        idx = np.where(inside)[0]
        if len(idx) == 0:
            return out
        vals = np.array([v[0] for v in src.sample(zip(xs[idx], ys[idx]))], dtype=float)
        if src.nodata is not None:
            vals[vals == src.nodata] = np.nan
        for sentinel in NODATA_SENTINELS:
            vals[vals == sentinel] = np.nan
        out[idx] = vals
    return out


def load_evt_crosswalk(raster_dir):
    """Load the newest LANDFIRE EVT attribute table (from
    download_attribute_tables.py) and return VALUE -> macro-class maps:
      phys  : EVT_PHYS  (~10 broad physiognomy classes - Hardwood,
              Conifer, Grassland, Riparian, Developed, ...)
      group : EVT_GP_N  (collapsed vegetation-type group name, coarser
              than raw EVT but finer than physiognomy)
    Returns None if no table is on disk."""
    files = sorted(glob.glob(os.path.join(raster_dir, "attribute_tables", "LF*_EVT.csv")))
    if not files:
        return None
    path = files[-1]  # lexicographic sort puts the newest LF year last
    try:
        tbl = pd.read_csv(path)
    except Exception as e:
        print(f"  [!] Could not read {path}: {e}")
        return None
    tbl.columns = [c.upper().strip() for c in tbl.columns]
    if "VALUE" not in tbl.columns or "EVT_PHYS" not in tbl.columns:
        print(f"  [!] {os.path.basename(path)} lacks VALUE/EVT_PHYS columns.")
        return None
    phys = dict(zip(tbl["VALUE"].astype(int), tbl["EVT_PHYS"].astype(str)))
    group_col = "EVT_GP_N" if "EVT_GP_N" in tbl.columns else "EVT_PHYS"
    group = dict(zip(tbl["VALUE"].astype(int), tbl[group_col].astype(str)))
    return {"phys": phys, "group": group, "source": os.path.basename(path)}


def background_nonveg_rate(region, feature_years, evt_xwalk, n_samples=3000, seed=0):
    if not feature_years.get('sclass') or not feature_years.get('evt'):
        return None
    sclass_yr = max(feature_years['sclass'])
    evt_yr = max(feature_years['evt'])
    sclass_tif = os.path.join(RASTER_DIR, f"{region}_{sclass_yr}_sclass.tif")
    evt_tif = os.path.join(RASTER_DIR, f"{region}_{evt_yr}_evt.tif")
    if not os.path.exists(sclass_tif) or not os.path.exists(evt_tif):
        return None
    rng = np.random.default_rng(seed)
    min_lon, min_lat, max_lon, max_lat = BOXES[region]
    lons = rng.uniform(min_lon, max_lon, n_samples)
    lats = rng.uniform(min_lat, max_lat, n_samples)
    sclass_vals = sample_raster(sclass_tif, lons, lats)
    evt_vals = sample_raster(evt_tif, lons, lats)
    both_valid = ~np.isnan(sclass_vals) & ~np.isnan(evt_vals)
    sclass_vals, evt_vals = sclass_vals[both_valid], evt_vals[both_valid]
    if len(sclass_vals) == 0:
        return None
    sclass_nonveg = np.isin(sclass_vals, list(NON_VEG_SCLASS_CODES))
    if evt_xwalk is not None:
        phys = pd.Series(evt_vals.astype(int)).map(evt_xwalk['phys']).fillna("Unmapped")
        phys_nonveg = is_evt_phys_nonveg(phys).values
    else:
        phys_nonveg = np.zeros(len(evt_vals), dtype=bool)
    nonveg = sclass_nonveg | phys_nonveg
    return float(nonveg.mean()), len(sclass_vals)


def coarse_quantile_bin(series, n_bins=4):
    """Data-driven quantile bins labeled Q1 (lowest) .. Qn (highest)."""
    try:
        binned = pd.qcut(series, q=n_bins, labels=False, duplicates='drop')
        return binned.map(lambda v: f"Q{int(v) + 1}" if pd.notna(v) else "NA").astype(str)
    except ValueError:
        return series.astype(int).astype(str)


def fit_scheme_binners(df, scheme):
    """Fit quantile bin EDGES on the sightings for every qN entry in the
    scheme. Critical for used-vs-available: background points must be
    binned with the SIGHTINGS' edges - re-quantiling the background
    independently would force it into equal quarters by construction and
    corrupt the availability estimate."""
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
    labels = [f"Q{i + 1}" for i in range(len(edges) - 1)]
    return pd.cut(series, bins=edges, labels=labels,
                  include_lowest=True).astype(str)


def build_envelope_id(df, scheme, binners=None):
    """Concatenate the configured (column, variant) pairs into envelope
    ids like 'EVT_PHYS:Hardwood|SCLASS:4|EVH:Q1'. When binners (from
    fit_scheme_binners) are provided, qN columns use those fitted edges;
    otherwise edges are fit on df itself."""
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


def background_envelope_sample(region, feature_years, evt_xwalk, binners,
                               n_samples=BACKGROUND_N, seed=1):
    """Estimate landscape AVAILABILITY of each envelope: sample random
    points across the region's bbox, extract the same feature stack used
    for sightings (most recent raster year per feature), drop nodata and
    non-vegetated SClass cells, and build envelope ids with the SAME
    scheme and the sightings-fitted bin edges. Returns a value_counts of
    envelope ids among vegetated background points, or None if required
    rasters are missing."""
    needed = {col for col, _ in ENVELOPE_SCHEME if col not in ("evt_phys", "evt_group")}
    needed |= {"sclass"}                      # for the non-veg filter
    if any(c for c, _ in ENVELOPE_SCHEME if c in ("evt_phys", "evt_group")):
        needed |= {"evt"}
    for feat in needed:
        if not feature_years.get(feat):
            print(f"    [bg] unavailable: no '{feat}' rasters on disk for {region}.")
            return None

    rng = np.random.default_rng(seed)
    min_lon, min_lat, max_lon, max_lat = BOXES[region]
    lons = rng.uniform(min_lon, max_lon, n_samples)
    lats = rng.uniform(min_lat, max_lat, n_samples)

    bg = pd.DataFrame({"longitude": lons, "latitude": lats})
    MIN_VALID_FRAC = 0.05   # below this, treat the year as broken, not
                            # just "sparse coverage", and fall back
    for feat in needed:
        years_desc = sorted(feature_years[feat], reverse=True)
        chosen_yr, vals, n_valid = None, None, 0
        for yr in years_desc:
            tif = os.path.join(RASTER_DIR, f"{region}_{yr}_{feat}.tif")
            candidate = sample_raster(tif, lons, lats)
            n_valid = int(pd.notna(candidate).sum())
            if n_valid >= n_samples * MIN_VALID_FRAC:
                chosen_yr, vals = yr, candidate
                break
            print(f"    [bg] {feat} {yr} ({os.path.basename(tif)}): "
                 f"only {n_valid:,}/{n_samples:,} valid - treating as "
                 f"broken/unusable, trying an older year instead of "
                 f"assuming newest=usable.")
        if vals is None:
            print(f"    [bg] unavailable: every year of '{feat}' "
                 f"({years_desc}) failed the sampling sanity check for "
                 f"{region}. Run check_raster_health.py on these files - "
                 f"this is very likely a corrupted/empty raster, not a "
                 f"code bug (sclass and other features sampled fine).")
            return None
        bg[feat] = vals
        print(f"    [bg] {feat} ({region}_{chosen_yr}_{feat}.tif): "
             f"{n_valid:,}/{n_samples:,} points sampled valid")
    # Same FDist policy as the sightings side: NaN means undisturbed/
    # nodata, not a missing record - fill, don't drop, so used and
    # available sets stay comparable if fdist joins the envelope scheme.
    if 'fdist' in bg.columns:
        bg['fdist'] = bg['fdist'].fillna(FDIST_NONE)
    n_before_dropna = len(bg)
    bg = bg.dropna()
    if len(bg) == 0:
        print(f"    [bg] unavailable: all {n_before_dropna:,} background "
             f"points had a NaN in at least one of {sorted(needed)} - "
             f"likely a CRS/extent mismatch between rasters, not missing files.")
        return None
    # evt_phys computed BEFORE the non-veg filter, since the filter now
    # checks it too (must match the sightings-side logic exactly, or
    # 'used' and 'available' would be applying different habitat
    # definitions and the selection ratio would be meaningless).
    if evt_xwalk is not None and 'evt' in bg.columns:
        bg['evt_phys'] = bg['evt'].astype(int).map(evt_xwalk['phys']).fillna("Unmapped")
        bg['evt_group'] = bg['evt'].astype(int).map(evt_xwalk['group']).fillna("Unmapped")
    else:
        bg['evt_phys'] = "Unmapped"
        bg['evt_group'] = "Unmapped"
    n_before_nonveg = len(bg)
    bg = bg[~(bg['sclass'].isin(NON_VEG_SCLASS_CODES) | is_evt_phys_nonveg(bg['evt_phys']))]
    if len(bg) == 0:
        print(f"    [bg] unavailable: all {n_before_nonveg:,} valid "
             f"background points were non-vegetated - implausible "
             f"for a real state; check the sclass/evt rasters.")
        return None
    return build_envelope_id(bg, ENVELOPE_SCHEME, binners=binners).value_counts()


# ==========================================
# 4. KDE MODES
# ==========================================
def kde_spatial(df, bw):
    """Classic 2D spatial density; global percentiles."""
    kde = KernelDensity(bandwidth=bw, kernel='gaussian')
    X = df[['x_5070', 'y_5070']].values
    kde.fit(X)
    density = np.exp(kde.score_samples(X))
    return pd.Series(density, index=df.index), _global_zones(pd.Series(density, index=df.index))


def kde_joint(df, bw):
    """One multivariate KDE over (x, y, standardized env features scaled
    to 'equivalent meters'). High density = many locations that are close
    in space AND environmentally similar."""
    cols = [c for c in JOINT_ENV_FEATURES if c in df.columns]
    feats = df[cols].astype(float)
    std = feats.std(ddof=0).replace(0, 1.0)
    z = (feats - feats.mean()) / std * JOINT_ENV_SCALE_M
    X = np.column_stack([df['x_5070'].values, df['y_5070'].values, z.values])
    kde = KernelDensity(bandwidth=bw, kernel='gaussian')
    kde.fit(X)
    density = np.exp(kde.score_samples(X))
    print(f"  [joint mode] Env features in kernel: {cols}; "
         f"1 SD of feature difference == {JOINT_ENV_SCALE_M} m of spatial "
         f"distance. 'Hotspot' = dense in combined space+environment.")
    return pd.Series(density, index=df.index), _global_zones(pd.Series(density, index=df.index))


def kde_stratified(df, bw):
    """A separate spatial KDE per macro habitat class (STRATIFY_BY), with
    percentile zones computed WITHIN each class. 'Hotspot' = dense
    relative to other locations of the same habitat type."""
    density = pd.Series(np.nan, index=df.index)
    zones = pd.Series('Moderate Density (10-90%)', index=df.index)
    small_strata = []
    for stratum, grp in df.groupby(STRATIFY_BY):
        if len(grp) < MIN_STRATUM_FOR_KDE:
            small_strata.append((stratum, len(grp)))
            continue
        kde = KernelDensity(bandwidth=bw, kernel='gaussian')
        X = grp[['x_5070', 'y_5070']].values
        kde.fit(X)
        d = np.exp(kde.score_samples(X))
        density.loc[grp.index] = d
        p10, p90 = np.percentile(d, 10), np.percentile(d, 90)
        zones.loc[grp.index[d <= p10]] = 'Coldest 10%'
        zones.loc[grp.index[d >= p90]] = 'Hotspot 10%'
    print(f"  [stratified mode] Separate KDE per '{STRATIFY_BY}' class; "
         f"hotspot/coldspot percentiles computed within each class.")
    if small_strata:
        listing = ", ".join(f"{s} (n={n})" for s, n in small_strata)
        print(f"    Strata below {MIN_STRATUM_FOR_KDE} records got no "
             f"density/zones (left as Moderate): {listing}")
    return density, zones


def _global_zones(density):
    zones = pd.Series('Moderate Density (10-90%)', index=density.index)
    p10, p90 = np.percentile(density, 10), np.percentile(density, 90)
    zones[density <= p10] = 'Coldest 10%'
    zones[density >= p90] = 'Hotspot 10%'
    return zones


# ==========================================
# 5. MAP HELPERS
# ==========================================
_BOUNDARY_UNLOADED = object()
_state_boundaries_cache = _BOUNDARY_UNLOADED

def load_state_boundaries():
    """Load US state boundary polygons for map context. Uses any .geojson
    or .shp already placed in MAP_DATA_DIR; otherwise downloads the Census
    1:20m cartographic boundary zip once and caches it. Returns a
    geopandas GeoDataFrame in EPSG:4326, or None (with a warning) if
    geopandas is missing or the download fails - the map still renders,
    just without boundary lines."""
    global _state_boundaries_cache
    if _state_boundaries_cache is not _BOUNDARY_UNLOADED:
        return _state_boundaries_cache
    _state_boundaries_cache = None
    try:
        import geopandas as gpd
    except ImportError:
        print("  [!] geopandas not installed - state boundaries skipped. "
             "Run: pip install geopandas")
        return None
    os.makedirs(MAP_DATA_DIR, exist_ok=True)
    zip_path = os.path.join(MAP_DATA_DIR, os.path.basename(STATE_BOUNDARY_URL))
    candidates = ([p for p in [zip_path] if os.path.exists(p)]
                  + sorted(glob.glob(os.path.join(MAP_DATA_DIR, "*.geojson")))
                  + sorted(glob.glob(os.path.join(MAP_DATA_DIR, "*.shp"))))
    src = candidates[0] if candidates else None
    if src is None:
        try:
            import urllib.request
            print(f"  Downloading state boundaries to {zip_path} (one-time)...")
            urllib.request.urlretrieve(STATE_BOUNDARY_URL, zip_path)
            src = zip_path
        except Exception as e:
            print(f"  [!] Could not download state boundaries ({e}). "
                 f"Map renders without them; to fix, place any state "
                 f"boundary .geojson/.shp in {MAP_DATA_DIR}/")
            return None
    try:
        gdf = gpd.read_file(src)
        if gdf.crs is not None and str(gdf.crs) != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        _state_boundaries_cache = gdf
        print(f"  State boundaries loaded from {os.path.basename(src)} "
             f"({len(gdf)} polygons).")
        return gdf
    except Exception as e:
        print(f"  [!] Could not read boundary file {src}: {e}")
        return None


def visualization_density_surface(valid, box, bw, grid_n=MAP_SURFACE_GRID_N):
    """A 2D spatial KDE evaluated on a regular grid, rendered as the
    PERCENTILE RANK of density (0-100) rather than raw density. Raw KDE
    values are extremely long-tailed - a few cells near the tightest
    clusters sit 50-100x above the median, so a linear color scale
    collapses everything else into one shade. Percentile rank uses the
    full colormap and speaks the same language as the hotspot/coldspot
    scores, which are percentile-defined.

    NOTE: this is always the plain SPATIAL density of unique observation
    locations, regardless of KDE_MODE - stratified/joint densities aren't
    comparable across strata/feature-space and can't be drawn as one
    surface. The markers still follow the configured mode."""
    min_lon, min_lat, max_lon, max_lat = box
    lon_g = np.linspace(min_lon, max_lon, grid_n)
    lat_g = np.linspace(min_lat, max_lat, grid_n)
    lon2d, lat2d = np.meshgrid(lon_g, lat_g)
    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    xs, ys = to_albers.transform(lon2d.ravel(), lat2d.ravel())
    kde = KernelDensity(bandwidth=bw, kernel='gaussian', rtol=1e-3)
    kde.fit(valid[['x_5070', 'y_5070']].values)
    d = np.exp(kde.score_samples(np.column_stack([xs, ys])))
    # Percentile-rank transform (0-100) across all grid cells.
    order = d.argsort().argsort()
    pct = 100.0 * order / max(len(d) - 1, 1)
    pct = pct.reshape(grid_n, grid_n)
    d = d.reshape(grid_n, grid_n)
    # Mask cells with effectively zero raw density (empty corners/ocean)
    # so they stay uncolored rather than reading as "0th percentile".
    pct = np.ma.masked_where(d < d.max() * 0.005, pct)
    return lon2d, lat2d, pct


def rare_envelope_contours(rare, box, bw, grid_n=MAP_SURFACE_GRID_N):
    """KDE surface over ONLY the bottom-10%-envelope records, for drawing
    contour lines that outline where rare-envelope habitat concentrates
    ('swaths'). Returns (lon2d, lat2d, density) or None if too few
    records to contour meaningfully."""
    if len(rare) < 20:
        return None
    min_lon, min_lat, max_lon, max_lat = box
    lon_g = np.linspace(min_lon, max_lon, grid_n)
    lat_g = np.linspace(min_lat, max_lat, grid_n)
    lon2d, lat2d = np.meshgrid(lon_g, lat_g)
    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    xs, ys = to_albers.transform(lon2d.ravel(), lat2d.ravel())
    kde = KernelDensity(bandwidth=bw, kernel='gaussian', rtol=1e-3)
    kde.fit(rare[['x_5070', 'y_5070']].values)
    d = np.exp(kde.score_samples(np.column_stack([xs, ys]))).reshape(grid_n, grid_n)
    return lon2d, lat2d, d


# ==========================================
# 6. PER-REGION PIPELINE
# ==========================================
def analyze_region(region, sightings_all, evt_xwalk):
    print(f"\n##########################################")
    print(f"# REGION: {region}")
    print(f"##########################################")

    sightings = clip_to_region(sightings_all, region)
    if sightings is None:
        return None
    sightings = collapse_duplicate_locations(sightings)

    print("Transforming coordinates to EPSG:5070 (CONUS Albers)...")
    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    sightings['x_5070'], sightings['y_5070'] = to_albers.transform(
        sightings['longitude'].values, sightings['latitude'].values
    )

    # --- Environmental extraction (now BEFORE KDE: stratified/joint modes
    # need the environmental features) --------------------------------
    print(f"\nExtracting environmental features from {RASTER_DIR}/ ...")
    feature_years = {f: available_years(region, f) for f in FEATURES}
    for f, yrs in feature_years.items():
        print(f"  {f:9s}: rasters on disk for years {yrs if yrs else 'NONE'}")
    missing = [f for f, yrs in feature_years.items() if not yrs]
    if missing:
        print(f"  [!] No rasters found for {missing} in {region}. Skipping.\n")
        return None

    for col in COLUMN_FOR_FEATURE.values():
        sightings[col] = np.nan

    for year in sorted(sightings['year'].unique()):
        mask = sightings['year'] == year
        pts = sightings[mask]
        if len(pts) == 0:
            continue
        lons, lats = pts['longitude'].values, pts['latitude'].values
        for feature in FEATURES:
            r_year = pick_raster_year(year, feature_years[feature])
            tif = os.path.join(RASTER_DIR, f"{region}_{r_year}_{feature}.tif")
            sightings.loc[mask, COLUMN_FOR_FEATURE[feature]] = sample_raster(tif, lons, lats)

    required_cols = [COLUMN_FOR_FEATURE[f] for f in REQUIRED_FEATURES]
    valid = sightings.dropna(subset=required_cols).copy()
    n_fdist_none = int(valid['fdist'].isna().sum())
    valid['fdist'] = valid['fdist'].fillna(FDIST_NONE)
    if n_fdist_none:
        print(f"  {n_fdist_none:,} records have no FDist value (undisturbed "
             f"or nodata) - filled with {FDIST_NONE} rather than dropped, "
             f"since requiring FDist would delete every undisturbed location.")
    print(f"Successfully extracted full feature stacks for "
          f"{len(valid):,} of {len(sightings):,} records.")
    if len(valid) == 0:
        print(f"  [!] All {region} records dropped during extraction. Skipping.\n")
        return None

    # --- Macro habitat classes from the EVT attribute table ------------
    if evt_xwalk is not None:
        valid['evt_phys'] = valid['evt'].astype(int).map(evt_xwalk['phys']).fillna("Unmapped")
        valid['evt_group'] = valid['evt'].astype(int).map(evt_xwalk['group']).fillna("Unmapped")
        n_unmapped = int((valid['evt_phys'] == "Unmapped").sum())
        print(f"  Macro classes mapped from {evt_xwalk['source']}: "
             f"{valid['evt_phys'].nunique()} physiognomy classes"
             + (f" ({n_unmapped:,} records unmapped)" if n_unmapped else ""))
    else:
        valid['evt_phys'] = "Unmapped"
        valid['evt_group'] = "Unmapped"
        print("  [!] No EVT attribute table found under "
             f"{RASTER_DIR}/attribute_tables/ - run "
             f"download_attribute_tables.py first. Macro classes set to "
             f"'Unmapped'; stratified KDE will degrade to a single stratum.")

    # --- Non-vegetated landcover flagging ------------------------------
    sclass_nonveg = valid['sclass'].isin(NON_VEG_SCLASS_CODES)
    phys_nonveg = is_evt_phys_nonveg(valid['evt_phys'])
    valid['nonveg_landcover'] = sclass_nonveg | phys_nonveg
    n_nonveg = int(valid['nonveg_landcover'].sum())
    pct_nonveg = 100 * n_nonveg / len(valid)
    n_phys_only = int((phys_nonveg & ~sclass_nonveg).sum())
    print(f"\n[data quality] {n_nonveg:,} of {len(valid):,} records "
          f"({pct_nonveg:.1f}%) fall on non-vegetated land cover - "
          f"excluded from the habitat-envelope analysis, kept in the full "
          f"CSV with a 'nonveg_landcover' flag and written to "
          f"data/pipeline/nonveg_flagged_{region}.csv.")
    if n_phys_only > 0:
        print(f"    ({n_phys_only:,} of those caught only by EVT_PHYS "
             f"({'/'.join(EVT_PHYS_NONVEG_PREFIXES)}) - their raw SClass "
             f"code wasn't one of the 5 universal fixed non-veg values, "
             f"so the SClass-only filter would have missed them.)")
    if n_nonveg > 0:
        breakdown = (valid.loc[sclass_nonveg, 'sclass']
                    .map(NON_VEG_SCLASS_LABELS).value_counts())
        for label, cnt in breakdown.items():
            print(f"    {label}: {cnt:,}")
        if n_phys_only > 0:
            phys_breakdown = valid.loc[phys_nonveg & ~sclass_nonveg, 'evt_phys'].value_counts()
            for label, cnt in phys_breakdown.items():
                print(f"    {label} (via EVT_PHYS): {cnt:,}")
    bg = background_nonveg_rate(region, feature_years, evt_xwalk)
    if bg is not None:
        frac_bg, n_bg = bg
        print(f"    Landscape baseline (random background sample, n={n_bg:,}): "
              f"{frac_bg * 100:.1f}% non-vegetated.")
        if pct_nonveg > 0 and frac_bg > 0:
            enrichment = (pct_nonveg / 100) / frac_bg
            verdict = (" -> suggests a location-precision artifact."
                      if enrichment > 1.5 else
                      " -> roughly consistent with landscape composition.")
            print(f"    Sightings land on non-veg cover {enrichment:.1f}x the "
                  f"landscape baseline rate{verdict}")
    valid.loc[valid['nonveg_landcover']].to_csv(
        f"data/pipeline/nonveg_flagged_{region}.csv", index=False)

    # --- KDE stage (mode-dependent) ------------------------------------
    bw = KDE_BANDWIDTH_M.get(region, 1000)
    print(f"\nKDE stage: mode='{KDE_MODE}', bandwidth={bw} m, on "
          f"{len(valid):,} unique locations...")
    print("  [methods note] Repeat visits were collapsed upstream. "
         "Remaining known bias: observer effort grew over 2016-2024, so "
         "more DISTINCT locations get reported in recent years regardless "
         "of grouse density - 'well-covered by observers' still inflates "
         "apparent density.")
    if KDE_MODE == "spatial":
        valid['spatial_density'], valid['spatial_zone'] = kde_spatial(valid, bw)
    elif KDE_MODE == "joint":
        valid['spatial_density'], valid['spatial_zone'] = kde_joint(valid, bw)
    elif KDE_MODE == "stratified":
        valid['spatial_density'], valid['spatial_zone'] = kde_stratified(valid, bw)
    else:
        raise ValueError(f"Unknown KDE_MODE '{KDE_MODE}'")

    # --- Envelope binning (habitat records only) ------------------------
    habitat = valid[~valid['nonveg_landcover']].copy()
    if len(habitat) == 0:
        print(f"  [!] All {region} records were non-vegetated. Skipping envelopes.\n")
        return valid, None

    print(f"\nBinning multi-feature envelopes "
         f"(scheme: {' + '.join(f'{c}({v})' for c, v in ENVELOPE_SCHEME)})...")
    binners = fit_scheme_binners(habitat, ENVELOPE_SCHEME)
    habitat['envelope_id'] = build_envelope_id(habitat, ENVELOPE_SCHEME,
                                               binners=binners)

    env_counts = habitat['envelope_id'].value_counts()
    n_singleton = int((env_counts == 1).sum())
    print(f"    Envelope cardinality check: {len(env_counts):,} distinct envelopes "
          f"for {len(habitat):,} habitat records (median "
          f"{int(env_counts.median())} sightings/envelope, {n_singleton:,} "
          f"singletons = {100 * n_singleton / max(len(env_counts), 1):.0f}%).")

    # --- Used vs available: selection ratios ----------------------------
    # Raw sighting counts conflate 'few sightings because the habitat
    # barely exists' (landscape-rare) with 'few sightings despite abundant
    # habitat' (avoided - genuinely rare to see a grouse there). The
    # selection ratio w = used_share / available_share separates them,
    # with availability estimated from BACKGROUND_N random points across
    # the region binned with the SIGHTINGS' own quantile edges.
    print(f"    Sampling {BACKGROUND_N:,} background points for envelope "
         f"availability...")
    bg_counts = background_envelope_sample(region, feature_years, evt_xwalk,
                                           binners)
    env_df = pd.DataFrame({'Envelope': env_counts.index,
                           'Sightings': env_counts.values})
    if bg_counts is not None:
        bg_df = pd.DataFrame({'Envelope': bg_counts.index,
                              'Avail_N': bg_counts.values})
        env_df = env_df.merge(bg_df, on='Envelope', how='outer')
        env_df[['Sightings', 'Avail_N']] = env_df[['Sightings', 'Avail_N']].fillna(0).astype(int)
        used_total, avail_total = env_df['Sightings'].sum(), env_df['Avail_N'].sum()
        env_df['Used_Pct'] = 100 * env_df['Sightings'] / used_total
        env_df['Avail_Pct'] = 100 * env_df['Avail_N'] / avail_total
        with np.errstate(divide='ignore', invalid='ignore'):
            env_df['Selection_Ratio'] = np.where(
                env_df['Avail_Pct'] > 0,
                env_df['Used_Pct'] / env_df['Avail_Pct'], np.nan)

        def classify(row):
            if row['Avail_N'] < MIN_AVAIL_BG:
                return 'Landscape-Rare (availability too low to judge)'
            if row['Selection_Ratio'] >= SELECT_W_HI:
                return 'Selected'
            if row['Selection_Ratio'] <= SELECT_W_LO:
                return 'Avoided'
            return 'Proportional'
        env_df['Classification'] = env_df.apply(classify, axis=1)

        n_bg_veg = int(avail_total)
        print(f"    Availability from {n_bg_veg:,} vegetated background points; "
             f"classification thresholds: Selected w>={SELECT_W_HI}, "
             f"Avoided w<={SELECT_W_LO}, min {MIN_AVAIL_BG} background hits.")
        cls_counts = env_df['Classification'].value_counts()
        print("    " + ", ".join(f"{c}: {n}" for c, n in cls_counts.items()))

        env_df = env_df.sort_values('Sightings', ascending=False).reset_index(drop=True)
        print(f"\nTOP 5 ENVELOPES BY SIGHTINGS ({region}) - now with selection context:")
        print(env_df.head(5)[['Envelope', 'Sightings', 'Avail_Pct',
                              'Selection_Ratio', 'Classification']].to_string(
            index=False, float_format=lambda x: f"{x:.2f}"))

        judged = env_df[env_df['Avail_N'] >= MIN_AVAIL_BG]
        sel = judged.sort_values('Selection_Ratio', ascending=False)
        print(f"\nMOST SELECTED ENVELOPES ({region}) - used far above availability:")
        print(sel.head(5)[['Envelope', 'Sightings', 'Avail_Pct',
                           'Selection_Ratio']].to_string(
            index=False, float_format=lambda x: f"{x:.2f}"))
        print(f"\nMOST AVOIDED ENVELOPES ({region}) - abundant habitat, few "
             f"sightings ('rare to see a grouse'):")
        print(sel.tail(5).iloc[::-1][['Envelope', 'Sightings', 'Avail_Pct',
                                      'Selection_Ratio']].to_string(
            index=False, float_format=lambda x: f"{x:.2f}"))
        n_lrare = int((env_df['Classification']
                       .str.startswith('Landscape-Rare')).sum())
        print(f"\n{n_lrare} envelopes are landscape-rare (too little availability "
             f"to judge selection) - these are NOT necessarily poor habitat.")

        cls_map = dict(zip(env_df['Envelope'], env_df['Classification']))
        habitat['env_zone'] = habitat['envelope_id'].map(cls_map)
        habitat.loc[habitat['env_zone'].str.startswith('Landscape-Rare'),
                    'env_zone'] = 'Landscape-Rare Envelope'
        habitat['env_zone'] = habitat['env_zone'].map({
            'Selected': 'Selected Envelope',
            'Avoided': 'Avoided Envelope',
            'Proportional': 'Proportional Envelope',
            'Landscape-Rare Envelope': 'Landscape-Rare Envelope',
        }).fillna('Proportional Envelope')
    else:
        print("    [!] Background sampling unavailable (see [bg] diagnostic "
             "above for the actual reason) - falling back to count-based "
             "bottom-10% labeling, which CANNOT distinguish landscape-rare "
             "from avoided habitat.")
        env_df['Percentage'] = 100 * env_df['Sightings'] / len(habitat)
        env_df = env_df.sort_values('Sightings', ascending=True).reset_index(drop=True)
        env_df['Cum_Sum_Pct'] = env_df['Percentage'].cumsum()
        bottom = env_df[env_df['Cum_Sum_Pct'] <= 10.0]
        habitat['env_zone'] = 'Proportional Envelope'
        habitat.loc[habitat['envelope_id'].isin(bottom['Envelope']),
                    'env_zone'] = 'Avoided Envelope'

    # --- Avoided-envelope x spatial-zone overlap diagnostic -------------
    rare = habitat[habitat['env_zone'] == 'Avoided Envelope']
    if len(rare) > 0:
        base_hot = (habitat['spatial_zone'] == 'Hotspot 10%').mean()
        base_cold = (habitat['spatial_zone'] == 'Coldest 10%').mean()
        rare_hot = (rare['spatial_zone'] == 'Hotspot 10%').mean()
        rare_cold = (rare['spatial_zone'] == 'Coldest 10%').mean()
        print(f"\nAvoided-envelope / spatial-zone overlap ({region}):")
        print(f"    Of {len(rare):,} avoided-envelope records: "
              f"{rare_hot * 100:.1f}% are hotspots "
              f"(vs {base_hot * 100:.1f}% of all habitat records"
              + (f", {rare_hot / base_hot:.1f}x enrichment)" if base_hot > 0 else ")"))
        print(f"    {rare_cold * 100:.1f}% are coldspots "
              f"(vs {base_cold * 100:.1f}% baseline"
              + (f", {rare_cold / base_cold:.1f}x)" if base_cold > 0 else ")"))

    # Macro-class distribution report (replaces the old aspect diagnostic)
    if evt_xwalk is not None:
        hot = habitat[habitat['spatial_zone'] == 'Hotspot 10%']
        if len(hot) > 0:
            print(f"\nMacro class (EVT_PHYS) distribution within hotspots ({region}):")
            for cls, pct in (hot['evt_phys'].value_counts(normalize=True) * 100).items():
                print(f"    {cls}: {pct:.1f}%")

    valid = valid.merge(habitat[['env_zone', 'envelope_id']],
                        left_index=True, right_index=True, how='left')
    valid['env_zone'] = valid['env_zone'].fillna('Non-Vegetated (excluded)')

    # --- Mapping ---
    print(f"\nGenerating diagnostic map for {region}...")
    fig, ax = plt.subplots(figsize=(12, 10))
    min_lon, min_lat, max_lon, max_lat = BOXES[region]

    # 1. KDE density gradient rendered as percentile rank (0-100), 50%
    #    opacity - see visualization_density_surface docstring.
    lon2d, lat2d, dsurf = visualization_density_surface(valid, BOXES[region], bw)
    mesh = ax.pcolormesh(lon2d, lat2d, dsurf, cmap='viridis', vmin=0, vmax=100,
                         alpha=MAP_SURFACE_ALPHA, shading='auto', zorder=1)
    cbar = fig.colorbar(mesh, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label('Observation density percentile (spatial KDE)', fontsize=9)

    # 2. State boundary lines for geographic context.
    boundaries = load_state_boundaries()
    if boundaries is not None:
        boundaries.boundary.plot(ax=ax, color='dimgray', linewidth=0.9,
                                 zorder=2)

    # 3. Avoided-envelope swaths: contours of a KDE fit on only the
    #    records in AVOIDED envelopes (abundant habitat, few sightings) -
    #    the genuine 'rare to see a grouse' areas.
    rare_pts = valid[valid['env_zone'] == 'Avoided Envelope']
    rare_surf = rare_envelope_contours(rare_pts, BOXES[region], bw)
    if rare_surf is not None:
        rlon, rlat, rd = rare_surf
        # Levels as fractions of the surface max: a lone point peaks far
        # below a genuine multi-point concentration, so this outlines
        # only true swaths instead of ringing every isolated record.
        levels = rd.max() * np.array([0.35, 0.6, 0.85])
        ax.contour(rlon, rlat, rd, levels=levels,
                   colors='darkorange', linewidths=[0.8, 1.2, 1.8],
                   alpha=0.9, zorder=6)
        from matplotlib.lines import Line2D
        rare_proxy = Line2D([0], [0], color='darkorange', linewidth=1.5,
                            label='Avoided-envelope swaths (density contours)')
    else:
        rare_proxy = None

    # 3. Point layers (unchanged semantics).
    base = valid[valid['spatial_zone'] == 'Moderate Density (10-90%)']
    ax.scatter(base['longitude'], base['latitude'], c='lightgray', s=5,
               alpha=0.3, label='Moderate Density', zorder=3)
    hot = valid[valid['spatial_zone'] == 'Hotspot 10%']
    ax.scatter(hot['longitude'], hot['latitude'], c='red', s=10,
               alpha=0.6, label='Spatial Hotspots (Top 10%)', zorder=4)
    cold = valid[valid['spatial_zone'] == 'Coldest 10%']
    ax.scatter(cold['longitude'], cold['latitude'], c='blue', s=10,
               alpha=0.6, label='Spatial Coldspots (Lowest 10%)', zorder=4)
    marginal = valid[valid['env_zone'] == 'Avoided Envelope']
    ax.scatter(marginal['longitude'], marginal['latitude'], c='yellow',
               marker='x', s=20, alpha=0.8,
               label='Avoided Envelopes (habitat abundant, sightings scarce)',
               zorder=5)
    lrare = valid[valid['env_zone'] == 'Landscape-Rare Envelope']
    ax.scatter(lrare['longitude'], lrare['latitude'], c='magenta',
               marker='+', s=22, alpha=0.8,
               label='Landscape-Rare Envelopes (too little habitat to judge)',
               zorder=5)
    nonveg = valid[valid['nonveg_landcover']]
    ax.scatter(nonveg['longitude'], nonveg['latitude'], c='black',
               marker='.', s=8, alpha=0.4, label='Non-Vegetated (excluded)',
               zorder=3)

    pad_lon = (max_lon - min_lon) * 0.02
    pad_lat = (max_lat - min_lat) * 0.02
    ax.set_xlim(min_lon - pad_lon, max_lon + pad_lon)
    ax.set_ylim(min_lat - pad_lat, max_lat + pad_lat)
    ax.set_title(f"Ruffed Grouse Diagnostic Map [{region}] (KDE mode: {KDE_MODE})",
                 fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    handles, labels = ax.get_legend_handles_labels()
    if rare_proxy is not None:
        handles.append(rare_proxy)
        labels.append(rare_proxy.get_label())
    ax.legend(handles, labels, loc='lower right')
    ax.grid(True, linestyle='--', alpha=0.4)
    fig.tight_layout()
    map_name = f"data/maps/grouse_diagnostic_map_{region}.png"
    fig.savefig(map_name, dpi=300)
    plt.close(fig)
    print(f"Map saved as '{map_name}'")

    valid.to_csv(f"data/pipeline/evaluated_sightings_{region}.csv", index=False)
    env_df.to_csv(f"data/pipeline/envelope_metrics_{region}.csv", index=False)
    print(f"Saved evaluated_sightings_{region}.csv, envelope_metrics_{region}.csv, "
          f"data/pipeline/nonveg_flagged_{region}.csv")

    return valid, env_df


# ==========================================
# 6. RUN ALL REGIONS
# ==========================================
if __name__ == "__main__":
    sightings_all = load_all_sightings()
    evt_xwalk = load_evt_crosswalk(RASTER_DIR)
    if evt_xwalk is None:
        print("[!] No EVT attribute table found - macro classes unavailable. "
             "Run download_attribute_tables.py to enable them.")
    results = {}
    for region in REGIONS_TO_RUN:
        results[region] = analyze_region(region, sightings_all, evt_xwalk)

    print(f"\n##########################################")
    print(f"# SUMMARY (KDE mode: {KDE_MODE})")
    print(f"##########################################")
    for region in REGIONS_TO_RUN:
        r = results.get(region)
        if r is None:
            print(f"  {region}: skipped (see log above)")
        else:
            valid, _ = r
            n_hab = int((~valid['nonveg_landcover']).sum())
            print(f"  {region}: {len(valid):,} unique locations "
                  f"({n_hab:,} vegetated habitat, {len(valid) - n_hab:,} non-veg)")

