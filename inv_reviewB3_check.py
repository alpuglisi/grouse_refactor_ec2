"""Round-3 review: verify v3's I2/I3 invariant numbers independently, and
measure the cost v3's polygon-based assertion (b) adds to EVERY dataset
build (train.py / calibrate.py / bench_pipeline.py). Read-only."""
import time, numpy as np, pandas as pd
from pyproj import Transformer
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def gid(d,bs=3000):
    x,y=t.transform(d.longitude.values,d.latitude.values)
    return np.array([f"{a}_{b}" for a,b in zip(np.floor(x/bs).astype(int),
                                               np.floor(y/bs).astype(int))])
rows=[]
for r in R:
    for split in ("train","val"):
        p=pd.read_csv(f"data/pipeline/{split}_positives_{r}.csv")[["longitude","latitude"]]
        n=pd.read_csv(f"data/negatives/{split}_negatives_{r}.csv")[["longitude","latitude"]]
        for kind,d in (("pos",p),("neg",n)):
            d=d.copy(); d["split"]=split; d["kind"]=kind; d["region"]=r; rows.append(d)
a=pd.concat(rows,ignore_index=True)
a["gb"]=gid(a)
tr=set(a.loc[a.split=="train","gb"]); va=set(a.loc[a.split=="val","gb"])
print(f"I2  global 3 km blocks holding BOTH a train and a val record "
      f"(either class): {len(tr&va)}    CR claims 882")
vn=a[(a.split=="val")&(a.kind=="neg")]
print(f"I3  val negatives sharing a global block with ANY train record: "
      f"{vn.gb.isin(tr).mean():.1%}   CR claims 37.2%")
vp=a[(a.split=="val")&(a.kind=="pos")]
print(f"    (val positives sharing a block with any train record: "
      f"{vp.gb.isin(tr).mean():.1%})")
# I1: pooled positive pairs < 30 m
from scipy.spatial import cKDTree
P=a[a.kind=="pos"][["longitude","latitude"]]
x,y=t.transform(P.longitude.values,P.latitude.values)
xy=np.column_stack([x,y])
pairs=cKDTree(xy).query_pairs(30.0)
print(f"I1  pooled positive pairs closer than 30 m: {len(pairs)}   "
      f"CR claims 1690")

print("\n=== cost of v3's polygon assertion (b) per dataset build ===")
t0=time.time(); import geopandas as gpd; t_imp=time.time()-t0
t0=time.time(); cty=gpd.read_file("data/roads/tl_2023_us_county.zip"); t_rd=time.time()-t0
t0=time.time()
st=cty[cty.STATEFP.isin(["23","33","50"])].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
t_dis=time.time()-t0
from shapely.geometry import Point
t0=time.time()
g=gpd.GeoDataFrame(a.copy(),geometry=[Point(p,q) for p,q in zip(a.longitude,a.latitude)],crs="EPSG:4326")
j=gpd.sjoin(g,st[["STATEFP","geometry"]],how="left",predicate="within"); t_sj=time.time()-t0
print(f"  import geopandas {t_imp:.1f}s | read_file(83 MB zip) {t_rd:.1f}s | "
      f"dissolve+reproject {t_dis:.1f}s | sjoin {len(a)} pts {t_sj:.1f}s")
print(f"  TOTAL added to every build_datasets() call: {t_imp+t_rd+t_dis+t_sj:.1f}s")
print(f"  counties loaded: {len(cty)} rows (national file)")
