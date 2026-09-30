"""
prepare_training_data.py

Turns evaluated_sightings_{region}.csv (for every region in
regions.REGIONS, pooled) into ML-ready positives, WITHOUT modifying those
files. CR-0012 section 2 ("Positives") is the specification; each step
below is a deterministic, order-free function of the inputs, so that
acceptance_split.py (CR-0013) can replay it exactly.

1. Load every region's evaluated sightings; raise unless
   state == region == R on every row.
2. Raise if any row (habitat or not) has a null year. Keep the habitat
   rows (~nonveg_landcover) whose year >= regions.YEAR_MIN (CR-0019): the
   one year floor for both classes, applied before thinning so a
   pre-floor point cannot win the thin order over a kept neighbour.
   evaluated_sightings_* themselves keep every year (the negatives'
   buffer and the envelope metrics use them all).
3. Drop rows whose WINDOW_PX window is not inside every FEATURE_SPEC
   raster (regions.window_in_bounds; nodata inside the window is not
   considered).
4. THINNING, pooled over all regions: visit rows by ascending
   order_key(coord), ties by lon then lat; keep a row iff its squared
   EPSG:5070 distance to every kept row is >= MIN_SPACING_M**2. Two
   distinct nearby coordinates can land in the same pixel and produce
   near-identical feature vectors - an unintentional per-location
   sample weight, not new information.
5. SPATIAL BLOCK HOLDOUT on ONE global grid (regions.block_ids): visit
   occupied blocks by ascending order_key(block_id) and add whole blocks
   to validation until the pooled record count reaches
   round(VAL_FRACTION x N). Blocking whole cells keeps spatially
   autocorrelated neighbours out of opposite splits; pooling keeps the
   guarantee across region borders (BUG-0027).
6. Write the per-region files and the one global block table, all
   canonically sorted, each via a same-directory temp file + os.replace,
   then the `positives` section of the split manifest. Any existing
   `negatives` manifest section and acceptance_record.json are removed:
   the negatives must be regenerated and re-accepted.

Outputs (PATH_TEMPLATES), none of which overwrite evaluated_sightings_*:
    thinned_positives_{region}.csv   - post-thin positives + block_id, split
    train_positives_{region}.csv     - its split == 'train' rows
    val_positives_{region}.csv       - its split == 'val' rows
    block_assignments.csv            - global block_id -> split, n
    split_manifest.json              - `positives` section (CR-0013 schema)

Usage (no flags; always every region in regions.REGIONS):
    python prepare_training_data.py
"""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile

import numpy as np
import pandas as pd
from pyproj import Transformer

import regions
# BUG-0001 / PA-0025: every spatial and split constant is defined once, in
# regions.py; CR-0012 removed this script's *_DEFAULT copies and flags.
from regions import (REGIONS, MIN_SPACING_M, BLOCK_SIZE_M, BUFFER_M,
                     BLOCK_ORIGIN_5070, VAL_FRACTION, SPLIT_SEED, WINDOW_PX,
                     block_ids, coord_text, order_key, window_in_bounds)
from grouse_data import GrouseData, DataConfig

REPO = os.path.dirname(os.path.abspath(__file__))

# CR-0013's config: the hash spec is copied from it verbatim (it is a
# textual description of regions.order_key and the draw, not a measured
# value); everything else in the manifest is measured at run time.
ACCEPTANCE_CONFIG = os.path.join(REPO, "docs", "quality",
                                 "acceptance_split.json")

# CR-0012 section 2 "Parsing".
READ_CSV_KW = {"float_precision": "round_trip"}

# Exactly CR-0013's config `columns.positives` / `columns.block_assignments`
# (tests/test_cr0012.py pins them against the config).
POSITIVE_COLUMNS = [
    "longitude", "latitude", "state", "year", "n_visits", "first_year",
    "last_year", "x_5070", "y_5070", "evt", "evh", "evc", "sclass", "fdist",
    "ch", "cc", "evt_phys", "evt_group", "nonveg_landcover",
    "spatial_density", "spatial_zone", "env_zone", "envelope_id", "region",
    "block_id", "split"]
BLOCK_COLUMNS = ["block_id", "split", "n"]
POSITIVE_ORDER = ["longitude", "latitude"]
SPLITS = ("train", "val")


# ---------------------------------------------------------------------------
# Shared helpers (also used by generate_negatives.py)
# ---------------------------------------------------------------------------
def read_csv(path):
    return pd.read_csv(path, **READ_CSV_KW)


def to_5070(lon, lat):
    """EPSG:4326 -> EPSG:5070 (always_xy), float64 arrays. Every distance
    and block id is computed from these, never from an x_5070 column.
    Thin wrapper: the one transform is regions.to_5070 (CR-0015 section 1)."""
    return regions.to_5070(lon, lat)


def coord_keys(lon, lat, prefix=""):
    """order_key(prefix + coord_text(lon, lat)) per row, as uint64."""
    return np.array([order_key(prefix + coord_text(a, b))
                     for a, b in zip(lon, lat)], dtype=np.uint64)


def thin_by_min_distance(df, min_spacing_m=MIN_SPACING_M):
    """Pooled greedy thinning (CR-0012 positives step 4 / pool step 5).

    Rows are visited by ascending order_key(f"{lon:.6f},{lat:.6f}"), ties
    broken by longitude then latitude; a row is kept iff its squared
    EPSG:5070 distance (recomputed from lon/lat) to every already-kept row
    is >= min_spacing_m**2, so a row exactly min_spacing_m away is kept.
    Returns the kept rows in their input order."""
    if len(df) == 0:
        return df.copy()
    lon = df["longitude"].to_numpy(dtype=np.float64)
    lat = df["latitude"].to_numpy(dtype=np.float64)
    x, y = to_5070(lon, lat)
    keys = coord_keys(lon, lat)
    order = np.lexsort((lat, lon, keys))          # last key is primary
    lim = float(min_spacing_m) * float(min_spacing_m)
    cell = float(min_spacing_m)
    grid = {}
    kept = np.zeros(len(df), dtype=bool)
    for i in order.tolist():
        xi, yi = float(x[i]), float(y[i])
        cx, cy = int(np.floor(xi / cell)), int(np.floor(yi / cell))
        ok = True
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for (kx, ky) in grid.get((gx, gy), ()):
                    dx, dy = xi - kx, yi - ky
                    if dx * dx + dy * dy < lim:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            kept[i] = True
            grid.setdefault((cx, cy), []).append((xi, yi))
    return df[kept].copy()


def year_filled(df, rd):
    """The raster-lookup year per row, filled as dataset.py:98-102 does,
    the max taken over `df`."""
    if "year" not in df.columns or df["year"].isna().all():
        return pd.Series(max(rd.raster_years("evt")), index=df.index,
                         dtype=np.int64)
    return df["year"].fillna(df["year"].max()).astype(int)


def window_mask(df, rd):
    """True where regions.window_in_bounds holds on every FEATURE_SPEC
    raster at rd.raster_path(feat, year), year filled over `df` (CR-0012
    positives step 3 / pool step 8). lon/lat go into each raster's own
    CRS, as dataset.py does."""
    import rasterio
    from models import FEATURE_SPEC
    ok = np.ones(len(df), dtype=bool)
    if len(df) == 0:
        return ok
    years = year_filled(df, rd).to_numpy()
    lon = df["longitude"].to_numpy(dtype=np.float64)
    lat = df["latitude"].to_numpy(dtype=np.float64)
    for feat in FEATURE_SPEC:
        for yr in sorted(set(years.tolist())):
            sel = years == yr
            path = rd.raster_path(feat, int(yr))
            with rasterio.open(path) as src:
                t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                xs, ys = t.transform(lon[sel], lat[sel])
                ok[sel] &= window_in_bounds(src, xs, ys)
    return ok


def canonical(df, by):
    """Stable canonical row order (CR-0012 section 2)."""
    return df.sort_values(by, kind="mergesort").reset_index(drop=True)


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_path(path, root):
    """Repo-relative manifest key (e.g. data/pipeline/x.csv)."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def atomic_write(path, data):
    """Write `data` (bytes) to a temp file in the target's directory,
    fsync, then os.replace it over `path`."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix="." + os.path.basename(path),
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def json_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def measured_environment():
    """The environment this run uses, measured (CR-0013 config
    `environment` keys; `op_rule` is descriptive and omitted)."""
    import geopandas
    import pyogrio
    import pyproj
    import rasterio
    import scipy
    import shapely
    return {
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pyproj": pyproj.__version__,
        "PROJ": pyproj.proj_version_str,
        "rasterio": rasterio.__version__,
        "GDAL": rasterio.__gdal_version__,
        "geopandas": geopandas.__version__,
        "shapely": shapely.__version__,
        "pyogrio": pyogrio.__version__,
        "op_4326_5070": Transformer.from_crs(
            "EPSG:4326", "EPSG:5070", always_xy=True).definition,
    }


def measured_constants():
    """Every constant in CR-0013's config list, as this code uses it."""
    import generate_negatives as gn
    return {
        "REGIONS": list(REGIONS),
        "MIN_SPACING_M": MIN_SPACING_M,
        "BLOCK_SIZE_M": BLOCK_SIZE_M,
        "BLOCK_ORIGIN_5070": list(BLOCK_ORIGIN_5070),
        "BUFFER_M": BUFFER_M,
        "VAL_FRACTION": VAL_FRACTION,
        "SPLIT_SEED": SPLIT_SEED,
        "WINDOW_PX": WINDOW_PX,
        "YEAR_MIN": regions.YEAR_MIN,
        "NEG_RATIO": gn.NEG_RATIO,
        "NONVEG_MAX_FRAC": gn.NONVEG_MAX_FRAC,
        "W_FLOOR": gn.W_FLOOR,
        "W_CAP": gn.W_CAP,
        "NEUTRAL_WEIGHT": gn.NEUTRAL_WEIGHT,
        "NONVEG_WEIGHT": gn.NONVEG_WEIGHT,
        "MAX_COORD_UNCERTAINTY_M": gn.MAX_COORD_UNCERTAINTY_M,
        "KEY_DECIMALS": gn.KEY_DECIMALS,
    }


def hash_spec():
    with open(ACCEPTANCE_CONFIG) as f:
        return json.load(f)["hash_spec"]


def git_state():
    """(commit, dirty): dirty iff `git status --porcelain` lists a tracked
    .py file."""
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True,
                            check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                            capture_output=True, text=True,
                            check=True).stdout
    dirty = False
    for line in status.splitlines():
        if line.startswith("??") or len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path.endswith(".py"):
            dirty = True
    return commit, dirty


def section_common(inputs, outputs, counts):
    commit, dirty = git_state()
    return {
        "constants": measured_constants(),
        "hash_spec": hash_spec(),
        "environment": measured_environment(),
        "inputs": dict(sorted(inputs.items())),
        "outputs": dict(sorted(outputs.items())),
        "counts": counts,
        "commit": commit,
        "dirty": dirty,
    }


def raster_inputs(data, root):
    """{rel path: sha256} of every raster any region accessor resolved or
    opened for validation (fallback candidates included)."""
    out = {}
    for r in REGIONS:
        for p in data[r].rasters_touched:
            out[rel_path(p, root)] = sha256_file(p)
    return out


# ---------------------------------------------------------------------------
# Block split (CR-0012 positives step 5)
# ---------------------------------------------------------------------------
def assign_spatial_blocks(df):
    """Global block id per row (from lon/lat) and the pooled validation
    draw: blocks visited by ascending (order_key(block_id), block_id);
    whole blocks go to validation until the running record count reaches
    round(VAL_FRACTION x N). Returns (block_id Series, split Series,
    block table DataFrame [block_id, split, n] sorted by block_id)."""
    x, y = to_5070(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    bid = pd.Series(block_ids(x, y), index=df.index, dtype=object)
    counts = bid.value_counts()
    blocks = sorted(counts.index.tolist(), key=lambda b: (order_key(b), b))
    target = int(round(VAL_FRACTION * len(df)))
    val_blocks, running = set(), 0
    for b in blocks:
        if running >= target:
            break
        val_blocks.add(b)
        running += int(counts[b])
    split = bid.map(lambda b: "val" if b in val_blocks else "train")
    table = pd.DataFrame({
        "block_id": list(counts.index),
        "split": ["val" if b in val_blocks else "train" for b in counts.index],
        "n": [int(v) for v in counts.values]})
    table = canonical(table, ["block_id"])[BLOCK_COLUMNS]
    return bid, split, table


# ---------------------------------------------------------------------------
# Build and write
# ---------------------------------------------------------------------------
def build(data, root):
    """All positive outputs and the manifest `positives` section, in
    memory. Raises before anything is written."""
    counts = {r: {} for r in REGIONS}
    inputs = {}
    frames = []
    for r in REGIONS:
        rd = data[r]
        path = rd.path("evaluated")
        df = read_csv(path)
        inputs[rel_path(path, root)] = sha256_file(path)
        counts[r]["1"] = len(df)
        for col in ("state", "region", "nonveg_landcover", "year"):
            if col not in df.columns:
                raise ValueError(f"{path}: no '{col}' column")
        bad = (df["state"] != r) | (df["region"] != r)
        if bad.any():
            raise ValueError(f"{path}: {int(bad.sum())} rows where "
                             f"state == region == {r!r} does not hold")
        # Step 2 (CR-0019): habitat rows at or above the one year floor.
        # regions.YEAR_MIN is read here, at call time (the test seam).
        n_null = int(df["year"].isna().sum())
        if n_null:
            raise ValueError(f"{path}: {n_null} rows with a null year "
                             f"(the year floor YEAR_MIN cannot be applied)")
        df = df[~df["nonveg_landcover"].astype(bool)
                & (df["year"] >= regions.YEAR_MIN)].copy()
        counts[r]["2"] = len(df)
        df = df[window_mask(df, rd)].copy()
        counts[r]["3"] = len(df)
        frames.append(df)
    pooled = pd.concat(frames, ignore_index=True)
    missing = [c for c in POSITIVE_COLUMNS
               if c not in ("block_id", "split") and c not in pooled.columns]
    if missing:
        raise ValueError(f"evaluated_sightings lack columns {missing}")

    thinned = thin_by_min_distance(pooled, MIN_SPACING_M)
    bid, split, table = assign_spatial_blocks(thinned)
    thinned["block_id"] = bid
    thinned["split"] = split

    outputs = {}
    for r in REGIONS:
        part = canonical(thinned[thinned["region"] == r][POSITIVE_COLUMNS],
                         POSITIVE_ORDER)
        counts[r]["4"] = len(part)
        counts[r]["5"] = int(part["block_id"].notna().sum())
        counts[r]["6"] = len(part)
        outputs[rd_rel(data, r, "thinned", root)] = csv_bytes(part)
        for s, kind in (("train", "train_positives"), ("val", "val_positives")):
            sub = part[part["split"] == s]
            outputs[rd_rel(data, r, kind, root)] = csv_bytes(sub)
    outputs[rel_path(data.path("block_assignments", must_exist=False), root)] \
        = csv_bytes(table)

    section = section_common(
        {**inputs, **raster_inputs(data, root)},
        {k: sha256_bytes(v) for k, v in outputs.items()}, counts)
    return outputs, section


def rd_rel(data, region, kind, root):
    return rel_path(data[region].path(kind, must_exist=False), root)


def run(root="."):
    """Build everything, then write: delete acceptance_record.json, write
    each output atomically, and last the manifest with only a `positives`
    section (dropping any `negatives` section)."""
    root = os.path.abspath(root)
    data = GrouseData(DataConfig(base_dir=root))
    outputs, section = build(data, root)
    record = data.path("acceptance_record", must_exist=False)
    if os.path.exists(record):
        os.remove(record)
    for relp, b in outputs.items():
        atomic_write(os.path.join(root, relp), b)
    atomic_write(data.path("split_manifest", must_exist=False),
                 json_bytes({"positives": section}))
    for r in REGIONS:
        c = section["counts"][r]
        print(f"  {r}: {c['1']:,} loaded, {c['2']:,} habitat, {c['3']:,} "
              f"window in bounds, {c['6']:,} kept after pooled thinning")
    n_all = sum(section["counts"][r]["6"] for r in REGIONS)
    print(f"  Wrote {len(outputs)} files and the manifest's positives "
          f"section ({n_all:,} positives).")
    return section


def main():
    argparse.ArgumentParser(
        description="Thin positive records (pooled) and assign the global "
                    "spatial-block train/val holdout (CR-0012). No flags: "
                    "always every region in regions.REGIONS.").parse_args()
    run(".")


if __name__ == "__main__":
    main()
