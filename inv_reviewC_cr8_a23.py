"""CR-0008 A3 units, and an attempt to BREAK A2."""
import rasterio, numpy as np, pandas as pd, rasterio.warp as rw
STEP=8
print("=== A3: 'share of pixels reading TSD_MAX inside coverage' vs 'training centre pixels'")
for r in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s:
        nl=s.read(1); T=s.transform; crs=s.crs
    inside_full=nl!=-9999
    with rasterio.open(f"data/landfire/{r}_2025_tsd.tif") as s: ts=s.read(1)
    SAT=3434
    d=inside_full[::STEP,::STEP]; t=ts[::STEP,::STEP]
    pix=(t[d]==SAT).mean()
    # training centre pixels
    dfs=[]
    for cls,ps in (("pos",[f"data/pipeline/{sp}_positives_{r}.csv" for sp in ("train","val")]),
                   ("neg",[f"data/negatives/{sp}_negatives_{r}.csv" for sp in ("train","val")])):
        df=pd.concat([pd.read_csv(p) for p in ps],ignore_index=True)
        xs,ys=rw.transform("EPSG:4326",crs,list(df.longitude),list(df.latitude))
        rr,cc=rasterio.transform.rowcol(T,xs,ys)
        v=ts[np.clip(rr,0,ts.shape[0]-1),np.clip(cc,0,ts.shape[1]-1)]
        dfs.append((cls,(v==SAT).mean(),len(df)))
    print(f"  {r}: in-coverage PIXELS at TSD_MAX = {100*pix:.1f}%   |   "
          + "  ".join(f"{c} centre px at TSD_MAX = {100*f:.1f}% (n={n})" for c,f,n in dfs))

print("\n=== BREAK A2: a regeneration that passes A1, A2, A3 and A5 but corrupts in-coverage values")
r="ME"
with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s: nl=s.read(1)[::STEP,::STEP]
inside=nl!=-9999; out=~inside
with rasterio.open(f"data/landfire/{r}_2025_balive.tif") as s: a=s.read(1)[::STEP,::STEP].astype(np.int32)
good=a.copy(); good[out]=-9999                       # the correct repair
bad=a.copy();  bad[out]=-9999
bad[inside & (a>0)] = np.clip(bad[inside&(a>0)]*2,None,32767)   # in-coverage values doubled
for name,arr in (("CORRECT repair",good),("CORRUPT (in-cov values doubled)",bad)):
    print(f"  {name}:")
    print(f"     A1 out-of-coverage nodata frac = {(arr[out]==-9999).mean():.4f}   (require >=0.99)  "
          f"{'PASS' if (arr[out]==-9999).mean()>=0.99 else 'FAIL'}")
    z=int((arr[inside]==0).sum())
    print(f"     A2 in-coverage zero count      = {z:,}   (require == 437,796)  {'PASS' if z==437796 else 'FAIL'}")
    print(f"     A5 grid identity               = PASS (same shape/transform/dtype/nodata by construction)")
    print(f"     in-coverage mean of nonzero    = {arr[inside&(arr>0)].mean():.1f}   <-- only a value check sees this")
    bitid=bool((arr[inside]==a[inside]).all())
    print(f"     bit-identity inside coverage   = {bitid}   <-- the check the CR does NOT require")
