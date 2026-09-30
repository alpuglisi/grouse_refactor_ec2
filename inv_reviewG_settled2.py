import numpy as np, rasterio, pyproj
from grouse_data import GrouseData
d=GrouseData()
tot_tz=0; tot_tz_us=0; tot_bz=0; tot_bz_us=0
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
    us=(nl>=11)&(nl<=95); del nl
    with rasterio.open(r.raster_path('evt',2022)) as s: ev=s.read(1)
    evv=(ev!=-9999); del ev
    with rasterio.open(r.raster_path('balive',2025)) as s: ba=s.read(1)
    with rasterio.open(r.raster_path('tcc',2023)) as s: tc=s.read(1); crs=s.crs
    bz=(ba==0); tz=(tc==0)
    print(f"{reg}:")
    print(f"   balive==0 & evt-valid -> inside US share = {(bz&evv&us).sum()/max((bz&evv).sum(),1):.4f}")
    print(f"   tcc==0 inside-US share (this region)     = {(tz&us).sum()/max(tz.sum(),1):.4f}")
    print(f"   tcc==0 & evt-valid -> inside US share    = {(tz&evv&us).sum()/max((tz&evv).sum(),1):.4f}")
    tot_tz+=int(tz.sum()); tot_tz_us+=int((tz&us).sum())
    tot_bz+=int(bz.sum()); tot_bz_us+=int((bz&us).sum())
    # centre pixel over all positives / all records
    tr=pyproj.Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    with rasterio.open(r.raster_path('balive',2025)) as s2:
        for nm,df in (('pos all',r.positives('all')),('neg all',r.negatives('all'))):
            x,y=tr.transform(df.longitude.values,df.latitude.values)
            v=np.array([q[0] for q in s2.sample(list(zip(x,y)))])
            print(f"   {nm}: n={len(df)} balive==0 at centre = {(v==0).mean():.4f}")
    del us,evv,ba,tc,bz,tz
print(f"\nPOOLED across 3 regions: tcc==0 inside-US share = {tot_tz_us/tot_tz:.4f}  (CR claims 18.4%)")
print(f"POOLED across 3 regions: balive==0 inside-US share = {tot_bz_us/tot_bz:.4f}  (CR claims 35% for ME)")
