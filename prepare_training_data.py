"""
prepare_training_data.py

Two independent steps for turning evaluated_sightings_{region}.csv into
ML-ready positives, WITHOUT modifying that file:

1. THINNING: enforce a minimum spacing between positive records so no two
   share a raster pixel (or closer). Exact-coordinate dedup already
   happened upstream in analyze_grouse.py; this goes further because two
   DISTINCT nearby coordinates can still land in the same pixel (or close
   enough to be non-independent for a classifier) and produce identical
   or near-identical feature vectors - training on those is an
   unintentional per-location sample weight, not new information.

2. SPATIAL BLOCK HOLDOUT: partition each region into a grid of blocks and
   assign each block entirely to train or validation. A random row split
   would scatter spatially-autocorrelated points across both sets, so the
   model gets validated on near-neighbors of its own training data and
   accuracy looks better than true generalization. Blocking whole grid
   cells avoids that.

Outputs (per region), none of which overwrite evaluated_sightings_*.csv:
    thinned_positives_{region}.csv   - post-thin positives, all columns
                                        retained, + block_id
    train_positives_{region}.csv     - thinned positives in TRAIN blocks
    val_positives_{region}.csv       - thinned positives in VAL blocks
    block_assignments_{region}.csv   - block_id -> split, for reuse when
                                        splitting negatives consistently

Usage:
    python prepare_training_data.py
    python prepare_training_data.py --regions ME --min-spacing-m 250
    python prepare_training_data.py --block-size-m 3000 --val-fraction 0.2
"""
import os
import argparse
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

REGIONS_DEFAULT = ["ME", "NH", "VT"]

# Same boxes as analyze_grouse.py / download.py - kept in sync manually
# since this script only reads evaluated_sightings CSVs, not the boxes.
BOXES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.614, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}
MIN_SPACING_M_DEFAULT = 30
#MIN_SPACING_M_DEFAULT = 250     # ~grouse home-range scale; use 30 for
                                 # "guaranteed no shared raster pixel" instead
BLOCK_SIZE_M_DEFAULT = 3000     # matches KDE_BANDWIDTH_M in analyze_grouse.py
VAL_FRACTION_DEFAULT = 0.2
RANDOM_SEED_DEFAULT = 42

def thin_by_min_distance(df, min_spacing_m, seed):
    """Greedy thinning: shuffle, then keep a point only if it's farther
    than min_spacing_m from every already-kept point. Shuffling first
    (rather than keeping in file order) avoids a systematic bias toward
    whichever year/state happened to be concatenated first."""
    if len(df) == 0:
        return df

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(df))
    coords = df[['x_5070', 'y_5070']].values[order]

    kept_mask = np.zeros(len(df), dtype=bool)
    kept_coords = []
    tree = None
    for i, pt in enumerate(coords):
        if tree is None or len(kept_coords) == 0:
            keep = True
        else:
            dist, _ = tree.query(pt, k=1)
            keep = dist >= min_spacing_m
        if keep:
            kept_coords.append(pt)
            kept_mask[order[i]] = True
            tree = cKDTree(np.array(kept_coords))

    return df[kept_mask].copy()


def assign_spatial_blocks(df, box, block_size_m, val_fraction, seed):
    """Grid the region in EPSG:5070 meters, assign each occupied block a
    sequential id, then randomly assign whole blocks (not points) to
    train/val until the val block set holds roughly val_fraction of
    RECORDS (not blocks - blocks vary in point count, so this balances by
    record count while still splitting on whole blocks)."""
    min_lon, min_lat, max_lon, max_lat = box
    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    corners_x, corners_y = to_albers.transform(
        [min_lon, max_lon], [min_lat, max_lat])
    x0, y0 = min(corners_x), min(corners_y)

    bx = np.floor((df['x_5070'].values - x0) / block_size_m).astype(int)
    by = np.floor((df['y_5070'].values - y0) / block_size_m).astype(int)
    block_id = pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)

    block_counts = block_id.value_counts()
    rng = np.random.default_rng(seed)
    shuffled_blocks = block_counts.sample(frac=1, random_state=seed).index.tolist()

    target_val = int(round(val_fraction * len(df)))
    val_blocks, running = set(), 0
    for b in shuffled_blocks:
        if running >= target_val:
            break
        val_blocks.add(b)
        running += block_counts[b]

    split = block_id.map(lambda b: 'val' if b in val_blocks else 'train')
    return block_id, split


def main():
    parser = argparse.ArgumentParser(
        description="Thin positive records to a minimum spacing and assign "
                    "a spatial block train/val holdout, without modifying "
                    "data/pipeline/evaluated_sightings_*.csv.")
    parser.add_argument("--regions", nargs="+", default=REGIONS_DEFAULT)
    parser.add_argument("--min-spacing-m", type=float, default=MIN_SPACING_M_DEFAULT,
                        help="Minimum distance between kept positives "
                             "(default: %(default)s m)")
    parser.add_argument("--block-size-m", type=float, default=BLOCK_SIZE_M_DEFAULT,
                        help="Spatial block grid size for the holdout "
                             "(default: %(default)s m)")
    parser.add_argument("--val-fraction", type=float, default=VAL_FRACTION_DEFAULT,
                        help="Target fraction of records in validation "
                             "(default: %(default)s)")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED_DEFAULT)
    parser.add_argument("--habitat-only", action='store_true', default=True,
                        help="Restrict to vegetated habitat records "
                             "(nonveg_landcover == False). Default: on.")
    args = parser.parse_args()

    for region in args.regions:
        path = f"data/pipeline/evaluated_sightings_{region}.csv"
        print(f"\n##########################################")
        print(f"# REGION: {region}")
        print(f"##########################################")
        if not os.path.exists(path):
            print(f"  [!] {path} not found - run analyze_grouse.py first. Skipping.")
            continue

        df = pd.read_csv(path)
        n_loaded = len(df)
        if args.habitat_only and 'nonveg_landcover' in df.columns:
            df = df[~df['nonveg_landcover'].astype(bool)].copy()
        print(f"  {len(df):,} vegetated habitat records loaded (of {n_loaded:,} total).")

        if len(df) == 0:
            print("  [!] Nothing to thin. Skipping.")
            continue

        thinned = thin_by_min_distance(df, args.min_spacing_m, args.seed)
        pct_kept = 100 * len(thinned) / len(df)
        print(f"  Thinning at {args.min_spacing_m:.0f} m spacing: "
             f"{len(df):,} -> {len(thinned):,} records kept ({pct_kept:.1f}%).")

        block_id, split = assign_spatial_blocks(
            thinned, BOXES[region], args.block_size_m, args.val_fraction, args.seed)
        thinned = thinned.copy()
        thinned['block_id'] = block_id
        thinned['split'] = split

        n_blocks = thinned['block_id'].nunique()
        n_val_blocks = thinned.loc[thinned['split'] == 'val', 'block_id'].nunique()
        val_pct = 100 * (thinned['split'] == 'val').mean()
        print(f"  Spatial blocks: {args.block_size_m:.0f} m grid, "
             f"{n_blocks} occupied blocks, {n_val_blocks} assigned to "
             f"validation ({val_pct:.1f}% of records).")

        thinned_path = f"data/pipeline/thinned_positives_{region}.csv"
        train_path = f"data/pipeline/train_positives_{region}.csv"
        val_path = f"data/pipeline/val_positives_{region}.csv"
        blocks_path = f"data/pipeline/block_assignments_{region}.csv"

        thinned.to_csv(thinned_path, index=False)
        thinned[thinned['split'] == 'train'].to_csv(train_path, index=False)
        thinned[thinned['split'] == 'val'].to_csv(val_path, index=False)
        thinned[['block_id', 'split']].drop_duplicates('block_id').to_csv(
            blocks_path, index=False)

        print(f"  Saved {thinned_path}, {train_path}, {val_path}, {blocks_path}")
        print(f"  (evaluated_sightings_{region}.csv left untouched)")


if __name__ == "__main__":
    main()
