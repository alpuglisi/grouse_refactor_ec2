"""CR-0006 review, part 2 (read-only): what the state partition does to
generate_negatives.py's 300 m exclusion buffer, and whether the negative
candidate pool can still meet the per-region val quota under one global
block split. Also alternative statistics for the proposed
positive/negative support assertion."""
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
from scipy.spatial import cKDTree

from prepare_training_data import (thin_by_min_distance, BLOCK_SIZE_M_DEFAULT,
                                   MIN_SPACING_M_DEFAULT, VAL_FRACTION_DEFAULT,
                                   RANDOM_SEED_DEFAULT)
from generate_negatives import BUFFER_M, MAX_COORD_UNCERTAINTY_M
from grouse_data import GrouseData

REGIONS = ["ME", "NH", "VT"]
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
SEED, BLOCK_M, VAL_FRAC = RANDOM_SEED_DEFAULT, BLOCK_SIZE_M_DEFAULT, VAL_FRACTION_DEFAULT
t5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
data = GrouseData()


def gid(x, y, bs=BLOCK_M):
    bx = np.floor(np.asarray(x, float) / bs).astype(int)
    by = np.floor(np.asarray(y, float) / bs).astype(int)
    return np.array([f"{a}_{b}" for a, b in zip(bx, by)])


def state_of(df):
    cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
    st = (cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP")
          .reset_index().to_crs("EPSG:4326"))
    g = gpd.GeoDataFrame(df.copy(),
                         geometry=[Point(a, b) for a, b in
                                   zip(df.longitude, df.latitude)],
                         crs="EPSG:4326")
    j = gpd.sjoin(g, st[["STATEFP", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j.STATEFP.map(FIPS).values


# ---------------------------------------------------------------- inputs
ev = []
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    d["src_region"] = r
    ev.append(d)
ev = pd.concat(ev, ignore_index=True)
ev["poly_state"] = state_of(ev)
ev["key"] = (ev.longitude.round(5).astype(str) + "," +
             ev.latitude.round(5).astype(str))
ev_u = ev.loc[~ev.key.duplicated()].copy()      # every known grouse location
print(f"ALL evaluated rows {len(ev)} -> unique coords {len(ev_u)} "
      f"(veg + nonveg; the buffer uses every row)")
print("   unique grouse locations by polygon state:",
      ev_u.poly_state.value_counts(dropna=False).to_dict())

print("\n=== A. 300 m buffer source: box-clipped (now) vs state-clipped "
      "(post-CR) vs pooled (PA-0018-correct) ===")
for r in REGIONS:
    cand = pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    n0 = len(cand)
    cand = cand[~(cand.coord_uncertainty_m > MAX_COORD_UNCERTAINTY_M)
                .fillna(False)].copy()
    k = cand[["longitude", "latitude"]].round(5)
    cand = cand.loc[~k.duplicated()].copy()
    cx, cy = t5070.transform(cand.longitude.values, cand.latitude.values)
    cand["x_5070"], cand["y_5070"] = cx, cy
    cand = thin_by_min_distance(cand, MIN_SPACING_M_DEFAULT, SEED)
    cxy = cand[["x_5070", "y_5070"]].values

    def survivors(src, label):
        x, y = t5070.transform(src.longitude.values, src.latitude.values)
        d, _ = cKDTree(np.column_stack([x, y])).query(cxy, k=1)
        keep = d > BUFFER_M
        print(f"   {r}: buffer against {label:<34} "
              f"{len(src):>5} grouse locs -> {int(keep.sum()):>5} of "
              f"{len(cand)} candidates survive")
        return keep

    now = survivors(data[r].evaluated, "rd.evaluated (box-clipped, NOW)")
    post = survivors(ev_u[ev_u.poly_state == r],
                     f"state {r} only (POST-CR)")
    allp = survivors(ev_u, "ALL grouse locations (correct)")
    print(f"   {r}: post-CR admits {int((post & ~now).sum())} candidates "
          f"that the CURRENT box-clipped buffer excludes, and "
          f"{int((allp & ~post).sum())} fewer than the pooled-source "
          f"buffer would; candidates within {BUFFER_M} m of an "
          f"out-of-state grouse location: {int((post & ~allp).sum())}")

print("\n=== B. can the candidate pool still fill a 1:1 val quota under a "
      "GLOBAL block split? ===")
# rebuild the proposed positive split (same as inv_reviewB_pipeline.py)
hab = ev[~ev.nonveg_landcover.astype(bool)].copy()
hab = hab.loc[~hab.key.duplicated()].copy()
hab = hab[hab.poly_state.notna()]
thp = thin_by_min_distance(hab, MIN_SPACING_M_DEFAULT, SEED)
thp["block_id"] = gid(thp.x_5070.values, thp.y_5070.values)
counts = thp.block_id.value_counts()
order = counts.sample(frac=1, random_state=SEED).index.tolist()
target, val_blocks, run = int(round(VAL_FRAC * len(thp))), set(), 0
for b in order:
    if run >= target:
        break
    val_blocks.add(b)
    run += counts[b]
thp["split"] = np.where(thp.block_id.isin(val_blocks), "val", "train")
print(f"   proposed positives {len(thp)}, val {int((thp.split=='val').sum())}")
val_frac_blocks = len(val_blocks) / len(counts)
print(f"   block-level val fraction (what split_for_unassigned would "
      f"hash at): {val_frac_blocks:.3f}")

import hashlib
def hash_split(b, vf, seed=SEED):
    h = int(hashlib.md5(f"{seed}:{b}".encode()).hexdigest(), 16)
    return 'val' if (h % 10_000) < vf * 10_000 else 'train'

for r in REGIONS:
    cand = pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    cand = cand[~(cand.coord_uncertainty_m > MAX_COORD_UNCERTAINTY_M)
                .fillna(False)].copy()
    k = cand[["longitude", "latitude"]].round(5)
    cand = cand.loc[~k.duplicated()].copy()
    cx, cy = t5070.transform(cand.longitude.values, cand.latitude.values)
    cand["x_5070"], cand["y_5070"] = cx, cy
    cand = thin_by_min_distance(cand, MIN_SPACING_M_DEFAULT, SEED)
    src = ev_u[ev_u.poly_state == r]
    x, y = t5070.transform(src.longitude.values, src.latitude.values)
    d, _ = cKDTree(np.column_stack([x, y])).query(
        cand[["x_5070", "y_5070"]].values, k=1)
    cand = cand[d > BUFFER_M].copy()
    cand["block_id"] = gid(cand.x_5070.values, cand.y_5070.values)
    assigned = cand.block_id.isin(set(thp.block_id))
    sp = np.where(cand.block_id.isin(val_blocks), "val",
                  np.where(assigned, "train",
                           [hash_split(b, val_frac_blocks)
                            for b in cand.block_id]))
    pos = thp[thp.poly_state == r]
    for split in ("train", "val"):
        need = int((pos.split == split).sum())
        have = int((sp == split).sum())
        flag = "  <-- SHORTFALL" if have < need else ""
        print(f"   {r} {split}: positives {need:>5}  candidates "
              f"available (pre-extraction-nodata) {have:>5}{flag}")
    print(f"      unassigned-block candidates (hash-split): "
          f"{int((~assigned).sum())} of {len(cand)}")

print("\n=== C. candidate statistics for the support assertion ===")
# pooled post-fix positives vs the negatives that would be drawn
for gsize in (3000, 10000, 30000):
    pb = set(gid(thp.x_5070.values, thp.y_5070.values, gsize).tolist())
    negs = []
    for r in REGIONS:
        n = data[r].negatives("all").copy()
        n["region"] = r
        negs.append(n)
    neg = pd.concat(negs, ignore_index=True)
    nx, ny = t5070.transform(neg.longitude.values, neg.latitude.values)
    nb = set(gid(nx, ny, gsize).tolist())
    print(f"   grid {gsize:>6} m: pos blocks {len(pb)} neg blocks {len(nb)} "
          f"jaccard {len(pb & nb)/len(pb | nb):.3f} "
          f"pos-only {len(pb-nb)/len(pb):.1%}")

print("   per-partition-unit class composition (the BUG-0029 statistic):")
neg_st = {}
for r in REGIONS:
    n = data[r].negatives("all")
    s = state_of(n)
    neg_st[r] = pd.Series(s).value_counts(dropna=False).to_dict()
    p = data[r].positives("all")
    ps = pd.Series(state_of(p)).value_counts(dropna=False).to_dict()
    print(f"     CURRENT {r}: pos {ps}   neg {neg_st[r]}")
for r in REGIONS:
    p = thp[thp.poly_state == r]
    print(f"     POST-CR {r}: pos {{'{r}': {len(p)}}}   neg {neg_st[r]}")

print("\n=== D. nearest-negative distance for positives ===")
negs = []
for r in REGIONS:
    n = data[r].negatives("all").copy()
    negs.append(n)
neg = pd.concat(negs, ignore_index=True)
nx, ny = t5070.transform(neg.longitude.values, neg.latitude.values)
tree = cKDTree(np.column_stack([nx, ny]))
for label, P in (("CURRENT pooled positives",
                  pd.concat([data[r].positives("all") for r in REGIONS],
                            ignore_index=True)),
                 ("POST-CR pooled positives", thp)):
    px, py = t5070.transform(P.longitude.values, P.latitude.values)
    d, _ = tree.query(np.column_stack([px, py]), k=1)
    print(f"   {label}: median nearest-negative {np.median(d):,.0f} m, "
          f"p90 {np.percentile(d,90):,.0f} m, "
          f"share with no negative within 3 km {(d>3000).mean():.1%}")
print("\ndone")
