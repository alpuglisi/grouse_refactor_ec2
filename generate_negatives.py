"""
generate_negatives.py

Builds negative training + validation data from the GBIF other-species
records (gbif_negatives_{ST}.csv) of every region in regions.REGIONS,
pooled. CR-0012 section 2 ("Candidate pool", "Draw") is the
specification; each step is a deterministic, order-free function of its
inputs so acceptance_split.py (CR-0013) can replay it exactly.

Candidate pool (data/negatives/candidate_pool.csv), pooled over regions:
   1. load gbif_negatives_R for every R; raise unless state == R
   2. drop records with coord_uncertainty_m > MAX_COORD_UNCERTAINTY_M
      (NaN kept - the GBIF analog of the hotspot-pin problem)
   3. deduplicate on the 5 dp coordinate key, keeping the SMALLEST
      gbif_id (file order is never used); raise if a key is filed under
      two states
   4. drop (never relabel) every record regions.verify_partition returns;
      their coordinates go into the manifest
   5. thin at MIN_SPACING_M, exactly as the positives are thinned
   6. 300 m BUFFER: drop candidates (a) within BUFFER_M (squared
      distance <= BUFFER_M**2) of ANY row of ANY evaluated_sightings_R -
      absence of a record next to a real grouse is not evidence of
      absence - or (b) within BUFFER_M of the edge of the sightings'
      acquisition domain D (the union of the STATE_FIPS county polygons;
      regions.domain_edge_m <= BUFFER_M): beyond D no sighting was
      acquired, so (a) cannot be certified there (CR-0017; BUG-0050)
   7. extract the envelope features on the region's grid; drop nodata
   8. drop rows whose WINDOW_PX window is not inside every feature raster
   9. evt_phys, envelope_id, is_nonveg and the ENVELOPE WEIGHT: the
      inverse of the grouse Selection_Ratio, clipped to [W_FLOOR, W_CAP];
      Landscape-Rare and unseen envelopes get NEUTRAL_WEIGHT; non-vegetated
      candidates get NONVEG_WEIGHT (the deliberate 'hard negatives')
  10. BLOCK-CONSISTENT SPLIT on the one global grid: a block's split is
      its split in block_assignments.csv (prepare_training_data.py owns
      the grid and the validation draw); a positive-free block is 'val'
      iff md5(f"{SPLIT_SEED}:{block_id}") % 10000 < vf x 10000
  11. write the pool

Draw, per region R and split s: n = round(n_pos(R, s) x NEG_RATIO);
NonVeg is capped at round(n x NONVEG_MAX_FRAC); the rest must come from
the habitat pool, and a habitat shortfall RAISES (no top-up). Each
sub-pool is sampled without replacement by Efraimidis-Spirakis keys
log(u)/weight, u from the seeded coordinate hash.

Outputs (per region):
    negatives_{region}.csv         - all selected negatives + split column
    train_negatives_{region}.csv   - its split == 'train' rows
    val_negatives_{region}.csv     - its split == 'val' rows
plus candidate_pool.csv and the `negatives` section of split_manifest.json
(added only after the `positives` section's output digests are verified
against the files on disk).

Usage (no flags; always every region in regions.REGIONS):
    python generate_negatives.py
"""
import argparse
import json
import math
import os
import traceback

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Single-source imports: thinning, window predicate and manifest helpers
# from the positives pipeline, envelope machinery from the analysis
# pipeline, raster access from the data layer, every spatial/split
# constant from regions.py - so this script can't drift out of sync with
# any of them.
from prepare_training_data import (
    thin_by_min_distance, window_mask, to_5070, coord_keys, read_csv,
    canonical, csv_bytes, sha256_bytes, sha256_file, rel_path,
    atomic_write, json_bytes, section_common, raster_inputs)
from regions import (REGIONS, BUFFER_M, COUNTY_POLYGONS_YEAR, MIN_SPACING_M,
                     block_ids, block_split, domain_edge_m, verify_partition)
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, load_evt_crosswalk,
                            sample_raster, NON_VEG_SCLASS_CODES,
                            is_evt_phys_nonveg)
from grouse_data import GrouseData, DataConfig, MissingDataError

# ==========================================
# CONFIGURATION
# ==========================================
# BUFFER_M (exclusion radius around every grouse location) and
# MIN_SPACING_M (same candidate thinning as positives): regions.py.
MAX_COORD_UNCERTAINTY_M = 1000  # drop GBIF records vaguer than this (NaN kept)
NEG_RATIO = 1.0                 # negatives per positive, per split

# Weighting: weight = 1 / clip(Selection_Ratio, W_FLOOR, W_CAP)
W_FLOOR = 0.1                   # ratio floor -> max habitat-based weight 10
W_CAP = 10.0                    # ratio cap   -> min weight 0.1
NEUTRAL_WEIGHT = 1.0            # Landscape-Rare / never-observed envelopes
NONVEG_WEIGHT = 10.0            # water/urban/etc 'hard negative' candidates

# Cap on the NonVeg share of each split's SAMPLED negatives. NonVeg
# candidates are useful as a floor (a model that can't reject open water
# is broken) but they're trivially separable - at high shares they let
# focal loss "solve" the negative class in one epoch via the water/urban
# embeddings and never learn to discriminate real habitat. The remainder
# of the quota is forced to come from the weighted habitat-based pool.
NONVEG_MAX_FRAC = 0.30

# Coordinate dedup key precision (decimal places), CR-0012 section 2.
KEY_DECIMALS = 5

CSV_KEEP = ["longitude", "latitude", "common_name", "obs_date", "year",
            "state", "gbif_id", "coord_uncertainty_m"]

# Envelope features extracted for every candidate (:198-199 at 05d788d).
ENVELOPE_FEATURES = sorted({c for c, _ in ENVELOPE_SCHEME
                            if c not in ("evt_phys", "evt_group")}
                           | {"sclass", "evt"})

# Exactly CR-0013's config `columns.negatives` and `columns.pool`
# (tests/test_cr0012.py pins them against the config).
NEGATIVE_COLUMNS = (CSV_KEEP + ENVELOPE_FEATURES +
                    ["evt_phys", "envelope_id", "is_nonveg", "weight",
                     "weight_basis", "block_id", "split", "label",
                     "x_5070", "y_5070", "region"])
POOL_COLUMNS = (["longitude", "latitude", "x_5070", "y_5070", "state",
                 "region", "year", "common_name", "gbif_id"]
                + ENVELOPE_FEATURES +
                ["evt_phys", "envelope_id", "is_nonveg", "weight",
                 "weight_basis", "block_id", "split"])
NEGATIVE_ORDER = ["longitude", "latitude"]
POOL_ORDER = ["region", "longitude", "latitude"]
SPLITS = ("train", "val")


def compute_block_ids(df):
    """Global block id per row, from its lon/lat (regions.block_ids), so
    a negative and a positive at the same spot share a block id."""
    x, y = to_5070(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    return pd.Series(block_ids(x, y), index=df.index, dtype=object)


def build_weight(env_id, metrics_map, nonveg_mask_value):
    if nonveg_mask_value:
        return NONVEG_WEIGHT, "NonVeg (hard negative)"
    row = metrics_map.get(env_id)
    if row is None:
        return NEUTRAL_WEIGHT, "Unknown envelope (neutral)"
    if str(row["Classification"]).startswith("Landscape-Rare"):
        return NEUTRAL_WEIGHT, "Landscape-Rare (neutral)"
    w = row["Selection_Ratio"]
    if pd.isna(w):
        # used-but-zero-availability: infinitely selected; minimum weight
        return 1.0 / W_CAP, "Selected (ratio undefined, min weight)"
    return 1.0 / float(np.clip(w, W_FLOOR, W_CAP)), row["Classification"]


# ---------------------------------------------------------------------------
# Candidate pool (CR-0012 section 2, pool steps 1-11)
# ---------------------------------------------------------------------------
def dedup_min_gbif_id(pool):
    """Pool step 3: one row per 5 dp (longitude, latitude) key, the one
    with the smallest gbif_id. Order-free: raises unless gbif_id is
    non-null and unique, and if a key is filed under two states."""
    if pool["gbif_id"].isna().any():
        raise ValueError("gbif_id is null on "
                         f"{int(pool['gbif_id'].isna().sum())} candidate rows")
    if pool["gbif_id"].duplicated().any():
        raise ValueError("gbif_id is not unique over the pooled candidates "
                         f"({int(pool['gbif_id'].duplicated().sum())} repeats)")
    # PA-0005: the rounded key is its own variable.
    key = pool[["longitude", "latitude"]].round(KEY_DECIMALS)
    key.columns = ["_klon", "_klat"]
    n_states = pd.concat([key, pool[["state"]]], axis=1).groupby(
        ["_klon", "_klat"])["state"].nunique()
    if (n_states > 1).any():
        raise ValueError(f"{int((n_states > 1).sum())} coordinate keys are "
                         f"filed under two states")
    order = pool["gbif_id"].sort_values(kind="mergesort").index
    first = ~key.loc[order].duplicated(keep="first")
    return pool.loc[order[first.to_numpy()]].reset_index(drop=True)


def buffer_drop_mask(cand_lon, cand_lat, sight_lon, sight_lat,
                     buffer_m=BUFFER_M):
    """Pool step 6: True for candidates whose squared EPSG:5070 distance
    (recomputed from lon/lat) to any sighting is <= buffer_m**2."""
    drop = np.zeros(len(cand_lon), dtype=bool)
    if len(cand_lon) == 0 or len(sight_lon) == 0:
        return drop
    cx, cy = to_5070(cand_lon, cand_lat)
    sx, sy = to_5070(sight_lon, sight_lat)
    lim = float(buffer_m) * float(buffer_m)
    tree = cKDTree(np.column_stack([sx, sy]))
    # An inflated radius finds every candidate neighbour; the exact
    # squared comparison decides the boundary.
    hits = tree.query_ball_point(np.column_stack([cx, cy]),
                                 r=float(buffer_m) * (1 + 1e-9) + 1e-6)
    for i, idx in enumerate(hits):
        xi, yi = float(cx[i]), float(cy[i])
        for j in idx:
            dx, dy = xi - float(sx[j]), yi - float(sy[j])
            if dx * dx + dy * dy <= lim:
                drop[i] = True
                break
    return drop


def domain_edge_drop_mask(lon, lat, domain=None):
    """Pool step 6 (b) (CR-0017 section 2): True for candidates whose
    EPSG:5070 distance (from lon/lat via to_5070) to the edge of the
    sightings' acquisition domain D is <= BUFFER_M; a point outside D
    has edge_m 0 and is dropped. `domain` is regions.domain_edge_m's
    test seam (None = D from the county file)."""
    lon = np.asarray(lon, dtype=np.float64)
    if len(lon) == 0:
        return np.zeros(0, dtype=bool)
    x, y = to_5070(lon, np.asarray(lat, dtype=np.float64))
    return domain_edge_m(x, y, domain=domain) <= BUFFER_M


def extract_envelope(cand, rd):
    """Pool step 7: sample the envelope features on the region's grid at
    rd.raster_path(feat, year) (nearest valid year)."""
    cand = cand.copy()
    for feat in ENVELOPE_FEATURES:
        vals = np.full(len(cand), np.nan)
        for year in sorted(cand["year"].dropna().unique()):
            mask = (cand["year"] == year).to_numpy()
            tif = rd.raster_path(feat, int(year))
            vals[mask] = sample_raster(tif, cand.loc[mask, "longitude"].values,
                                       cand.loc[mask, "latitude"].values)
        cand[feat] = vals
    return cand


def attach_weights(cand, evaluated, metrics, evt_xwalk):
    """Pool step 9: evt_phys, envelope_id, is_nonveg, weight, weight_basis."""
    cand = cand.copy()
    if evt_xwalk is not None:
        cand["evt_phys"] = cand["evt"].astype(int).map(
            evt_xwalk["phys"]).fillna("Unmapped")
    else:
        cand["evt_phys"] = "Unmapped"
    # EVH quantile edges refit from the SAME habitat records the envelope
    # metrics were built from, so negatives are binned into the identical
    # envelope ids the metrics table uses.
    habitat = evaluated[~evaluated["nonveg_landcover"].astype(bool)]
    binners = fit_scheme_binners(habitat, ENVELOPE_SCHEME)
    cand["envelope_id"] = build_envelope_id(cand, ENVELOPE_SCHEME,
                                            binners=binners)
    cand["is_nonveg"] = (cand["sclass"].isin(NON_VEG_SCLASS_CODES)
                         | is_evt_phys_nonveg(cand["evt_phys"]))
    metrics_map = {row["Envelope"]: row for _, row in metrics.iterrows()}
    weights, basis = [], []
    for env_id, nv in zip(cand["envelope_id"], cand["is_nonveg"]):
        w, cls = build_weight(env_id, metrics_map, nv)
        weights.append(w)
        basis.append(cls)
    cand["weight"] = weights
    cand["weight_basis"] = basis
    return cand


def assign_split(cand, blocks):
    """Pool step 10: block_id; the block's split if the block is in
    block_assignments.csv, else the md5 rule with vf = the share of
    positive-occupied blocks in validation."""
    cand = cand.copy()
    cand["block_id"] = compute_block_ids(cand)
    # The one block-split rule (CR-0015 section 1; PA-0001).
    cand["split"] = block_split(cand["block_id"], blocks).tolist()
    return cand


# ---------------------------------------------------------------------------
# Draw (CR-0012 section 2 "Draw")
# ---------------------------------------------------------------------------
def es_select(sub, n):
    """The n rows of `sub` with the largest log(u)/weight, u =
    (order_key("neg:" + coord) + 0.5) / 2**64; ties by ascending key.
    Efraimidis-Spirakis weighted sampling without replacement; positional,
    no index labels (removes weighted_take's .loc hazard)."""
    if n <= 0 or len(sub) == 0:
        return sub.iloc[0:0]
    keys = coord_keys(sub["longitude"].to_numpy(dtype=np.float64),
                      sub["latitude"].to_numpy(dtype=np.float64),
                      prefix="neg:")
    w = sub["weight"].to_numpy(dtype=np.float64)
    scored = []
    for i, (k, wi) in enumerate(zip(keys.tolist(), w.tolist())):
        u = (int(k) + 0.5) / 2**64
        scored.append((-(math.log(u) / wi), int(k), i))
    scored.sort()
    take = sorted(i for _, _, i in scored[:n])
    return sub.iloc[take]


def draw_region_split(pool_rs, n_pos):
    """Draw one (region, split): returns (selected rows, {n, n_nv, n_hab}).
    Raises when the habitat pool cannot supply its share."""
    n = int(round(n_pos * NEG_RATIO))
    nv = pool_rs["is_nonveg"].astype(bool)
    nv_pool, hab_pool = pool_rs[nv], pool_rs[~nv]
    n_nv = min(int(round(n * NONVEG_MAX_FRAC)), len(nv_pool))
    n_hab = n - n_nv
    if len(hab_pool) < n_hab:
        raise RuntimeError(
            f"habitat pool undersupplied: {len(hab_pool):,} candidates for "
            f"a habitat target of {n_hab:,} (n={n:,}, NonVeg {n_nv:,}); "
            f"raise the download headroom (CR-0012: no NonVeg top-up)")
    got = pd.concat([es_select(hab_pool, n_hab), es_select(nv_pool, n_nv)],
                    ignore_index=True)
    return got, {"n": n, "n_nv": n_nv, "n_hab": n_hab}


# ---------------------------------------------------------------------------
# Build and write
# ---------------------------------------------------------------------------
def verify_positive_outputs(manifest, root):
    """Raise unless the manifest's positives section exists and every
    output digest it lists matches the file on disk."""
    if "positives" not in manifest:
        raise RuntimeError("split_manifest.json has no positives section - "
                           "run prepare_training_data.py first")
    outs = manifest["positives"].get("outputs") or {}
    if not outs:
        raise RuntimeError("split_manifest.json positives section lists no "
                           "outputs")
    bad = []
    for relp, digest in sorted(outs.items()):
        p = os.path.join(root, relp)
        if not os.path.exists(p) or sha256_file(p) != digest:
            bad.append(relp)
    if bad:
        raise RuntimeError(f"positive outputs differ from the manifest's "
                           f"positives section (re-run "
                           f"prepare_training_data.py): {bad}")


def build(data, root):
    """Pool, draw and the manifest `negatives` section, in memory. Raises
    before anything is written. Returns (outputs {rel: bytes}, section,
    manifest read from disk)."""
    with open(data.path("split_manifest")) as f:
        manifest = json.load(f)
    verify_positive_outputs(manifest, root)

    inputs = {}

    def digest(path):
        inputs[rel_path(path, root)] = sha256_file(path)
        return path

    counts = {r: {} for r in REGIONS}

    def count(step, df):
        vc = df["region"].value_counts()
        for r in REGIONS:
            counts[r][str(step)] = int(vc.get(r, 0))

    blocks = read_csv(digest(data.path("block_assignments")))

    # 1. load every region's candidates
    frames = []
    for r in REGIONS:
        path = digest(data[r].path("gbif_candidates"))
        df = read_csv(path)
        if "state" not in df.columns or (df["state"] != r).any():
            raise ValueError(f"{path}: rows where state != {r!r}")
        df["region"] = r
        frames.append(df)
    pool = pd.concat(frames, ignore_index=True)
    count(1, pool)

    # 2. coordinate uncertainty (NaN kept)
    too_vague = pool["coord_uncertainty_m"] > MAX_COORD_UNCERTAINTY_M
    pool = pool[~too_vague.fillna(False).astype(bool)].reset_index(drop=True)
    count(2, pool)

    # 3. order-free dedup
    pool = dedup_min_gbif_id(pool)
    count(3, pool)

    # 4. partition exceptions: dropped, not relabelled
    bad = verify_partition(pool["longitude"].to_numpy(),
                           pool["latitude"].to_numpy(),
                           pool["state"].to_numpy())
    digest(data.path("tiger_county", year=COUNTY_POLYGONS_YEAR))
    drop = np.zeros(len(pool), dtype=bool)
    drop[np.asarray(bad.index, dtype=np.int64)] = True
    dropped = sorted([float(a), float(b)] for a, b in zip(
        pool.loc[drop, "longitude"], pool.loc[drop, "latitude"]))
    pool = pool[~drop].reset_index(drop=True)
    count(4, pool)

    # 5. pooled thinning, as for the positives
    pool = thin_by_min_distance(pool, MIN_SPACING_M).reset_index(drop=True)
    count(5, pool)

    # 6. (a) buffer against every row of every region's sightings;
    #    (b) drop within BUFFER_M of the acquisition-domain edge (CR-0017).
    #    Both are row filters on the step-5 pool.
    evaluated = {r: read_csv(digest(data[r].path("evaluated")))
                 for r in REGIONS}
    sights = pd.concat(list(evaluated.values()), ignore_index=True)
    in_buffer = buffer_drop_mask(
        pool["longitude"].to_numpy(dtype=np.float64),
        pool["latitude"].to_numpy(dtype=np.float64),
        sights["longitude"].to_numpy(dtype=np.float64),
        sights["latitude"].to_numpy(dtype=np.float64))
    at_edge = domain_edge_drop_mask(
        pool["longitude"].to_numpy(dtype=np.float64),
        pool["latitude"].to_numpy(dtype=np.float64))
    n_buffered = int(in_buffer.sum())
    n_edge_only = int((at_edge & ~in_buffer).sum())
    n_overlap = int((at_edge & in_buffer).sum())
    pool = pool[~(in_buffer | at_edge)].reset_index(drop=True)
    count(6, pool)

    # 7-10 per region, on its own grid and envelope metrics
    evt_xwalk = load_evt_crosswalk(data.config.resolve(data.config.raster_dir))
    if evt_xwalk is None:
        print("[!] No EVT attribute table found - evt_phys will be "
              "'Unmapped' and envelope weighting will degrade. Run "
              "download_attribute_tables.py first.")
    else:
        digest(data.config.resolve(os.path.join(
            data.config.attribute_dir, evt_xwalk["source"])))
    parts = []
    for r in REGIONS:
        rd = data[r]
        cand = extract_envelope(pool[pool["region"] == r], rd)
        cand = cand.dropna(subset=ENVELOPE_FEATURES)
        counts[r]["7"] = len(cand)
        cand = cand[window_mask(cand, rd)]
        counts[r]["8"] = len(cand)
        metrics = read_csv(digest(rd.path("envelope_metrics")))
        cand = attach_weights(cand, evaluated[r], metrics, evt_xwalk)
        counts[r]["9"] = len(cand)
        cand = assign_split(cand, blocks)
        counts[r]["10"] = len(cand)
        parts.append(cand)
    pool = pd.concat(parts, ignore_index=True)
    pool["x_5070"], pool["y_5070"] = to_5070(pool["longitude"].to_numpy(),
                                             pool["latitude"].to_numpy())
    missing = sorted(c for c in set(POOL_COLUMNS) | set(NEGATIVE_COLUMNS)
                     if c not in pool.columns and c != "label")
    if missing:
        raise ValueError(f"candidate pool lacks columns {missing}")
    pool = canonical(pool, POOL_ORDER)
    count(11, pool)

    # Draw, per region and split
    outputs = {rel_path(data.path("candidate_pool", must_exist=False), root):
               csv_bytes(pool[POOL_COLUMNS])}
    draw = {}
    for r in REGIONS:
        rd = data[r]
        picked, draw[r] = [], {}
        for s in SPLITS:
            n_pos = len(read_csv(digest(rd.path(f"{s}_positives"))))
            sub = pool[(pool["region"] == r) & (pool["split"] == s)]
            got, draw[r][s] = draw_region_split(sub, n_pos)
            picked.append(got)
        sel = pd.concat(picked, ignore_index=True)
        sel["label"] = 0
        sel = canonical(sel[NEGATIVE_COLUMNS], NEGATIVE_ORDER)
        outputs[rel_path(rd.path("negatives", must_exist=False), root)] = \
            csv_bytes(sel)
        for s in SPLITS:
            outputs[rel_path(rd.path(f"{s}_negatives", must_exist=False),
                             root)] = csv_bytes(sel[sel["split"] == s])

    section = section_common(
        {**inputs, **raster_inputs(data, root)},
        {k: sha256_bytes(v) for k, v in outputs.items()}, counts)
    section["draw"] = draw
    section["dropped"] = dropped
    print(f"  Pool: {len(pool):,} candidates; {len(dropped)} partition "
          f"exception(s) dropped; {n_buffered:,} within {BUFFER_M} m of a "
          f"grouse location dropped (a); {n_edge_only:,} more within "
          f"{BUFFER_M} m of the acquisition-domain edge dropped (b only); "
          f"{n_overlap:,} in both (a) and (b).")
    for r in REGIONS:
        print(f"  {r}: " + "; ".join(
            f"{s} {d['n']:,} ({d['n_hab']:,} habitat + {d['n_nv']:,} NonVeg)"
            for s, d in draw[r].items()))
    return outputs, section, manifest


def run(root="."):
    """Build everything in memory, then write each output atomically and,
    last, the manifest with both sections."""
    root = os.path.abspath(root)
    data = GrouseData(DataConfig(base_dir=root))
    outputs, section, manifest = build(data, root)
    for relp, b in outputs.items():
        atomic_write(os.path.join(root, relp), b)
    atomic_write(data.path("split_manifest", must_exist=False),
                 json_bytes({"positives": manifest["positives"],
                             "negatives": section}))
    print(f"  Wrote {len(outputs)} files and the manifest's negatives "
          f"section.")
    return section


def main():
    argparse.ArgumentParser(
        description="Build the pooled candidate pool and draw the "
                    "envelope-weighted, buffered, block-split negatives "
                    "(CR-0012). No flags: always every region in "
                    "regions.REGIONS.").parse_args()
    # CR-0012 section 3 / PA-0011: no skip path. MissingDataError
    # propagates as is; anything else is logged with its type and
    # traceback, then re-raised.
    try:
        run(".")
    except MissingDataError:
        raise
    except Exception as e:
        print(f"[!] generate_negatives failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()