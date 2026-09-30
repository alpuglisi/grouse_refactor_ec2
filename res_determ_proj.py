"""res_determ_proj.py -- reprojection / block-boundary sensitivity, and the
cascade from one flipped record to the whole split.  Read-only.
"""
import numpy as np, pandas as pd, pyproj
from pyproj import Transformer
from pyproj.transformer import TransformerGroup
from scipy.spatial import cKDTree
from prepare_training_data import thin_by_min_distance

REGIONS = ("ME", "NH", "VT"); BLOCK = 3000.0; ORIGIN = (0.0, 0.0)
VF = 0.20; SEED = 42; SPACING = 30.0

print(f"pyproj {pyproj.__version__}  PROJ {pyproj.proj_version_str}  "
      f"network={pyproj.network.is_network_enabled()}")

fr = []
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    fr.append(d[d["state"] == r])
p = pd.concat(fr, ignore_index=True)
p = p[~p["nonveg_landcover"].astype(bool)]
p = p.drop_duplicates(subset=["longitude", "latitude", "year"]).reset_index(drop=True)
t = thin_by_min_distance(p, SPACING, SEED).reset_index(drop=True)
print(f"pooled {len(p):,} -> thinned {len(t):,}")

lon, lat = t["longitude"].values, t["latitude"].values

print("\n" + "=" * 78)
print("P1  stored x_5070/y_5070 vs recomputed with today's PROJ")
print("=" * 78)
tf = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
X, Y = tf.transform(lon, lat)
dx = np.abs(X - t["x_5070"].values); dy = np.abs(Y - t["y_5070"].values)
print(f"  max |dx| {dx.max():.3e} m   max |dy| {dy.max():.3e} m   "
      f"exact-equal rows {int(((dx == 0) & (dy == 0)).sum()):,}/{len(t):,}")
print(f"  transformer description : {tf.description}")
print(f"  operation              : {tf.to_proj4()!r}")

print("\n" + "=" * 78)
print("P2  candidate 4326->5070 operations PROJ could choose from")
print("=" * 78)
tg = TransformerGroup("EPSG:4326", "EPSG:5070", always_xy=True)
print(f"  {len(tg.transformers)} available, {len(tg.unavailable_operations)} "
      f"unavailable (missing grids)")
for i, tr in enumerate(tg.transformers[:6]):
    xi, yi = tr.transform(lon, lat)
    d = np.hypot(xi - X, yi - Y)
    print(f"   [{i}] {tr.description[:70]!r}\n        max offset vs chosen: "
          f"{d.max():.4f} m, median {np.median(d):.4f} m")
for op in tg.unavailable_operations[:6]:
    print(f"   [unavailable] {op.name[:90]}")

print("\n" + "=" * 78)
print("P3  distance from each record to the nearest 3 km block boundary")
print("=" * 78)
def edge_dist(v, origin):
    m = np.mod(v - origin, BLOCK)
    return np.minimum(m, BLOCK - m)
ex = edge_dist(t["x_5070"].values, ORIGIN[0])
ey = edge_dist(t["y_5070"].values, ORIGIN[1])
e = np.minimum(ex, ey)
for tol in (0.01, 0.1, 0.33, 0.5, 1.0, 2.0, 5.0, 10.0):
    print(f"  records within {tol:5.2f} m of a block edge: {int((e < tol).sum()):4d}"
          f"  ({100*(e < tol).mean():.4f}%)")
print(f"  minimum edge distance in the set: {e.min():.4f} m "
      f"(record {int(np.argmin(e))}, lon {lon[np.argmin(e)]:.5f} "
      f"lat {lat[np.argmin(e)]:.5f})")
srt = np.sort(e)[:8]
print(f"  eight smallest edge distances: {[round(float(z), 4) for z in srt]}")

print("\n" + "=" * 78)
print("P4  cascade: what does flipping ONE record's block do to the split?")
print("=" * 78)
def blocks_from(xv, yv, index):
    bx = np.floor((xv - ORIGIN[0]) / BLOCK).astype(int)
    by = np.floor((yv - ORIGIN[1]) / BLOCK).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=index)

def draw(bid, n, seed=SEED):
    c = bid.value_counts()
    order = c.sample(frac=1, random_state=seed).index.tolist()
    T = int(round(VF * n)); v, run = set(), 0
    for b in order:
        if run >= T: break
        v.add(b); run += c[b]
    return v

x0 = t["x_5070"].values.copy(); y0 = t["y_5070"].values.copy()
bid0 = blocks_from(x0, y0, t.index)
vb0 = draw(bid0, len(t))
iv0 = bid0.isin(vb0).values
xy = np.column_stack([x0, y0])
def stat(iv):
    d, _ = cKDTree(xy[~iv]).query(xy[iv], k=1)
    per = t.assign(v=iv).groupby("state").v.mean() * 100
    return (int(iv.sum()), tuple(round(z, 2) for z in per.values),
            round(float(np.median(d))), round(float((d < 1920).mean()*100), 2))
print(f"  baseline: {len(vb0)} val blocks, {stat(iv0)}")

i = int(np.argmin(e))
for shift in (0.4, 1.0):
    x1 = x0.copy(); y1 = y0.copy()
    # push the closest-to-edge record across its nearest boundary
    if ex[i] <= ey[i]:
        m = np.mod(x0[i] - ORIGIN[0], BLOCK)
        x1[i] = x0[i] + (shift if m > BLOCK / 2 else -shift)
    else:
        m = np.mod(y0[i] - ORIGIN[1], BLOCK)
        y1[i] = y0[i] + (shift if m > BLOCK / 2 else -shift)
    b1 = blocks_from(x1, y1, t.index)
    moved = int((b1 != bid0).sum())
    v1 = draw(b1, len(t)); iv1 = b1.isin(v1).values
    print(f"  after moving record {i} by {shift} m ({moved} record(s) change "
          f"block id): val blocks {len(v1)}, symmetric diff vs baseline "
          f"{len(v1 ^ vb0)}, Jaccard {len(v1 & vb0)/len(v1 | vb0):.4f}, "
          f"records changing split {int((iv1 != iv0).sum()):,} "
          f"({100*(iv1 != iv0).mean():.1f}%)  {stat(iv1)}")

print("\n  uniform grid shifts (a systematic datum/PROJ change):")
for s in (0.001, 0.01, 0.1, 1.0, 5.0):
    b1 = blocks_from(x0 + s, y0 + s, t.index)
    moved = int((b1 != bid0).sum())
    v1 = draw(b1, len(t)); iv1 = b1.isin(v1).values
    print(f"   shift {s:6.3f} m -> {moved:4d} records change block, "
          f"val-block Jaccard {len(v1 & vb0)/len(v1 | vb0):.4f}, "
          f"{int((iv1 != iv0).sum()):,} records change split "
          f"({100*(iv1 != iv0).mean():.1f}%)  {stat(iv1)}")

print("\n" + "=" * 78)
print("P5  does a sub-metre shift change the THINNED set as well?")
print("=" * 78)
for s in (0.001, 0.01, 0.1, 1.0):
    q = p.copy()
    q["x_5070"] = q["x_5070"] + s
    q["y_5070"] = q["y_5070"] + s
    tt = thin_by_min_distance(q, SPACING, SEED)
    print(f"   shift {s:6.3f} m -> thinned {len(tt):,} "
          f"(baseline {len(t):,})")
