"""INDEPENDENT REVIEW of CR-0006 (read-only). Re-derives the proposed
pipeline from the CURRENT source of prepare_training_data.py instead of
from the CR's prose, and from evaluated_sightings_*.csv (the real input
of the proposed rebuild) instead of from the already-thinned files the
author's simulation used."""
import time
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
from scipy.spatial import cKDTree

from prepare_training_data import (thin_by_min_distance, BOXES,
                                   BLOCK_SIZE_M_DEFAULT,
                                   MIN_SPACING_M_DEFAULT,
                                   VAL_FRACTION_DEFAULT,
                                   RANDOM_SEED_DEFAULT,
                                   assign_spatial_blocks)

REGIONS = ["ME", "NH", "VT"]
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
BLOCK_M = BLOCK_SIZE_M_DEFAULT
SEED = RANDOM_SEED_DEFAULT
VAL_FRAC = VAL_FRACTION_DEFAULT
print(f"constants from source: MIN_SPACING={MIN_SPACING_M_DEFAULT} "
      f"BLOCK_M={BLOCK_M} VAL_FRAC={VAL_FRAC} SEED={SEED}")

# ---------------------------------------------------------------- 0. grid
print("\n=== 0. global block-id math: injectivity / negative coords ===")
def gid(x, y, bs=BLOCK_M):
    bx = np.floor(np.asarray(x, dtype=float) / bs).astype(int)
    by = np.floor(np.asarray(y, dtype=float) / bs).astype(int)
    return np.array([f"{a}_{b}" for a, b in zip(bx, by)])

probe = [(0.0, 0.0), (-1.0, -1.0), (-3000.0, 3000.0), (2999.9, -2999.9),
         (-3000.1, 0.0), (1.0e6, -2.0e6), (-1.0e6, 2.0e6)]
for (x, y) in probe:
    print(f"   x={x:>10.1f} y={y:>10.1f} -> {gid([x],[y])[0]}")
# injectivity over a dense integer lattice incl. negatives
bx = np.arange(-500, 500)
XX, YY = np.meshgrid(bx, bx)
ids = np.char.add(np.char.add(XX.ravel().astype(str), "_"),
                  YY.ravel().astype(str))
print(f"   lattice {ids.size} (bx,by) pairs from -500..499 -> "
      f"{len(set(ids.tolist()))} distinct ids "
      f"({'INJECTIVE' if len(set(ids.tolist()))==ids.size else 'COLLIDES'})")
t5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
corner_pts = []
for r, b in BOXES.items():
    corner_pts += [(b[0], b[1]), (b[2], b[3])]
cx, cy = t5070.transform([p[0] for p in corner_pts], [p[1] for p in corner_pts])
print(f"   study-area EPSG:5070 x range {min(cx):.0f}..{max(cx):.0f}  "
      f"y range {min(cy):.0f}..{max(cy):.0f}  (both strictly positive: "
      f"{min(cx) > 0 and min(cy) > 0})")

# ------------------------------------------------- 1. load real inputs
print("\n=== 1. the real input of the proposed rebuild ===")
frames = []
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    d["src_region"] = r
    n0 = len(d)
    hab = d[~d["nonveg_landcover"].astype(bool)].copy()
    print(f"   {r}: {n0} evaluated rows, {len(hab)} habitat-only "
          f"(nonveg dropped {n0-len(hab)})")
    frames.append(hab)
pool = pd.concat(frames, ignore_index=True)
print(f"   pooled habitat rows: {len(pool)}")
print(f"   (author's simulation instead pooled the already-thinned files: "
      f"{sum(len(pd.read_csv(f'data/pipeline/thinned_positives_{r}.csv')) for r in REGIONS)} rows)")
# column drift between evaluated and the thinned files on disk
ev_cols = set(pd.read_csv('data/pipeline/evaluated_sightings_NH.csv', nrows=1).columns)
th_cols = set(pd.read_csv('data/pipeline/thinned_positives_NH.csv', nrows=1).columns)
print(f"   columns only in evaluated: {sorted(ev_cols - th_cols)}")
print(f"   columns only in thinned  : {sorted(th_cols - ev_cols)}")

# ------------------------------------------------- 2. state partition
print("\n=== 2. state-polygon partition of the REAL input ===")
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
st = (cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP")
      .reset_index().to_crs("EPSG:4326"))
g = gpd.GeoDataFrame(pool.copy(),
                     geometry=[Point(a, b) for a, b in
                               zip(pool.longitude, pool.latitude)],
                     crs="EPSG:4326")
j = gpd.sjoin(g, st[["STATEFP", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
pool["poly_state"] = j.STATEFP.map(FIPS).values
nost = pool.poly_state.isna()
print(f"   habitat positives in NO state polygon: {int(nost.sum())} of {len(pool)}")
if nost.any():
    print(pool[nost].groupby('src_region').size().to_string())
    print("   lon/lat of the first few:")
    print(pool.loc[nost, ['longitude', 'latitude', 'src_region', 'state']]
          .head(12).to_string())
print("   src_region -> poly_state crosstab:")
print(pd.crosstab(pool.src_region, pool.poly_state.fillna("NONE")).to_string())
print(f"   rows whose CSV 'state' column (source file) != poly_state: "
      f"{int((pool.state != pool.poly_state).sum())} of {len(pool)}  "
      f"<-- prepare_training_data cannot use 'state' as the region")

# ------------------------------------------------- 3. dedup
print("\n=== 3. pooled de-duplication on rounded coordinates ===")
key = (pool.longitude.round(5).astype(str) + "," +
       pool.latitude.round(5).astype(str))
pool["key"] = key
ded = pool.loc[~key.duplicated()].copy()
print(f"   {len(pool)} pooled rows -> {len(ded)} unique rounded coords "
      f"(removes {len(pool)-len(ded)})")
ded = ded[ded.poly_state.notna()].copy()
print(f"   after dropping no-state records: {len(ded)}")
print("   by assigned state:", ded.poly_state.value_counts().to_dict())

# ------------------------------------------------- 4. thin ONCE, pooled
print("\n=== 4. thinning: pooled-once vs per-region (real algorithm) ===")
t0 = time.time()
th_pooled = thin_by_min_distance(ded, MIN_SPACING_M_DEFAULT, SEED)
t_pooled = time.time() - t0
print(f"   pooled thin: {len(ded)} -> {len(th_pooled)} kept "
      f"({100*len(th_pooled)/len(ded):.1f}%) in {t_pooled:.1f}s")
tot, t1 = 0, time.time()
for r in REGIONS:
    sub = ded[ded.poly_state == r]
    tot += len(thin_by_min_distance(sub, MIN_SPACING_M_DEFAULT, SEED))
print(f"   per-region thin of the SAME partitioned input: {tot} kept "
      f"in {time.time()-t1:.1f}s  (pooled removes {tot-len(th_pooled)} more)")

# ------------------------------------------------- 5. global split
print("\n=== 5. one global block grid + one draw (source algorithm) ===")
thp = th_pooled.copy()
thp["block_id"] = gid(thp.x_5070.values, thp.y_5070.values)
counts = thp.block_id.value_counts()
order = counts.sample(frac=1, random_state=SEED).index.tolist()
target = int(round(VAL_FRAC * len(thp)))
val_blocks, run = set(), 0
for b in order:
    if run >= target:
        break
    val_blocks.add(b)
    run += counts[b]
thp["split"] = np.where(thp.block_id.isin(val_blocks), "val", "train")
nval = int((thp.split == "val").sum())
print(f"   pooled positives: {len(thp)}  occupied blocks: {len(counts)}")
print(f"   target val {target}  val blocks {len(val_blocks)}  val records "
      f"{nval} ({nval/len(thp):.2%})  overshoot {nval-target}")
print(f"   largest block holds {counts.max()} records; "
      f"blocks with 1 record: {(counts==1).sum()}")
tr, va = thp[thp.split == "train"], thp[thp.split == "val"]
print(f"   exact coord collisions train&val: "
      f"{len(set(tr.key) & set(va.key))}")
d, _ = cKDTree(tr[["x_5070", "y_5070"]].values).query(
    va[["x_5070", "y_5070"]].values, k=1)
for m in (30, 300, 1500, 3000):
    print(f"   val points with a train positive within {m:>5} m: "
          f"{(d <= m).mean():6.2%}  ({int((d<=m).sum())} of {len(va)})")
print("   val by state:", va.poly_state.value_counts().to_dict())
print("   train by state:", tr.poly_state.value_counts().to_dict())
for r in REGIONS:
    s = thp[thp.poly_state == r]
    print(f"     {r}: {len(s)} records, val fraction "
          f"{(s.split=='val').mean():.2%}")
print("   CR claims: 6712 positives / 4069 blocks / 763 val blocks / "
      "1344 val (20.0%) / 0.0% 1.3% 64.4%")

# ---------------------------------------- 6. current-data support check
print("\n=== 6. positive/negative 3km-block support, CURRENT data ===")
from grouse_data import GrouseData
data = GrouseData()
def blocks_of(df):
    x, y = t5070.transform(df.longitude.values, df.latitude.values)
    return set(gid(x, y).tolist())
for split in ("train", "val"):
    pb, nb = set(), set()
    for r in REGIONS:
        rd = data[r]
        p = blocks_of(rd.positives(split))
        n = blocks_of(rd.negatives(split))
        pb |= p
        nb |= n
        inter = len(p & n)
        print(f"   {r} {split}: pos blocks {len(p)} neg blocks {len(n)} "
              f"shared {inter}  jaccard {inter/len(p|n):.3f}  "
              f"pos-only {len(p-n)} ({len(p-n)/len(p):.1%}) "
              f"neg-only {len(n-p)} ({len(n-p)/len(n):.1%})")
    inter = len(pb & nb)
    print(f"   POOLED {split}: pos {len(pb)} neg {len(nb)} shared {inter} "
          f"jaccard {inter/len(pb|nb):.3f} pos-only {len(pb-nb)/len(pb):.1%} "
          f"neg-only {len(nb-pb)/len(nb):.1%}")

# ---------------------------------------- 7. support check, POST-fix sim
print("\n=== 7. support check on the SIMULATED post-fix data ===")
# post-fix positives = section 5; negatives keep their own coordinates
# (their acquisition is unchanged by this CR) but are re-split on the
# global grid and resampled 1:1 per region/split.
negs = []
for r in REGIONS:
    n = data[r].negatives("all").copy()
    n["region"] = r
    negs.append(n)
neg = pd.concat(negs, ignore_index=True)
nx, ny = t5070.transform(neg.longitude.values, neg.latitude.values)
neg["block_id"] = gid(nx, ny)
neg["split"] = np.where(neg.block_id.isin(val_blocks), "val", "train")
rng = np.random.default_rng(SEED)
for split in ("train", "val"):
    pb, nb = set(), set()
    for r in REGIONS:
        p = thp[(thp.poly_state == r) & (thp.split == split)]
        cand = neg[(neg.region == r) & (neg.split == split)]
        take = min(len(p), len(cand))
        pick = cand.sample(n=take, random_state=SEED) if take else cand
        sp = set(p.block_id.tolist())
        sn = set(pick.block_id.tolist())
        pb |= sp
        nb |= sn
        print(f"   {r} {split}: pos {len(p)} (blocks {len(sp)}) "
              f"neg avail {len(cand)} sampled {take} (blocks {len(sn)}) "
              f"shared {len(sp&sn)} jaccard "
              f"{len(sp&sn)/max(len(sp|sn),1):.3f} "
              f"pos-only {len(sp-sn)/max(len(sp),1):.1%}")
    print(f"   POOLED {split}: jaccard "
          f"{len(pb&nb)/max(len(pb|nb),1):.3f} "
          f"pos-only {len(pb-nb)/max(len(pb),1):.1%} "
          f"neg-only {len(nb-pb)/max(len(nb),1):.1%}")

# ---------------------------------------- 8. year-gap interaction
print("\n=== 8. does filter_by_year_gap (train.py, pre-pool) matter? ===")
import train as T
feats = ["evt", "evh", "evc", "sclass", "fdist", "ch", "cc", "tcc", "nlcd",
         "road_dist", "tsd", "balive", "tpa_live", "qmd", "carbon_dwn"]
for r in REGIONS:
    rd = data[r]
    for split in ("train", "val"):
        for kind, get in (("pos", rd.positives), ("neg", rd.negatives)):
            df = get(split)
            f = T.filter_by_year_gap(df, rd, feats, 2, f"{kind} {split}", r)
            print(f"   {r} {kind} {split}: {len(df)} -> {len(f)}")
print("\ndone")
