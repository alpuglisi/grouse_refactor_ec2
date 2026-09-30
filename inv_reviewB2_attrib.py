"""Round-2: (1) do the 1,982 reassigned records land on valid data in
their NEW region's rasters? (2) how many training patches actually change
when the six fabricated-fill channels are regenerated? Read-only."""
import numpy as np, pandas as pd, rasterio, glob
from pyproj import Transformer
from grouse_data import GrouseData, NODATA_SENTINELS, RASTER_FEATURES
R=["ME","NH","VT"]; data=GrouseData()

# ---- pooled, state-partitioned positives (the post-CR membership) -------
ev=[]
for r in R:
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv"); d["src"]=r; ev.append(d)
ev=pd.concat(ev,ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
hab=ev[~ev.nonveg_landcover.astype(bool)]
u=hab.loc[~hab.key.duplicated()].copy()          # state column == region post-CR
moved=u[u.state!=u.src]
print(f"unique habitat positives {len(u)}; of these {len(moved)} sit in a "
      f"different region's file today than their state column says "
      f"(= the reassigned set)")

print("\n=== 1. bounds + nodata for EVERY feature of the NEW region ===")
for r in R:
    sub=u[u.state==r]
    feats=[f for f in RASTER_FEATURES if data[r].raster_years(f)]
    worst_oob=0; bad=[]
    for f in feats:
        for yr in sorted(data[r].raster_years(f)):
            p=data[r].raster_path(f,yr,validate=False)
            with rasterio.open(p) as s:
                tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
                x,y=tr.transform(sub.longitude.values,sub.latitude.values)
                rr,cc=rasterio.transform.rowcol(s.transform,x,y)
                rr=np.asarray(rr); cc=np.asarray(cc)
                oob=int(((rr-32<0)|(cc-32<0)|(rr+32>s.height)|(cc+32>s.width)).sum())
                v=np.array([q[0] for q in s.sample(zip(x,y))],dtype=np.float64)
                nod=int(np.isin(v,list(NODATA_SENTINELS)).sum()
                        + (np.isnan(v).sum() if v.dtype.kind=='f' else 0))
                if oob or nod: bad.append((f,yr,oob,nod))
                worst_oob=max(worst_oob,oob)
    print(f"  {r}: {len(sub)} records x {len(feats)} features, "
          f"max out-of-window {worst_oob}")
    for f,yr,oob,nod in bad[:12]:
        print(f"      {f} {yr}: out-of-window {oob}, center-pixel nodata {nod}")
    if not bad: print("      no out-of-window, no center-pixel nodata anywhere")

print("\n=== 2. how many 64x64 windows TOUCH the LANDFIRE coverage edge? ===")
print("   (those are the only training patches whose tsd/treemap/tcc values")
print("    change when the fabricated fill becomes NODATA)")
for r in R:
    sub=u[u.state==r]
    p=data[r].latest_raster_path("evt")
    with rasterio.open(p) as s:
        tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
        x,y=tr.transform(sub.longitude.values,sub.latitude.values)
        rr,cc=rasterio.transform.rowcol(s.transform,x,y)
        rr=np.asarray(rr); cc=np.asarray(cc); n_touch=0
        for i in range(len(sub)):
            w=rasterio.windows.Window(cc[i]-32,rr[i]-32,64,64)
            a=s.read(1,window=w,boundless=True,fill_value=-9999)
            if np.isin(a,list(NODATA_SENTINELS)).any(): n_touch+=1
    print(f"  {r}: {n_touch} of {len(sub)} records ({100*n_touch/max(len(sub),1):.2f}%) "
          f"have >=1 nodata evt pixel in their 64x64 window")
