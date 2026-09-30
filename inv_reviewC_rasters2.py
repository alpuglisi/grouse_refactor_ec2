import numpy as np, rasterio
from grouse_data import GrouseData
STEP=8
rd=GrouseData()["ME"]
with rasterio.open(rd.latest_raster_path("evt")) as s:
    evt=s.read(1)[::STEP,::STEP]; nd=s.nodata
ins=evt!=nd
for f in ("tcc","nlcd","tsd"):
    p=rd.latest_raster_path(f)
    with rasterio.open(p) as s:
        a=s.read(1)[::STEP,::STEP]; fnd=s.nodata
    print(f"\n--- ME {f}  ({p})  nodata={fnd}")
    v=a[ins]
    u,c=np.unique(v,return_counts=True)
    order=np.argsort(-c)[:12]
    print("  INSIDE evt-cov top values:", [(float(u[i]),int(c[i])) for i in order])
    v2=a[~ins]
    u2,c2=np.unique(v2,return_counts=True)
    order2=np.argsort(-c2)[:8]
    print("  OUTSIDE evt-cov top values:", [(float(u2[i]),int(c2[i])) for i in order2])
