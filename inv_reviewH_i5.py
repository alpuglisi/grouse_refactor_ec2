"""CR-0007 I5 on the POST-PARTITION pooled positive set (the one the rebuild
ships), and on the negative candidate pool.  The CR calls I5 'unfailable by
construction' -- but the construction (drop windowless records) is specified
only for negatives, in generate_negatives.py; nothing drops positives."""
import numpy as np, pandas as pd, rasterio, glob
from pyproj import Transformer
IMG=64; HALF=IMG//2
grids={}
for r in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{r}_2025_nlcd.tif") as s:
        grids[r]=(s.height,s.width,s.transform,s.crs)
def windowless(df,regcol):
    bad=[]
    for r,g in df.groupby(regcol):
        H,W,T,CRS=grids[r]
        tr=Transformer.from_crs("EPSG:4326",CRS,always_xy=True)
        x,y=tr.transform(g.longitude.values,g.latitude.values)
        inv=~T
        col,row=inv*(x,y)
        col=np.floor(col).astype(int); row=np.floor(row).astype(int)
        ok=(row-HALF>=0)&(row-HALF+IMG<=H)&(col-HALF>=0)&(col-HALF+IMG<=W)
        bad.append((r,int((~ok).sum()),len(g)))
    return bad
t=pd.read_csv("inv_reviewH_pooled_positives.csv")
print("POST-partition pooled positives (state == region), 64 px window:")
for r,n,tot in windowless(t,"state"): print(f"   {r}: {n} of {tot} windowless")
old=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(reg=r)
               for r in ("ME","NH","VT")],ignore_index=True)
print("PRE-partition thinned positives (filing region), 64 px window:")
for r,n,tot in windowless(old,"reg"): print(f"   {r}: {n} of {tot} windowless   (CR I5: NH 4, ME 0, VT 0)")
C=[]
for r in ("ME","NH","VT"):
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv"); c["reg"]=r; C.append(c)
C=pd.concat(C,ignore_index=True)
print(f"raw negative candidates by filing region, 64 px window (CR: NH 721 of 69,219, ME 2, VT 0):")
for r,n,tot in windowless(C,"reg"): print(f"   {r}: {n} of {tot} windowless")
# post-partition NH 30 km positive-occupied blocks (CR-0007 says 39)
B=30000.0
for r in ("ME","NH","VT"):
    g=t[t.state==r]
    nb=len(set(zip(np.floor(g.x_5070/B).astype(int),np.floor(g.y_5070/B).astype(int))))
    print(f"post-partition {r}: {len(g)} positives in {nb} occupied 30 km blocks "
          f"-> I10 granularity 1/{nb} = {1/nb:.4f}"
          + ("   (CR-0007 says NH has only 39)" if r=="NH" else ""))
