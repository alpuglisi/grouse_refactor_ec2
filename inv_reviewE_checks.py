"""Reviewer E evidence. Read-only.
1. Pooled negative pairs < 30 m  -> is there a missing acceptance invariant
   for S5's "thinning pooled" on negatives?
2. Negatives whose `state` column disagrees with the dissolved TIGER
   polygon -> would a MANDATORY, fail-on-disagreement verify_partition()
   over BOTH classes (S Acceptance) abort the rebuild?
3. NH box vs NH polygon + 64x64 patch margin.
"""
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box as shbox
from pyproj import Transformer
from scipy.spatial import cKDTree

R = ["ME", "NH", "VT"]
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(src=r)
                 for r in R], ignore_index=True)
pos = pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(src=r)
                 for r in R], ignore_index=True)
print(f"negatives on disk: {len(neg)}   positives(thinned): {len(pos)}")

# ---- 1. pooled <30 m pairs, negatives -------------------------------------
for name, df in (("negatives", neg), ("positives", pos)):
    x, y = t.transform(df.longitude.values, df.latitude.values)
    pr = cKDTree(np.column_stack([x, y])).query_pairs(30, output_type='ndarray')
    cross = sum(1 for i, j in pr if df.src.values[i] != df.src.values[j])
    print(f"  pooled {name}: {len(pr)} pairs < 30 m  ({cross} of them cross-region)")

# ---- 2. state column vs dissolved TIGER polygon ---------------------------
c = gpd.read_file("data/roads/tl_2023_us_county.zip")
c = c[c.STATEFP.isin(FIPS)].copy()
c["ST"] = c.STATEFP.map(FIPS)
poly = c.dissolve(by="ST").to_crs("EPSG:4326")
for name, df in (("negatives", neg), ("positives", pos)):
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude),
                         crs="EPSG:4326")
    j = gpd.sjoin(g, poly.reset_index()[["ST", "geometry"]],
                  how="left", predicate="within")
    j = j[~j.index.duplicated()]
    bad = j[j.ST.fillna("<none>") != j.state]
    print(f"\n  {name}: {len(bad)} of {len(j)} records where state != TIGER polygon")
    if len(bad):
        print(bad[["longitude", "latitude", "state", "src", "ST"]]
              .head(12).to_string(index=False))

# ---- 3. NH box vs polygon + 64x64 patch margin ----------------------------
from regions import BOXES
for r in R:
    p = poly.loc[r, "geometry"]
    b = BOXES[r]
    bb = shbox(*b)
    outside = p.difference(bb)
    print(f"\n  {r}: polygon bounds {tuple(round(v,4) for v in p.bounds)}")
    print(f"      box            {b}")
    print(f"      polygon area outside box: {100*outside.area/p.area:.4f} %")
    # 64 px * 30 m = 1920 m half-window 960 m; how much margin does the box give?
    pm = gpd.GeoSeries([p], crs="EPSG:4326").to_crs("EPSG:5070")
    bm = gpd.GeoSeries([bb], crs="EPSG:4326").to_crs("EPSG:5070")
    need = pm.buffer(32*30)          # half a 64 px window at 30 m
    short = need.difference(bm)
    print(f"      polygon+32px buffer area outside box: "
          f"{100*float(short.area.iloc[0])/float(need.area.iloc[0]):.4f} %")
