import numpy as np, pandas as pd, rasterio
from scipy.spatial import cKDTree
print("== CR-0007: is there any invariant covering the NEGATIVE side's own"
      "  30 m spacing / within-split duplicates?  Today's values: ==")
tn=pd.concat([pd.read_csv(f"data/negatives/train_negatives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
vn=pd.concat([pd.read_csv(f"data/negatives/val_negatives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
for nm,d in (("train",tn),("val",vn),("pooled",pd.concat([tn,vn],ignore_index=True))):
    xy=d[["x_5070","y_5070"]].values
    dup=int(d[["longitude","latitude"]].round(5).duplicated().sum())
    print(f"  negatives {nm:7s} n={len(d):5d}  30 m pairs={len(cKDTree(xy).query_pairs(30.0)):4d}"
          f"  duplicate 5dp coords={dup}")
tp=pd.concat([pd.read_csv(f"data/pipeline/train_positives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
vp=pd.concat([pd.read_csv(f"data/pipeline/val_positives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
for nm,d in (("train",tp),("val",vp)):
    print(f"  positives {nm:7s} n={len(d):5d}  duplicate 5dp coords="
          f"{int(d[['longitude','latitude']].round(5).duplicated().sum())}")
print("\n== CR-0008: is the NLCD valid mask time-invariant? ==")
for r in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s: a=s.read(1)!=-9999
    with rasterio.open(f"data/landfire/{r}_2025_nlcd.tif") as s: b=s.read(1)!=-9999
    print(f"  {r}: 2016 vs 2025 NLCD valid mask differs on {int((a^b).sum()):,} px"
          f"  (CR claims 0)")
    del a,b
