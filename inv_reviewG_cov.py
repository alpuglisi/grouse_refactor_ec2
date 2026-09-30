import numpy as np, rasterio, sys
from grouse_data import GrouseData
d=GrouseData()
regs=['ME','NH','VT']
STEP=8
def read(reg,feat,year=None,step=1):
    r=d[reg]
    yrs=r.raster_years(feat)
    y=year if year is not None else yrs[0]
    p=r.raster_path(feat,y)
    with rasterio.open(p) as s:
        a=s.read(1)[::step,::step]
        return a, s.nodata, p, yrs
for reg in regs:
    r=d[reg]
    print("="*70)
    print(reg)
    for feat in ['nlcd','evt','tcc','tsd','balive','tpa_live','qmd','carbon_dwn','road_dist']:
        try:
            yrs=r.raster_years(feat)
        except Exception as e:
            print(f"  {feat}: ERR {e}"); continue
        print(f"  {feat}: years={yrs}")
