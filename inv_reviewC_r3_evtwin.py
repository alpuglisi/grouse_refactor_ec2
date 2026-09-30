"""Confirm v3's own measurement (0 records with a nodata evt pixel in-window)
and contrast it with the same test against the NLCD footprint (§ Coverage)."""
import rasterio, numpy as np, pandas as pd
HALF=32
for r in ("ME","NH","VT"):
    out={}
    for feat,path in (("evt",f"data/landfire/{r}_2022_evt.tif"),("nlcd",f"data/landfire/{r}_2016_nlcd.tif")):
        with rasterio.open(path) as s:
            a=s.read(1); bad=(a==-9999); T=s.transform; crs=s.crs; H,W=a.shape
        ii=np.cumsum(np.cumsum(bad.astype(np.int64),0),1)
        for cls,paths in (("pos",[f"data/pipeline/{sp}_positives_{r}.csv" for sp in ("train","val")]),
                          ("neg",[f"data/negatives/{sp}_negatives_{r}.csv" for sp in ("train","val")])):
            df=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
            import rasterio.warp as rw
            xs,ys=rw.transform("EPSG:4326",crs,list(df.longitude),list(df.latitude))
            rr,cc=rasterio.transform.rowcol(T,xs,ys); rr=np.asarray(rr); cc=np.asarray(cc)
            r0=np.clip(rr-HALF,0,H-1); r1=np.clip(rr+HALF-1,0,H-1)
            c0=np.clip(cc-HALF,0,W-1); c1=np.clip(cc+HALF-1,0,W-1)
            S=lambda A,B: ii[np.clip(A,0,H-1),np.clip(B,0,W-1)]
            tot=S(r1,c1)-np.where(r0>0,S(r0-1,c1),0)-np.where(c0>0,S(r1,c0-1),0)+np.where((r0>0)&(c0>0),S(r0-1,c0-1),0)
            out[(feat,cls)]=(int((tot>0).sum()),len(df))
    for cls in ("pos","neg"):
        e=out[("evt",cls)]; n=out[("nlcd",cls)]
        print(f"  {r} {cls}: windows touching evt-nodata {e[0]}/{e[1]}  vs  outside NLCD footprint {n[0]}/{n[1]}")
