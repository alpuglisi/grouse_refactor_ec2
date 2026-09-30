"""Sizing data for CR-0006: what a state-polygon partition + one global
block split would actually do to the existing records. Read-only."""
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from shapely.geometry import Point
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from regions import BOXES

REGIONS = ["ME", "NH", "VT"]
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
BLOCK_M, VAL_FRAC, SEED = 3000, 0.2, 42
data = GrouseData()

rows = []
for reg in REGIONS:
    rd = data[reg]
    for kind, get in (("pos", rd.positives), ("neg", rd.negatives)):
        for split in ("train", "val"):
            d = get(split)[["longitude", "latitude"]].copy()
            d["src_region"], d["kind"], d["old_split"] = reg, kind, split
            rows.append(d)
allr = pd.concat(rows, ignore_index=True)
allr["key"] = (allr.longitude.round(5).astype(str) + "," +
               allr.latitude.round(5).astype(str))

cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
cty = cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
g = gpd.GeoDataFrame(allr, geometry=[Point(x, y) for x, y in
                                     zip(allr.longitude, allr.latitude)],
                     crs="EPSG:4326")
j = gpd.sjoin(g, cty[["STATEFP", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
allr["state"] = j.STATEFP.map(FIPS).values

print("=== 1. Does a state partition cover every record? ===")
print(f"records with no state (outside all three polygons): "
      f"{int(allr.state.isna().sum())} of {len(allr)}")
print(allr.groupby(["kind"]).state.apply(lambda s: s.isna().sum()).to_string())

print("\n=== 2. Records whose region would CHANGE ===")
u = allr.drop_duplicates(["kind", "key"]).copy()
ch = u[u.state.notna() & (u.state != u.src_region)]
print(f"unique (kind,coord) records: {len(u)}")
print("  by kind, src_region -> state:")
print(allr[allr.state.notna() & (allr.state != allr.src_region)]
      .groupby(["kind", "src_region", "state"]).size().to_string())

print("\n=== 3. Dataset size before/after de-duplication ===")
for kind in ("pos", "neg"):
    k = allr[allr.kind == kind]
    print(f"  {kind}: {len(k)} pooled rows -> {k.key.nunique()} unique coords "
          f"(removes {len(k)-k.key.nunique()} duplicate rows)")
    if kind == "pos":
        print("     unique coords by assigned state:",
              k.drop_duplicates('key').state.value_counts().to_dict())

print("\n=== 4. Is every record inside its assigned state's BOX? ===")
for st in REGIONS:
    s = allr[allr.state == st]
    lo, la, hi, ha = BOXES[st]
    out = ~(s.longitude.between(lo, hi) & s.latitude.between(la, ha))
    print(f"  {st}: {int(out.sum())} of {len(s)} records fall OUTSIDE BOXES['{st}']")
    if out.any():
        print("     lon range of outliers:",
              s[out].longitude.min(), s[out].longitude.max(),
              "| lat:", s[out].latitude.min(), s[out].latitude.max())

print("\n=== 5. Is every record's 64x64 window inside its state's raster? ===")
for st in REGIONS:
    rd = data[st]
    p = rd.latest_raster_path("evt")
    with rasterio.open(p) as src:
        t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        s = allr[allr.state == st]
        x, y = t.transform(s.longitude.values, s.latitude.values)
        from rasterio.transform import rowcol
        r, c = rowcol(src.transform, x, y)
        r, c = np.asarray(r), np.asarray(c)
        bad = ((r - 32 < 0) | (c - 32 < 0) |
               (r + 32 > src.height) | (c + 32 > src.width))
    print(f"  {st}: {int(bad.sum())} of {len(s)} records lack a full 64x64 "
          f"window in {p.split('/')[-1]}")

print("\n=== 6. One GLOBAL block grid (origin EPSG:5070 (0,0)), one draw ===")
to5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
x, y = to5070.transform(allr.longitude.values, allr.latitude.values)
allr["x"], allr["y"] = x, y
allr["gblock"] = (np.floor(x / BLOCK_M).astype(int).astype(str) + "_" +
                  np.floor(y / BLOCK_M).astype(int).astype(str))
pos = allr[allr.kind == "pos"].drop_duplicates("key").copy()
counts = pos.gblock.value_counts()
rng_order = counts.sample(frac=1, random_state=SEED).index.tolist()
target = int(round(VAL_FRAC * len(pos)))
val_blocks, run = set(), 0
for b in rng_order:
    if run >= target: break
    val_blocks.add(b); run += counts[b]
pos["new_split"] = np.where(pos.gblock.isin(val_blocks), "val", "train")
print(f"  pooled unique positives: {len(pos)}  occupied blocks: {len(counts)}")
print(f"  val blocks: {len(val_blocks)}  val records: {int((pos.new_split=='val').sum())} "
      f"({(pos.new_split=='val').mean():.1%})")
tr = pos[pos.new_split == "train"]; va = pos[pos.new_split == "val"]
print(f"  coords in BOTH train and val: {len(set(tr.key) & set(va.key))}  (was 522)")
d, _ = cKDTree(tr[["x","y"]].values).query(va[["x","y"]].values, k=1)
for m in (30, 300, 3000):
    print(f"  val with a train positive within {m:>4} m: {(d<=m).mean():6.1%}  "
          f"(pooled before: {[31.7,32.6,74.7][[30,300,3000].index(m)]}%)")
print("  new val split by state:", va.state.value_counts().to_dict())
print("  new train split by state:", tr.state.value_counts().to_dict())
