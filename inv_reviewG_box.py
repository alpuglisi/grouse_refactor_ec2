import numpy as np, rasterio, pandas as pd
from rasterio.warp import transform_bounds
from grouse_data import GrouseData
import regions
d=GrouseData()
BOX=(-71.25,44.70,-70.95,44.90)
for reg in ['NH','ME']:
    p=d[reg].raster_path('evt',2024)
    with rasterio.open(p) as s:
        b=transform_bounds(s.crs,'EPSG:4326',*s.bounds)
    print(f"{reg} grid lon/lat extent: {tuple(round(x,4) for x in b)}  (BOXES={regions.BOXES[reg]})")
    covers = b[0]<=BOX[0] and b[1]<=BOX[1] and b[2]>=BOX[2] and b[3]>=BOX[3]
    print(f"   covers Errol box {BOX}? {covers}")
    if not covers:
        w = max(b[0],BOX[0]); e=min(b[2],BOX[2])
        print(f"   -> usable lon span {w:.4f}..{e:.4f} = {(e-w)/(BOX[2]-BOX[0])*100:.1f}% of the requested box width")
print()
print("=== records inside the Errol box ===")
for reg in ['NH','ME','VT']:
    rd=d[reg]
    for split in ['train','val']:
        try: pos=rd.positives(split)
        except Exception as e: print(reg,split,'pos ERR',e); pos=None
        try: neg=rd.negatives(split)
        except Exception as e:
            neg=None
        for nm,df in (('pos',pos),('neg',neg)):
            if df is None: 
                print(f"  {reg} {split} {nm}: n/a"); continue
            m=(df.longitude>=BOX[0])&(df.longitude<=BOX[2])&(df.latitude>=BOX[1])&(df.latitude<=BOX[3])
            sub=df[m]
            st = sub['state'].value_counts().to_dict() if 'state' in sub.columns else 'NO state col'
            print(f"  {reg} {split} {nm}: total={len(df)} in-box={len(sub)} by state={st}")
