import rasterio, itertools
from grouse_data import GrouseData
d=GrouseData()
FE=['nlcd','tcc','balive','tpa_live','qmd','carbon_dwn','tsd','road_dist','evt']
n=0; bad=0
for reg in ['ME','NH','VT']:
    r=d[reg]; ref=None
    for f in FE:
        ys=r.raster_years(f)
        for y in [ys[0],ys[-1]]:
            p=r.raster_path(f,y); n+=1
            with rasterio.open(p) as s:
                sig=(s.transform,s.width,s.height,str(s.crs),s.dtypes[0],s.nodata)
            if ref is None: ref=sig; print(f"{reg} ref {f}{y}: dtype={sig[4]} nodata={sig[5]} {sig[1]}x{sig[2]}")
            elif sig!=ref:
                bad+=1; print(f"  MISMATCH {reg} {f} {y}: {sig} vs {ref}")
print(f"\nfiles checked={n} mismatches={bad}")
