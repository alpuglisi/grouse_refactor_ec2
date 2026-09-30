import numpy as np, rasterio, os
from grouse_data import GrouseData
d=GrouseData()
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
    usvalid=(nl>=11)&(nl<=95)
    with rasterio.open(r.raster_path('evt',2022)) as s: ev=s.read(1)
    evvalid=(ev!=-9999); del ev
    ylast=r.raster_years('balive')[-1]
    with rasterio.open(r.raster_path('balive',ylast)) as s: ba=s.read(1)
    ytcc=r.raster_years('tcc')[-1]
    with rasterio.open(r.raster_path('tcc',ytcc)) as s: tc=s.read(1)
    print("="*64); print(reg)
    print(f"  balive==0 share of evt-valid grid (y={ylast}) = {((ba==0)&evvalid).sum()/evvalid.sum():.4f}")
    bz=(ba==0)
    print(f"  of those balive zeros, inside the US          = {(bz&usvalid).sum()/bz.sum():.4f}")
    print(f"  tcc==0 share of evt-valid grid (y={ytcc})     = {((tc==0)&evvalid).sum()/evvalid.sum():.4f}")
    tz=(tc==0)
    print(f"  share of tcc zeros inside the US (real 0% cc) = {(tz&usvalid).sum()/tz.sum():.4f}")
    print(f"  balive > 0 OUTSIDE the NLCD footprint        = {int(((ba>0)&~usvalid).sum()):,}")
    print(f"  balive nonzero-nodata outside footprint      = {int((~usvalid).sum()):,} px outside total")
    # centre-pixel balive==0 for train positives
    import pyproj
    tr=pyproj.Transformer.from_crs('EPSG:4326', s.crs, always_xy=True)
    with rasterio.open(r.raster_path('balive',ylast)) as s2:
        for split in ['train']:
            for nm,get in (('pos',lambda: r.positives(split)),('neg',lambda: r.negatives(split))):
                df=get()
                x,y=tr.transform(df.longitude.values, df.latitude.values)
                vals=np.array([v[0] for v in s2.sample(list(zip(x,y)))])
                print(f"  {split} {nm}: n={len(df)} balive==0 at centre = {(vals==0).mean():.4f}")
    del nl,usvalid,evvalid,ba,tc
