"""Round-2: BUG-0025's fix spec says 'drop the unmask(0) fill outside
TreeMap coverage'. Inside CONUS, is 0 also what non-forest pixels read?
If so the fix changes training patches, not just out-of-coverage area."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from grouse_data import GrouseData
data=GrouseData(); R=["ME","NH","VT"]
ev=[]
for r in R:
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv"); d["src"]=r; ev.append(d)
ev=pd.concat(ev,ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
u=ev[~ev.nonveg_landcover.astype(bool)]; u=u.loc[~u.key.duplicated()]
for r in R:
    sub=u[u.state==r]
    for feat in ("balive","tcc","tsd"):
        p=data[r].latest_raster_path(feat)
        with rasterio.open(p) as s:
            tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
            x,y=tr.transform(sub.longitude.values,sub.latitude.values)
            v=np.array([q[0] for q in s.sample(zip(x,y))],dtype=np.float64)
            rr,cc=rasterio.transform.rowcol(s.transform,x,y)
            rr=np.asarray(rr); cc=np.asarray(cc)
            zc=0; tot=0
            for i in range(0,len(sub),max(1,len(sub)//300)):   # ~300 windows
                w=rasterio.windows.Window(cc[i]-32,rr[i]-32,64,64)
                a=s.read(1,window=w,boundless=True,fill_value=-9999)
                zc+=int((a==0).sum()); tot+=a.size
            sent = 3434 if feat=="tsd" else 0
            print(f"  {r} {feat:<8} center pixel == {sent}: "
                  f"{int((v==sent).sum()):>5} of {len(sub)} records "
                  f"({100*(v==sent).mean():5.1f}%) | pixels == 0 inside "
                  f"sampled 64x64 windows: {100*zc/max(tot,1):5.1f}%")
