"""
generate_negatives.py

Builds negative training + validation data from the GBIF other-species
records (gbif_negatives_{ST}.csv), per the agreed design:

  1. ENVELOPE WEIGHTING: each candidate's habitat envelope is looked up
     in envelope_metrics_{region}.csv and weighted by the INVERSE of the
     grouse Selection_Ratio - more negatives get sampled from envelopes
     where grouse presence was scarce relative to availability. Guardrails:
       - ratio clipped to [W_FLOOR, W_CAP] before inversion, so w=0
         envelopes can't get infinite weight
       - Landscape-Rare envelopes (availability too low to judge) get
         NEUTRAL weight 1.0 - "we couldn't judge" is not "avoided"
       - envelopes never seen in metrics at all get neutral 1.0
       - non-vegetated candidates (water/urban/etc) get NONVEG_WEIGHT -
         kept deliberately (the 'hard negative' zones requested), weighted
         at the maximum since they're definitionally not grouse habitat
  2. 300m BUFFER: any candidate within BUFFER_M of ANY known grouse
     location (every row of evaluated_sightings, vegetated or not) is
     excluded - absence of a grouse record 250m from a real grouse is
     not evidence of absence.
  3. BLOCK-CONSISTENT SPLIT: negatives inherit the SAME spatial-block
     train/val assignment as positives (block_assignments_{region}.csv),
     so no negative in the validation set sits in a training block.
     Blocks that contain no positives (unassigned) are assigned
     deterministically by hashing the block id at the same val fraction -
     stable across re-runs, no coordination file needed.

Candidate hygiene before any of that: exact-duplicate coordinates
collapsed, records with coordinate uncertainty > MAX_COORD_UNCERTAINTY_M
dropped (the GBIF analog of the hotspot-pin problem), then the same 30m
minimum-spacing thinning applied to positives.

Counts: per region and per split, negatives are sampled 1:1 against the
positive counts in train_positives/val_positives (NEG_RATIO adjustable).

Outputs (per region):
    negatives_{region}.csv         - all selected negatives + split column
    train_negatives_{region}.csv
    val_negatives_{region}.csv

Usage:
    python generate_negatives.py
    python generate_negatives.py --regions ME --seed 7
"""
import os
import math
import hashlib
import argparse

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

# Single-source imports: boxes + thinning from the positives pipeline,
# envelope machinery from the analysis pipeline, raster access from the
# data layer - so this script can't drift out of sync with any of them.
from prepare_training_data import BOXES, BLOCK_SIZE_M_DEFAULT, thin_by_min_distance
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, load_evt_crosswalk,
                            sample_raster, NON_VEG_SCLASS_CODES,
                            is_evt_phys_nonveg, RASTER_DIR)
from grouse_data import GrouseData

# ==========================================
# CONFIGURATION
# ==========================================
BUFFER_M = 300                  # exclusion radius around every grouse location
MIN_SPACING_M = 30              # same candidate thinning as positives
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

CSV_KEEP = ["longitude", "latitude", "common_name", "obs_date", "year",
            "state", "gbif_id", "coord_uncertainty_m"]


def to_albers(lons, lats):
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    return t.transform(np.asarray(lons), np.asarray(lats))


def compute_block_ids(df, box, block_size_m):
    """Same grid + anchoring math as prepare_training_data's
    assign_spatial_blocks, so a negative and a positive at the same spot
    land in the same block id."""
    min_lon, min_lat, max_lon, max_lat = box
    cx, cy = to_albers([min_lon, max_lon], [min_lat, max_lat])
    x0, y0 = min(cx), min(cy)
    bx = np.floor((df['x_5070'].values - x0) / block_size_m).astype(int)
    by = np.floor((df['y_5070'].values - y0) / block_size_m).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)


def split_for_unassigned(block_id, val_fraction, seed):
    """Deterministic train/val assignment for blocks that hold no
    positives: hash the block id (stable across runs/machines) and put
    ~val_fraction of them in validation."""
    h = int(hashlib.md5(f"{seed}:{block_id}".encode()).hexdigest(), 16)
    return 'val' if (h % 10_000) < val_fraction * 10_000 else 'train'


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


def process_region(region, data, evt_xwalk, seed):
    print(f"\n##########################################")
    print(f"# REGION: {region}")
    print(f"##########################################")
    rng = np.random.default_rng(seed)

    # ---- inputs ----------------------------------------------------------
    cand_path = f"data/negatives/gbif_negatives_{region}.csv"
    if not os.path.exists(cand_path):
        print(f"  [!] {cand_path} not found - run gbif_negatives_download.py. Skipping.")
        return
    cand = pd.read_csv(cand_path)
    print(f"  {len(cand):,} raw candidate records loaded.")

    try:
        evaluated = data[region].evaluated
        metrics = data[region].envelope_metrics
        blocks = data[region].block_assignments
        n_train_pos = len(data[region].positives("train"))
        n_val_pos = len(data[region].positives("val"))
    except Exception as e:
        print(f"  [!] Missing pipeline inputs for {region}: {e}. Skipping.")
        return

    # ---- candidate hygiene ----------------------------------------------
    n0 = len(cand)
    too_vague = cand['coord_uncertainty_m'] > MAX_COORD_UNCERTAINTY_M
    cand = cand[~too_vague.fillna(False)].copy()
    print(f"  Dropped {n0 - len(cand):,} records with coordinate "
         f"uncertainty > {MAX_COORD_UNCERTAINTY_M} m (NaN uncertainty kept).")

    n1 = len(cand)
    cand = cand.drop_duplicates(
        subset=cand[['longitude', 'latitude']].round(5).columns.tolist()
    )
    coords_key = cand[['longitude', 'latitude']].round(5)
    cand = cand.loc[~coords_key.duplicated()].copy()
    print(f"  Collapsed {n1 - len(cand):,} exact-duplicate coordinates "
         f"(reused pins across checklists/species).")

    cand['x_5070'], cand['y_5070'] = to_albers(cand['longitude'].values,
                                               cand['latitude'].values)

    n2 = len(cand)
    cand = thin_by_min_distance(cand, MIN_SPACING_M, seed)
    print(f"  Thinned at {MIN_SPACING_M} m spacing: {n2:,} -> {len(cand):,}.")

    # ---- 300m buffer around every known grouse location ------------------
    pos_x, pos_y = to_albers(evaluated['longitude'].values,
                             evaluated['latitude'].values)
    tree = cKDTree(np.column_stack([pos_x, pos_y]))
    dist, _ = tree.query(cand[['x_5070', 'y_5070']].values, k=1)
    n3 = len(cand)
    cand = cand[dist > BUFFER_M].copy()
    print(f"  Buffer: removed {n3 - len(cand):,} candidates within "
         f"{BUFFER_M} m of a grouse location ({len(evaluated):,} grouse "
         f"locations buffered, vegetated and non-veg alike).")
    if len(cand) == 0:
        print("  [!] No candidates survived - nothing to sample. Skipping.")
        return

    # ---- envelope extraction + weights -----------------------------------
    rd = data[region]
    feats_needed = sorted({c for c, _ in ENVELOPE_SCHEME
                           if c not in ("evt_phys", "evt_group")} | {"sclass", "evt"})
    for feat in feats_needed:
        vals = np.full(len(cand), np.nan)
        for year in sorted(cand['year'].dropna().unique()):
            mask = (cand['year'] == year).values
            tif = rd.raster_path(feat, int(year))   # nearest valid year
            vals[mask] = sample_raster(tif, cand.loc[mask, 'longitude'].values,
                                       cand.loc[mask, 'latitude'].values)
        cand[feat] = vals
    n4 = len(cand)
    cand = cand.dropna(subset=feats_needed).copy()
    print(f"  Extraction: {n4 - len(cand):,} candidates dropped for "
         f"nodata in {feats_needed}; {len(cand):,} remain.")

    if evt_xwalk is not None:
        cand['evt_phys'] = cand['evt'].astype(int).map(evt_xwalk['phys']).fillna("Unmapped")
    else:
        cand['evt_phys'] = "Unmapped"

    # Refit the EVH quantile edges from the SAME habitat records the
    # envelope metrics were built from (deterministic - qcut on the same
    # data reproduces the same edges), so negatives are binned into the
    # identical envelope ids the metrics table uses.
    habitat = evaluated[~evaluated['nonveg_landcover'].astype(bool)]
    binners = fit_scheme_binners(habitat, ENVELOPE_SCHEME)
    cand['envelope_id'] = build_envelope_id(cand, ENVELOPE_SCHEME, binners=binners)

    cand['is_nonveg'] = (cand['sclass'].isin(NON_VEG_SCLASS_CODES)
                         | is_evt_phys_nonveg(cand['evt_phys']))

    metrics_map = {row['Envelope']: row for _, row in metrics.iterrows()}
    weights, wclass = [], []
    for env_id, nv in zip(cand['envelope_id'], cand['is_nonveg']):
        w, cls = build_weight(env_id, metrics_map, nv)
        weights.append(w)
        wclass.append(cls)
    cand['weight'] = weights
    cand['weight_basis'] = wclass

    print(f"  Weight basis distribution among candidates:")
    for basis, n in cand['weight_basis'].value_counts().items():
        print(f"    {basis}: {n:,}")

    # ---- block-consistent split ------------------------------------------
    cand['block_id'] = compute_block_ids(cand, BOXES[region], BLOCK_SIZE_M_DEFAULT)
    block_split = dict(zip(blocks['block_id'], blocks['split']))
    val_fraction = (blocks['split'] == 'val').mean()
    cand['split'] = [
        block_split.get(b) or split_for_unassigned(b, val_fraction, seed)
        for b in cand['block_id']
    ]

    # ---- weighted sampling per split -------------------------------------
    targets = {'train': int(round(n_train_pos * NEG_RATIO)),
               'val': int(round(n_val_pos * NEG_RATIO))}
    picked = []
    for split, n_target in targets.items():
        pool = cand[cand['split'] == split]
        if len(pool) == 0:
            print(f"  [!] No candidates in '{split}' blocks - 0/{n_target} sampled.")
            continue
        # Two-pool sampling: NonVeg capped at NONVEG_MAX_FRAC of the
        # target; the rest must come from habitat-based candidates so
        # trivially-separable water/urban records can't dominate.
        nonveg_pool = pool[pool['is_nonveg']]
        habitat_pool = pool[~pool['is_nonveg']]
        n_nonveg_t = min(int(round(n_target * NONVEG_MAX_FRAC)),
                         len(nonveg_pool))
        n_habitat_t = n_target - n_nonveg_t

        def weighted_take(subpool, n):
            if n <= 0 or len(subpool) == 0:
                return subpool.iloc[0:0]
            if len(subpool) <= n:
                return subpool
            p = subpool['weight'].values / subpool['weight'].sum()
            idx = rng.choice(subpool.index.values, size=n, replace=False, p=p)
            return subpool.loc[idx]

        take_hab = weighted_take(habitat_pool, n_habitat_t)
        shortfall = n_habitat_t - len(take_hab)
        if shortfall > 0:
            # Habitat pool undersupplied: top up from NonVeg beyond the
            # cap rather than under-delivering, but say so loudly.
            print(f"  [!] '{split}': habitat pool undersupplied "
                 f"({len(take_hab):,}/{n_habitat_t:,}) - filling "
                 f"{shortfall:,} extra from NonVeg beyond the "
                 f"{NONVEG_MAX_FRAC:.0%} cap. Raise the download headroom "
                 f"to fix properly.")
            n_nonveg_t = min(n_nonveg_t + shortfall, len(nonveg_pool))
        take_nv = weighted_take(nonveg_pool, n_nonveg_t)

        got = pd.concat([take_hab, take_nv])
        if len(got) < n_target:
            print(f"  [!] '{split}': only {len(got):,}/{n_target:,} "
                 f"available across both pools - taking all of them.")
        else:
            print(f"  Sampled {len(got):,} '{split}' negatives "
                 f"({len(take_hab):,} habitat + {len(take_nv):,} NonVeg "
                 f"[{100 * len(take_nv) / max(len(got), 1):.0f}%], "
                 f"cap {NONVEG_MAX_FRAC:.0%}).")
        picked.append(got)
    if not picked:
        return
    selected = pd.concat(picked).copy()
    selected['label'] = 0

    out_cols = (CSV_KEEP + feats_needed +
                ['evt_phys', 'envelope_id', 'is_nonveg', 'weight',
                 'weight_basis', 'block_id', 'split', 'label',
                 'x_5070', 'y_5070'])
    out_cols = [c for c in out_cols if c in selected.columns]
    selected = selected[out_cols]

    selected.to_csv(f"data/negatives/negatives_{region}.csv", index=False)
    selected[selected['split'] == 'train'].to_csv(
        f"data/negatives/train_negatives_{region}.csv", index=False)
    selected[selected['split'] == 'val'].to_csv(
        f"data/negatives/val_negatives_{region}.csv", index=False)

    n_tr = int((selected['split'] == 'train').sum())
    n_va = int((selected['split'] == 'val').sum())
    print(f"  Saved negatives_{region}.csv "
         f"({n_tr:,} train vs {n_train_pos:,} positive train; "
         f"{n_va:,} val vs {n_val_pos:,} positive val).")
    print(f"  Selected-set weight basis:")
    for basis, n in selected['weight_basis'].value_counts().items():
        print(f"    {basis}: {n:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate envelope-weighted, buffered, block-split "
                    "negative training/validation data.")
    parser.add_argument("--regions", nargs="+", default=list(BOXES.keys()),
                        choices=list(BOXES.keys()))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data = GrouseData()
    evt_xwalk = load_evt_crosswalk(RASTER_DIR)
    if evt_xwalk is None:
        print("[!] No EVT attribute table found - evt_phys will be "
             "'Unmapped' and envelope weighting will degrade. Run "
             "download_attribute_tables.py first.")

    for region in args.regions:
        process_region(region, data, evt_xwalk, args.seed)


if __name__ == "__main__":
    main()

