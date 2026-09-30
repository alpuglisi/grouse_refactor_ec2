import numpy as np, rasterio
from grouse_data import GrouseData
import models
d=GrouseData()
print("TSD_MAX_YEARS:", getattr(models,'TSD_MAX_YEARS','?'))
import generate_time_since_disturbance as T
print("T.TSD_MAX_YEARS:", getattr(T,'TSD_MAX_YEARS','?'))
sat = None
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1)
    valid=(nl>=11)&(nl<=95); del nl
    print("="*60); print(reg, "in-coverage (NLCD-valid) FULL-RES counts")
    for y in r.raster_years('tsd'):
        with rasterio.open(r.raster_path('tsd',y)) as s:
            a=s.read(1)
        z=int(((a==0)&valid).sum())
        u,c=np.unique(a[valid],return_counts=True)
        top=u[np.argmax(c)]
        satshare=float((a[valid]==top).mean())
        print(f"  tsd {y}: in-cov zeros={z:>10,}  modal value={top} share={satshare:.4f}  min={a[valid].min()} max={a[valid].max()}")
        del a
    del valid
