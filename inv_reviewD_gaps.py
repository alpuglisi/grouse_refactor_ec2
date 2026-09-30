import numpy as np, pandas as pd, rasterio
from rasterio.windows import Window
from scipy.spatial import cKDTree
from pyproj import Transformer
REG=["ME","NH","VT"]

# ---- GAP 1: 300 m buffer is per-region today; no acceptance gate makes it 0 ----
ev=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in REG],ignore_index=True)
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
ex,ey=T.transform(ev.longitude.values,ev.latitude.values)
tree=cKDTree(np.column_stack([ex,ey]))
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(region=r) for r in REG],ignore_index=True)
d,_=tree.query(neg[["x_5070","y_5070"]].values,k=1)
print("=== GAP 1: selected negatives vs POOLED grouse locations ===")
print(f"  within 300 m of a POOLED grouse location: {(d<=300).sum()} of {len(neg)} ({100*(d<=300).mean():.2f}%)")
for r in REG:
    m=(neg.region==r).values
    print(f"    {r}: {(d[m]<=300).sum()} of {m.sum()} ({100*(d[m]<=300).mean():.2f}%)")
print(f"  within 30 m:  {(d<=30).sum()}   within 100 m: {(d<=100).sum()}")
# same-region baseline
for r in REG:
    e=ev[ev.index.isin(ev.index)]  # placeholder
ev_by={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in REG}
for r in REG:
    e=ev_by[r]; x,y=T.transform(e.longitude.values,e.latitude.values)
    t2=cKDTree(np.column_stack([x,y])); m=(neg.region==r).values
    d2,_=t2.query(neg.loc[m,["x_5070","y_5070"]].values,k=1)
    print(f"    {r}: within 300 m of its OWN region's sightings: {(d2<=300).sum()} (this is what the code enforces)")

# ---- GAP 2: nodata INSIDE the 64x64 window (invariant only checks the centre) ----
print("\n=== GAP 2: nodata share inside 64x64 windows, NH road_dist (already-fixed raster) ===")
tr=pd.read_csv("data/pipeline/train_positives_NH.csv")
src=rasterio.open("data/landfire/NH_2023_road_dist.tif")
tt=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
xs,ys=tt.transform(tr.longitude.values,tr.latitude.values)
rows,cols=rasterio.transform.rowcol(src.transform,xs,ys)
rows=np.asarray(rows); cols=np.asarray(cols)
half=32; fr=[]; centre_nd=0
for rr,cc in zip(rows,cols):
    a=src.read(1,window=Window(cc-half,rr-half,64,64),boundless=True,fill_value=src.nodata)
    fr.append(float((a==src.nodata).mean()))
    c=src.read(1,window=Window(cc,rr,1,1),boundless=True,fill_value=src.nodata)
    centre_nd += int(c[0,0]==src.nodata)
fr=np.array(fr)
print(f"  NH train positives: {len(fr)}")
print(f"  centre pixel nodata: {centre_nd}  <- the CR's invariant")
print(f"  records with ANY nodata in the 64x64 window: {(fr>0).sum()} ({100*(fr>0).mean():.2f}%)")
print(f"  records with >10% window nodata: {(fr>0.10).sum()};  >25%: {(fr>0.25).sum()};  >50%: {(fr>0.50).sum()}")
print(f"  max window nodata fraction: {fr.max():.3f}")
